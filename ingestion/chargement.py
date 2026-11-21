"""Chargement d'un fichier CSV dans une table bronze (COPY), commun à toutes les sources."""

import csv
import hashlib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import psycopg
from psycopg import sql

from ingestion.config import SCHEMA, ErreurIngestion

COLONNES_TECHNIQUES = ("_id_run", "_source", "_num_ligne", "_sha256")


@dataclass(frozen=True)
class Resultat:
    """Bilan du chargement d'un fichier."""

    nb_lignes: int
    sha256: str
    max_date_maj: datetime | None


def sha256_fichier(chemin: Path) -> str:
    """Empreinte SHA-256 d'un fichier."""
    return hashlib.sha256(chemin.read_bytes()).hexdigest()


def charger_fichier(
    cur: psycopg.Cursor[Any],
    table: str,
    colonnes: tuple[str, ...],
    chemin: Path,
    chemin_relatif: str,
    id_run: str,
    cle_conflit: tuple[str, ...] | None = None,
) -> Resultat:
    """Charge un CSV (en-tête compris) dans bronze.<table>, avec les colonnes techniques.

    Sans `cle_conflit` (tables csv_*) : COPY direct, aucun dédoublonnage.
    Avec `cle_conflit` (tables ops_*) : COPY dans une table de lot temporaire, puis
    INSERT … ON CONFLICT (clé, date_maj) DO NOTHING, filet de sécurité de l'incrémental.
    Valeur vide → NULL ; _num_ligne = numéro de ligne physique dans le fichier.
    """
    empreinte = sha256_fichier(chemin)
    cible = sql.Identifier(SCHEMA, table)
    lot = sql.Identifier(f"_lot_{table}")
    if cle_conflit is not None:
        cur.execute(
            sql.SQL("CREATE TEMP TABLE {} (LIKE {} INCLUDING DEFAULTS) ON COMMIT DROP").format(
                lot, cible
            )
        )
    noms = sql.SQL(", ").join(sql.Identifier(c) for c in colonnes + COLONNES_TECHNIQUES)
    copie_sql = sql.SQL("COPY {} ({}) FROM STDIN").format(
        lot if cle_conflit is not None else cible, noms
    )
    nb = 0
    with chemin.open(encoding="utf-8", newline="") as fichier:
        lecteur = csv.reader(fichier)
        entete = next(lecteur, None)
        if entete is None or tuple(entete) != colonnes:
            raise ErreurIngestion(f"en-tête inattendu dans {chemin_relatif} : {entete}")
        with cur.copy(copie_sql) as copie:
            for ligne in lecteur:
                if len(ligne) != len(colonnes):
                    raise ErreurIngestion(
                        f"{chemin_relatif}, ligne {lecteur.line_num} : {len(ligne)} colonnes "
                        f"au lieu de {len(colonnes)}"
                    )
                valeurs: list[Any] = [v if v != "" else None for v in ligne]
                copie.write_row([*valeurs, id_run, chemin_relatif, lecteur.line_num, empreinte])
                nb += 1

    if cle_conflit is None:
        return Resultat(nb, empreinte, None)

    cur.execute(
        sql.SQL("INSERT INTO {} SELECT * FROM {} ON CONFLICT ({}) DO NOTHING").format(
            cible,
            lot,
            sql.SQL(", ").join(sql.Identifier(c) for c in (*cle_conflit, "date_maj")),
        )
    )
    inseres = cur.rowcount
    cur.execute(sql.SQL("SELECT max(date_maj) FROM {}").format(lot))
    ligne_max = cur.fetchone()
    cur.execute(sql.SQL("DROP TABLE {}").format(lot))
    return Resultat(inseres, empreinte, ligne_max[0] if ligne_max else None)
