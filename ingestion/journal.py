"""Journal d'ingestion, filigranes et empreinte de génération (schéma bronze)."""

import hashlib
import json
from dataclasses import astuple, dataclass, fields
from datetime import date, datetime
from typing import Any

import psycopg

from ingestion.config import ErreurIngestion

# Clés du manifeste qui ne dépendent que de la génération (aucun horodatage d'exécution).
CLES_DETERMINISTES = ("parametres", "lignes", "indicateurs", "fichiers")


@dataclass(frozen=True)
class LigneJournal:
    """Une ligne de bronze._ingestions : un objet traité lors d'un run."""

    id_run: str
    empreinte_generation: str
    jour: date
    source: str
    objet: str
    chemin: str | None
    sha256: str | None
    nb_lignes: int
    filigrane_avant: datetime | None
    filigrane_apres: datetime | None
    statut: str
    debut: datetime
    fin: datetime


def empreinte_generation(manifeste: dict[str, Any]) -> str:
    """SHA-256 de la partie déterministe du manifeste (JSON canonique, clés triées)."""
    partie = {cle: manifeste[cle] for cle in CLES_DETERMINISTES if cle in manifeste}
    texte = json.dumps(partie, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(texte.encode("utf-8")).hexdigest()


def verifier_empreinte(cur: psycopg.Cursor[Any], empreinte: str) -> None:
    """Refuse d'ingérer si bronze contient des runs issus d'une autre génération."""
    cur.execute(
        "SELECT DISTINCT empreinte_generation FROM bronze._ingestions "
        "WHERE empreinte_generation <> %s",
        (empreinte,),
    )
    if cur.fetchone() is not None:
        raise ErreurIngestion(
            "bronze issu d'une autre génération : make reset-bronze "
            "(ou régénère les mêmes données que celles déjà ingérées)"
        )


def prochain_id_run(cur: psycopg.Cursor[Any], jour: date) -> str:
    """Identifiant déterministe du run : « AAAA-MM-JJ#n », n = rang du run pour ce jour."""
    cur.execute("SELECT count(DISTINCT id_run) FROM bronze._ingestions WHERE jour = %s", (jour,))
    ligne = cur.fetchone()
    deja = int(ligne[0]) if ligne else 0
    return f"{jour.isoformat()}#{deja + 1}"


def lire_filigrane(cur: psycopg.Cursor[Any], table_source: str) -> datetime | None:
    """Filigrane courant d'une table de imf_ops (None : jamais extraite)."""
    cur.execute("SELECT filigrane FROM bronze._filigranes WHERE table_source = %s", (table_source,))
    ligne = cur.fetchone()
    return ligne[0] if ligne else None


def ecrire_filigrane(cur: psycopg.Cursor[Any], table_source: str, filigrane: datetime) -> None:
    """Enregistre le nouveau filigrane (dans la transaction du jour)."""
    cur.execute(
        "INSERT INTO bronze._filigranes (table_source, filigrane) VALUES (%s, %s) "
        "ON CONFLICT (table_source) DO UPDATE SET filigrane = EXCLUDED.filigrane",
        (table_source, filigrane),
    )


def enregistrer(cur: psycopg.Cursor[Any], lignes: list[LigneJournal]) -> None:
    """Ajoute les lignes du run au journal (dans la transaction du jour)."""
    colonnes = [f.name for f in fields(LigneJournal)]
    cur.executemany(
        f"INSERT INTO bronze._ingestions ({', '.join(colonnes)}) "
        f"VALUES ({', '.join(['%s'] * len(colonnes))})",
        [astuple(ligne) for ligne in lignes],
    )
