"""Copie du bronze PostgreSQL vers BigQuery (phase 9, cadrage v0.7 : L1, L2, L5).

Pour chacune des 15 tables (14 du schéma bronze + audit.audit_runs) :
1. lecture dans PostgreSQL (variables POSTGRES_*, comme l'ingestion) ;
2. écriture d'un Parquet dans data/bq/ (gitignoré), typé par Arrow ;
3. chargement dans le dataset BigQuery du même nom (`bronze`, `audit`) par un load job
   WRITE_TRUNCATE, avec un schéma explicite (jamais d'autodétection) ;
4. contrôle : lignes BigQuery = lignes PostgreSQL, sinon erreur.

Les types BigQuery viennent d'UNE table de correspondance (`CORRESPONDANCE`), reprise de
docs/phase9/inventaire_bq.md. `timestamp without time zone` (date_maj, filigranes) devient
DATETIME, pas TIMESTAMP : c'est une heure locale (date de l'événement à 20:00), pas un instant.

Projet et région lus dans l'environnement : BQ_PROJECT, BQ_LOCATION (L5 : région fixe, jamais
changée ; un dataset existant dans une autre région fait échouer le chargement).

    python -m ingestion.charger_bq                 # make load-bq : 15 tables
    python -m ingestion.charger_bq --sans-audit    # make load-bq SANS_AUDIT=1 : 14 (CI, L15)
"""

import argparse
import os
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psycopg
import pyarrow as pa
import pyarrow.parquet as pq
from dotenv import load_dotenv
from google.api_core.exceptions import GoogleAPIError
from google.cloud import bigquery

from ingestion.config import ErreurIngestion, parametres_connexion

DOSSIER_PARQUET = Path("data/bq")

# Tables copiées, dans l'ordre de chargement : (schéma PostgreSQL = dataset BigQuery, table).
TABLES: tuple[tuple[str, str], ...] = (
    ("bronze", "_filigranes"),
    ("bronze", "_ingestions"),
    ("bronze", "csv_agences"),
    ("bronze", "csv_appro_caisse"),
    ("bronze", "csv_charges"),
    ("bronze", "csv_operations"),
    ("bronze", "csv_ouverture"),
    ("bronze", "meta_catalogue_anomalies"),
    ("bronze", "ops_clients"),
    ("bronze", "ops_comptes"),
    ("bronze", "ops_credits"),
    ("bronze", "ops_echeancier"),
    ("bronze", "ops_produits_credit"),
    ("bronze", "ops_remboursements"),
    ("audit", "audit_runs"),
)
DATASETS: tuple[str, ...] = tuple(dict.fromkeys(schema for schema, _ in TABLES))
# Journal d'exécution d'Airflow : absent du PostgreSQL éphémère de la CI (L15, --sans-audit).
SCHEMA_AUDIT = "audit"


@dataclass(frozen=True)
class Colonne:
    """Colonne PostgreSQL, telle que la décrit information_schema.columns."""

    nom: str
    type_pg: str  # data_type : « text », « numeric », « ARRAY », …
    type_element: str = ""  # udt_name sans le « _ » initial pour un tableau (« text »)
    precision: int | None = None
    echelle: int | None = None


def _decimal(colonne: Colonne) -> pa.DataType:
    if colonne.precision is None or colonne.echelle is None:
        raise ErreurIngestion(f"numeric sans précision ni échelle : {colonne.nom}")
    return pa.decimal128(colonne.precision, colonne.echelle)


# Table de correspondance UNIQUE : type PostgreSQL → (type BigQuery, type Arrow du Parquet).
CORRESPONDANCE: dict[str, tuple[str, Callable[[Colonne], pa.DataType]]] = {
    "text": ("STRING", lambda _: pa.string()),
    "character varying": ("STRING", lambda _: pa.string()),
    "character": ("STRING", lambda _: pa.string()),
    "bigint": ("INT64", lambda _: pa.int64()),
    "integer": ("INT64", lambda _: pa.int64()),
    "smallint": ("INT64", lambda _: pa.int64()),
    "numeric": ("NUMERIC", _decimal),
    "date": ("DATE", lambda _: pa.date32()),
    "boolean": ("BOOL", lambda _: pa.bool_()),
    "timestamp with time zone": ("TIMESTAMP", lambda _: pa.timestamp("us", tz="UTC")),
    # Heure locale sans fuseau (date_maj, filigranes) : DATETIME en BigQuery, horodatage Arrow
    # sans fuseau dans le Parquet.
    "timestamp without time zone": ("DATETIME", lambda _: pa.timestamp("us")),
}


