"""Empreinte du schéma gold : MD5 du contenu trié de chaque table, toutes colonnes.

Sert à prouver qu'un gold construit jour par jour (backfill Airflow) est identique à un gold
construit en une fois (dbt build à la même date d'arrêté).

    python -m orchestration.empreinte calculer FICHIER   # make empreinte-gold FICHIER=…
    python -m orchestration.empreinte comparer A B       # make compare-empreintes A=… B=…

Codes de sortie : 0 = succès (empreintes identiques), 1 = échec.
"""

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psycopg
from dotenv import load_dotenv
from psycopg import sql

from ingestion.config import parametres_connexion

SCHEMA = "gold"
NB_TABLES = 19
# MD5 de la chaîne vide (string_agg sur zéro ligne) : jamais écrit tel quel.
MD5_VIDE = "d41d8cd98f00b204e9800998ecf8427e"
# Empreinte notée pour une table légitimement vide (ex. mart_kpi_portefeuille avant la première
# fin de mois) : acceptée, contrairement à une empreinte absente ou mal formée.
VIDE = "VIDE"
CHIFFRES_HEXA = frozenset("0123456789abcdef")


class ErreurEmpreinte(Exception):
    """Empreinte incomplète ou illisible."""


@dataclass(frozen=True)
class Empreinte:
    table: str
    lignes: int
    md5: str


def calculer(conn: psycopg.Connection[Any]) -> list[Empreinte]:
    """Une empreinte par table du schéma gold, triée par nom de table."""
    tables = [
        ligne[0]
        for ligne in conn.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = %s ORDER BY 1", (SCHEMA,)
        ).fetchall()
    ]
    empreintes = []
    for table in tables:
        requete = sql.SQL(
            "SELECT count(*), md5(coalesce(string_agg(x::text, '|' ORDER BY x::text), '')) "
            "FROM {} AS x"
        ).format(sql.Identifier(SCHEMA, table))
        resultat = conn.execute(requete).fetchone()
        assert resultat is not None
        lignes = int(resultat[0])
        empreintes.append(Empreinte(table, lignes, VIDE if lignes == 0 else resultat[1] or ""))
    return empreintes


def _md5_valide(md5: str) -> bool:
    return len(md5) == 32 and set(md5) <= CHIFFRES_HEXA and md5 != MD5_VIDE


def valider(empreintes: list[Empreinte]) -> None:
    """Exactement 19 tables ; table vide notée VIDE, sinon un MD5 de 32 caractères hexa.

    Refusé (sortie cassée) : empreinte absente ou mal formée, VIDE sur une table qui a des
    lignes, MD5 de la chaîne vide, ou MD5 sur une table annoncée à 0 ligne.
    """
    if len(empreintes) != NB_TABLES:
        raise ErreurEmpreinte(f"{len(empreintes)} table(s) gold au lieu de {NB_TABLES}")
    cassees = [
        e.table for e in empreintes if not (e.md5 == VIDE if e.lignes == 0 else _md5_valide(e.md5))
    ]
    if cassees:
        raise ErreurEmpreinte(f"empreinte cassée : {', '.join(cassees)}")


def ecrire(empreintes: list[Empreinte], fichier: Path) -> None:
    fichier.parent.mkdir(parents=True, exist_ok=True)
    texte = "".join(f"{e.table} {e.lignes} {e.md5}\n" for e in empreintes)
    fichier.write_text(texte, encoding="utf-8")


def lire(fichier: Path) -> list[Empreinte]:
    empreintes = []
    for numero, ligne in enumerate(fichier.read_text(encoding="utf-8").splitlines(), start=1):
        morceaux = ligne.split()
        if len(morceaux) != 3 or not morceaux[1].isdigit():
            raise ErreurEmpreinte(f"{fichier}:{numero} : ligne illisible « {ligne} »")
        empreintes.append(Empreinte(morceaux[0], int(morceaux[1]), morceaux[2]))
    valider(empreintes)
    return empreintes


def comparer(a: list[Empreinte], b: list[Empreinte]) -> list[str]:
    """Écarts entre deux empreintes (vide = identiques)."""
    index_a = {e.table: e for e in a}
    index_b = {e.table: e for e in b}
    ecarts = []
    for table in sorted(index_a.keys() | index_b.keys()):
        ea, eb = index_a.get(table), index_b.get(table)
        if ea is None or eb is None:
            ecarts.append(f"{table} : présente d'un seul côté")
        elif ea != eb:
            ecarts.append(f"{table} : {ea.lignes} {ea.md5} ≠ {eb.lignes} {eb.md5}")
    return ecarts


def main(arguments: list[str] | None = None) -> int:
    parseur = argparse.ArgumentParser(prog="python -m orchestration.empreinte")
    sous = parseur.add_subparsers(dest="action", required=True)
    sous.add_parser("calculer").add_argument("fichier", type=Path)
    comparaison = sous.add_parser("comparer")
    comparaison.add_argument("a", type=Path)
    comparaison.add_argument("b", type=Path)
    args = parseur.parse_args(arguments)
    try:
        if args.action == "calculer":
            load_dotenv()
            base = parametres_connexion(os.getenv("POSTGRES_DB_DWH", "imf_dwh"))
            with psycopg.connect(**base) as conn:
                empreintes = calculer(conn)
            valider(empreintes)
            ecrire(empreintes, args.fichier)
            vides = [e.table for e in empreintes if e.md5 == VIDE]
            note = f" (table(s) vide(s) : {', '.join(vides)})" if vides else ""
            print(f"{len(empreintes)} tables gold → {args.fichier}{note}")
            return 0
        ecarts = comparer(lire(args.a), lire(args.b))
    except (ErreurEmpreinte, OSError, psycopg.Error) as erreur:
        print(f"Erreur : {erreur}", file=sys.stderr)
        return 1
    if ecarts:
        print(f"{len(ecarts)} table(s) différente(s) :", *ecarts, sep="\n  ", file=sys.stderr)
        return 1
    print(f"Empreintes identiques ({NB_TABLES} tables) : {args.a} = {args.b}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
