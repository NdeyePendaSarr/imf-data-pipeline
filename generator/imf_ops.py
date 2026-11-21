"""Chargement de la base opérationnelle simulée imf_ops (rechargement complet)."""

import os
from dataclasses import astuple, fields
from pathlib import Path
from typing import Any

import psycopg

from generator.anomalies import Brut

DDL = Path(__file__).parent / "sql" / "imf_ops.sql"

# Tables de imf_ops, dans l'ordre de chargement (parents avant enfants).
TABLES_IMF_OPS = (
    "produits_credit",
    "clients",
    "comptes",
    "credits",
    "echeancier",
    "remboursements",
)


class ErreurConnexion(RuntimeError):
    """Configuration absente ou PostgreSQL injoignable."""


def parametres_connexion(dbname: str | None = None) -> dict[str, Any]:
    """Paramètres de connexion lus uniquement dans les variables d'environnement (.env)."""
    utilisateur = os.getenv("POSTGRES_USER")
    mot_de_passe = os.getenv("POSTGRES_PASSWORD")
    if not utilisateur or not mot_de_passe:
        raise ErreurConnexion(
            "POSTGRES_USER ou POSTGRES_PASSWORD absent : copie .env.example en .env"
        )
    return {
        "host": os.getenv("POSTGRES_HOST", "localhost"),
        "port": int(os.getenv("POSTGRES_PORT", "5433")),
        "user": utilisateur,
        "password": mot_de_passe,
        "dbname": dbname or os.getenv("POSTGRES_DB_OPS", "imf_ops"),
        "connect_timeout": 5,
    }


def connecter(dbname: str | None = None) -> psycopg.Connection:
    """Ouvre une connexion ; message clair si PostgreSQL est injoignable."""
    parametres = parametres_connexion(dbname)
    try:
        return psycopg.connect(**parametres)
    except psycopg.OperationalError as erreur:
        raise ErreurConnexion(
            f"PostgreSQL injoignable : lance `make up` (base {parametres['dbname']} : {erreur})"
        ) from erreur


def charger(brut: Brut, dbname: str | None = None) -> dict[str, int]:
    """Recrée le schéma et recharge toutes les tables dans une seule transaction."""
    comptes: dict[str, int] = {}
    with connecter(dbname) as conn, conn.cursor() as cur:
        # Sans paramètre, psycopg envoie le script entier en une requête simple.
        cur.execute(DDL.read_text(encoding="utf-8").encode())
        for table in TABLES_IMF_OPS:
            lignes = getattr(brut, table)
            colonnes = ", ".join(f.name for f in fields(lignes[0]))
            with cur.copy(f"COPY {table} ({colonnes}) FROM STDIN") as copie:
                for ligne in lignes:
                    copie.write_row(astuple(ligne))
            comptes[table] = len(lignes)
        # Sortie du bloc `with conn` : COMMIT (ou ROLLBACK en cas d'erreur).
    return comptes