def _type(colonne: Colonne) -> tuple[str, pa.DataType]:
    """Type BigQuery et type Arrow d'une colonne scalaire (élément d'un tableau compris)."""
    type_pg = colonne.type_element if colonne.type_pg == "ARRAY" else colonne.type_pg
    if type_pg not in CORRESPONDANCE:
        raise ErreurIngestion(
            f"type PostgreSQL sans correspondance BigQuery : {colonne.nom} {type_pg}"
        )
    type_bq, arrow = CORRESPONDANCE[type_pg]
    return type_bq, arrow(colonne)


def champ_bq(colonne: Colonne) -> bigquery.SchemaField:
    """Champ BigQuery explicite : tableau → REPEATED, sinon NULLABLE (bronze sans contrainte)."""
    type_bq, _ = _type(colonne)
    mode = "REPEATED" if colonne.type_pg == "ARRAY" else "NULLABLE"
    if type_bq == "NUMERIC" and colonne.precision is not None and colonne.echelle is not None:
        return bigquery.SchemaField(
            colonne.nom, type_bq, mode=mode, precision=colonne.precision, scale=colonne.echelle
        )
    return bigquery.SchemaField(colonne.nom, type_bq, mode=mode)


def schema_arrow(colonnes: list[Colonne]) -> pa.Schema:
    """Schéma Arrow du Parquet, aligné sur le schéma BigQuery."""
    champs = []
    for colonne in colonnes:
        _, arrow = _type(colonne)
        champs.append(
            pa.field(colonne.nom, pa.list_(arrow) if colonne.type_pg == "ARRAY" else arrow)
        )
    return pa.schema(champs)


def config_chargement(colonnes: list[Colonne]) -> bigquery.LoadJobConfig:
    """Load job Parquet : schéma explicite, WRITE_TRUNCATE, listes Parquet lues comme REPEATED."""
    options = bigquery.ParquetOptions()  # type: ignore[no-untyped-call]
    options.enable_list_inference = True
    config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.PARQUET,
        schema=[champ_bq(c) for c in colonnes],
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        autodetect=False,
    )
    config.parquet_options = options
    return config


def tables_a_charger(sans_audit: bool) -> tuple[tuple[str, str], ...]:
    """Les 15 tables, ou les 14 du bronze avec --sans-audit (L15 : la CI n'a pas d'audit)."""
    return tuple(t for t in TABLES if not (sans_audit and t[0] == SCHEMA_AUDIT))


def creer_datasets(
    client: bigquery.Client, projet: str, region: str, datasets: tuple[str, ...] = DATASETS
) -> None:
    """Crée les datasets dans la région demandée ; un dataset existant ailleurs : erreur (L5)."""
    for nom in datasets:
        dataset = bigquery.Dataset(f"{projet}.{nom}")
        dataset.location = region
        obtenu = client.create_dataset(dataset, exists_ok=True)
        if (obtenu.location or "").upper() != region.upper():
            raise ErreurIngestion(
                f"dataset {projet}.{nom} en {obtenu.location}, attendu {region} : "
                "la région d'un dataset ne change pas (L5), supprimer le dataset à la main"
            )


def colonnes_pg(conn: psycopg.Connection[Any], schema: str, table: str) -> list[Colonne]:
    lignes = conn.execute(
        "SELECT column_name, data_type, ltrim(udt_name, '_'), numeric_precision, numeric_scale "
        "FROM information_schema.columns WHERE table_schema = %s AND table_name = %s "
        "ORDER BY ordinal_position",
        (schema, table),
    ).fetchall()
    if not lignes:
        raise ErreurIngestion(f"table PostgreSQL introuvable : {schema}.{table}")
    return [
        Colonne(nom, type_pg, element if type_pg == "ARRAY" else "", precision, echelle)
        for nom, type_pg, element, precision, echelle in lignes
    ]


