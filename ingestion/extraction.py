"""Extraction incrémentale de imf_ops vers data/landing (COPY TO STDOUT)."""

import csv
import os
from pathlib import Path
from typing import Any

import psycopg
from psycopg import sql

from ingestion.config import ObjetOps
from ingestion.fenetre import Fenetre


def requete_extraction(objet: ObjetOps, fenetre: Fenetre) -> sql.Composed:
    """SELECT de la fenêtre ]filigrane, J+1 00:00[, trié par clé (ordre déterministe)."""
    conditions = [sql.SQL("date_maj < {}").format(sql.Literal(fenetre.fin_exclue))]
    if fenetre.debut_exclu is not None:
        conditions.append(sql.SQL("date_maj > {}").format(sql.Literal(fenetre.debut_exclu)))
    return sql.SQL("SELECT {} FROM {} WHERE {} ORDER BY {}").format(
        sql.SQL(", ").join(sql.Identifier(c) for c in objet.colonnes),
        sql.Identifier(objet.objet),
        sql.SQL(" AND ").join(conditions),
        sql.SQL(", ").join(sql.Identifier(c) for c in objet.cle),
    )


def extraire(
    conn_ops: psycopg.Connection[Any], objet: ObjetOps, fenetre: Fenetre, destination: Path
) -> int:
    """Écrit l'extraction en CSV (en-tête) dans `destination` ; renvoie le nombre de lignes.

    Rien n'est écrit si la fenêtre ne contient aucune ligne : un fichier d'atterrissage
    existant n'est jamais écrasé par une extraction vide. L'écriture passe par un fichier
    temporaire renommé, pour ne jamais laisser de fichier tronqué.
    """
    if fenetre.vide:
        return 0
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporaire = destination.with_suffix(".csv.tmp")
    copie_sql = sql.SQL("COPY ({}) TO STDOUT WITH (FORMAT csv, HEADER)").format(
        requete_extraction(objet, fenetre)
    )
    with (
        conn_ops.cursor() as cur,
        temporaire.open("wb") as fichier,
        cur.copy(copie_sql) as copie,
    ):
        for bloc in copie:
            fichier.write(bloc)
    with temporaire.open(encoding="utf-8", newline="") as fichier:
        nb = sum(1 for _ in csv.reader(fichier)) - 1
    if nb <= 0:
        temporaire.unlink()
        if not any(destination.parent.iterdir()):
            destination.parent.rmdir()
        return 0
    os.replace(temporaire, destination)
    return nb