def ecrire_parquet(
    conn: psycopg.Connection[Any], schema: str, table: str, colonnes: list[Colonne], dossier: Path
) -> tuple[Path, int]:
    """Lit toute la table et l'écrit en Parquet ; renvoie le fichier et le nombre de lignes."""
    noms = ", ".join(f'"{c.nom}"' for c in colonnes)
    lignes = conn.execute(f'SELECT {noms} FROM "{schema}"."{table}"'.encode()).fetchall()
    schema_pa = schema_arrow(colonnes)
    tableau = pa.table(
        {c.nom: pa.array([ligne[i] for ligne in lignes], type=schema_pa.field(c.nom).type)
         for i, c in enumerate(colonnes)},
        schema=schema_pa,
    )  # fmt: skip
    dossier.mkdir(parents=True, exist_ok=True)
    fichier = dossier / f"{schema}.{table}.parquet"
    pq.write_table(tableau, fichier)
    return fichier, len(lignes)


def charger_table(
    client: bigquery.Client,
    destination: str,
    fichier: Path,
    colonnes: list[Colonne],
    nb_attendu: int,
) -> int:
    """Charge un Parquet (WRITE_TRUNCATE) puis vérifie le nombre de lignes de la table BigQuery."""
    with fichier.open("rb") as flux:
        job = client.load_table_from_file(flux, destination, job_config=config_chargement(colonnes))
    job.result()
    nb_bq = client.get_table(destination).num_rows
    if nb_bq != nb_attendu:
        raise ErreurIngestion(
            f"{destination} : {nb_bq} lignes dans BigQuery, {nb_attendu} dans PostgreSQL"
        )
    return int(nb_bq)


def charger(
    client: bigquery.Client,
    projet: str,
    region: str,
    conn: psycopg.Connection[Any],
    sans_audit: bool = False,
) -> list[tuple[str, int, int, float]]:
    """Copie les tables ; renvoie (table, lignes PostgreSQL, lignes BigQuery, secondes).

    sans_audit : audit.audit_runs n'est ni lu ni chargé, et le dataset audit de BigQuery n'est
    ni créé ni modifié (il garde la copie chargée depuis le poste). Sans l'option, une table
    absente de PostgreSQL reste une erreur.
    """
    tables = tables_a_charger(sans_audit)
    creer_datasets(client, projet, region, tuple(dict.fromkeys(s for s, _ in tables)))
    bilan = []
    for schema, table in tables:
        debut = time.monotonic()
        colonnes = colonnes_pg(conn, schema, table)
        fichier, nb_pg = ecrire_parquet(conn, schema, table, colonnes, DOSSIER_PARQUET)
        nb_bq = charger_table(client, f"{projet}.{schema}.{table}", fichier, colonnes, nb_pg)
        bilan.append((f"{schema}.{table}", nb_pg, nb_bq, time.monotonic() - debut))
    return bilan


def main(arguments: list[str] | None = None) -> int:
    parseur = argparse.ArgumentParser(prog="python -m ingestion.charger_bq")
    parseur.add_argument(
        "--sans-audit",
        action="store_true",
        help="n'exclut que audit.audit_runs : le dataset audit de BigQuery n'est pas modifié "
        "(CI : pas d'audit dans le PostgreSQL éphémère)",
    )
    sans_audit = parseur.parse_args(arguments).sans_audit
    load_dotenv()
    projet, region = os.getenv("BQ_PROJECT", ""), os.getenv("BQ_LOCATION", "")
    if not projet or not region:
        print("Erreur : BQ_PROJECT et BQ_LOCATION doivent être renseignés (.env)", file=sys.stderr)
        return 2
    debut = time.monotonic()
    try:
        client = bigquery.Client(project=projet, location=region)
        with psycopg.connect(
            **parametres_connexion(os.getenv("POSTGRES_DB_DWH", "imf_dwh"))
        ) as conn:
            bilan = charger(client, projet, region, conn, sans_audit=sans_audit)
    except (ErreurIngestion, GoogleAPIError) as erreur:
        # Un load job refusé (schéma, type) lève une GoogleAPIError : message tel quel, sans
        # contournement.
        print(f"Erreur : {erreur}", file=sys.stderr)
        return 1
    for table, nb_pg, nb_bq, secondes in bilan:
        print(f"{table:35} PostgreSQL {nb_pg:>7}  BigQuery {nb_bq:>7}  {secondes:5.1f} s")
    print(f"{len(bilan)} tables chargées en {time.monotonic() - debut:.1f} s, région {region}")
    if sans_audit:
        print(
            f"--sans-audit : {SCHEMA_AUDIT}.audit_runs exclu ; dataset {SCHEMA_AUDIT} de BigQuery "
            "non modifié (copie chargée depuis le poste)"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
