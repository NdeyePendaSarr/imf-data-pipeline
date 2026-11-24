"""Chargeur BigQuery (phase 9) sans réseau ni identifiants : client BigQuery simulé.

Tournent dans la CI : aucun appel à Google, aucune base PostgreSQL.
"""

import datetime as dt
from decimal import Decimal
from pathlib import Path
from typing import Any

import psycopg
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from google.cloud import bigquery

from ingestion import charger_bq
from ingestion.charger_bq import (
    CORRESPONDANCE,
    DATASETS,
    TABLES,
    Colonne,
    champ_bq,
    charger,
    charger_table,
    config_chargement,
    creer_datasets,
    schema_arrow,
)
from ingestion.config import ErreurIngestion

PROJET = "projet-test"

# Colonnes représentatives de l'inventaire (docs/phase9/inventaire_bq.md).
COLONNES = [
    Colonne("id_credit", "character varying"),
    Colonne("montant_accorde", "bigint"),
    Colonne("duree_mois", "smallint"),
    Colonne("taux_annuel", "numeric", precision=6, echelle=4),
    Colonne("date_decaissement", "date"),
    Colonne("date_maj", "timestamp without time zone"),
    Colonne("_charge_le", "timestamp with time zone"),
    Colonne("noeuds_en_echec", "ARRAY", type_element="text"),
]


class JobSimule:
    def result(self) -> None:
        return None


class TableSimulee:
    def __init__(self, num_rows: int) -> None:
        self.num_rows = num_rows


class ClientSimule:
    """Enregistre les appels ; `region_existante` simule un dataset déjà créé ailleurs."""

    def __init__(self, lignes_bq: int = 0, region_existante: str | None = None) -> None:
        self.lignes_bq = lignes_bq
        self.region_existante = region_existante
        self.datasets: list[bigquery.Dataset] = []
        self.chargements: list[tuple[str, bigquery.LoadJobConfig]] = []

    def create_dataset(self, dataset: bigquery.Dataset, exists_ok: bool = False) -> Any:
        assert exists_ok, "les datasets doivent être créés avec exists_ok=True"
        self.datasets.append(dataset)
        if self.region_existante is not None:
            existant = bigquery.Dataset(dataset.reference)
            existant.location = self.region_existante
            return existant
        return dataset

    def load_table_from_file(self, flux: Any, destination: str, job_config: Any) -> JobSimule:
        assert flux.read(4) == b"PAR1", "le fichier chargé doit être un Parquet"
        self.chargements.append((destination, job_config))
        return JobSimule()

    def get_table(self, destination: str) -> TableSimulee:
        return TableSimulee(self.lignes_bq)


def _client(**kwargs: Any) -> bigquery.Client:
    client: Any = ClientSimule(**kwargs)
    return client  # type: ignore[no-any-return]


def test_quinze_tables_deux_datasets() -> None:
    assert len(TABLES) == 15
    assert DATASETS == ("bronze", "audit")


def test_location_passee_a_la_creation_des_datasets() -> None:
    client = _client()
    creer_datasets(client, PROJET, "EU")
    datasets = client.datasets  # type: ignore[attr-defined]
    assert [d.dataset_id for d in datasets] == ["bronze", "audit"]
    assert all(d.location == "EU" for d in datasets)
    assert all(d.project == PROJET for d in datasets)


def test_dataset_existant_dans_une_autre_region_echoue() -> None:
    """L5 : la région ne change jamais ; un dataset déjà en US fait échouer, sans le toucher."""
    with pytest.raises(ErreurIngestion, match="en US, attendu EU"):
        creer_datasets(_client(region_existante="US"), PROJET, "EU")


def test_schema_explicite_et_write_truncate() -> None:
    config = config_chargement(COLONNES)
    assert config.source_format == bigquery.SourceFormat.PARQUET
    assert config.write_disposition == bigquery.WriteDisposition.WRITE_TRUNCATE
    assert config.autodetect is False
    assert config.schema is not None
    assert [(c.name, c.field_type, c.mode) for c in config.schema] == [
        ("id_credit", "STRING", "NULLABLE"),
        ("montant_accorde", "INT64", "NULLABLE"),
        ("duree_mois", "INT64", "NULLABLE"),
        ("taux_annuel", "NUMERIC", "NULLABLE"),
        ("date_decaissement", "DATE", "NULLABLE"),
        ("date_maj", "DATETIME", "NULLABLE"),
        ("_charge_le", "TIMESTAMP", "NULLABLE"),
        ("noeuds_en_echec", "STRING", "REPEATED"),
    ]
    taux = config.schema[3]
    assert (taux.precision, taux.scale) == (6, 4)
    assert config.parquet_options.enable_list_inference is True


def test_date_maj_en_datetime_pas_en_timestamp() -> None:
    """timestamp sans fuseau (date_maj) → DATETIME en BigQuery, sans fuseau dans le Parquet."""
    date_maj = Colonne("date_maj", "timestamp without time zone")
    assert champ_bq(date_maj).field_type == "DATETIME"
    assert schema_arrow([date_maj]).field("date_maj").type == pa.timestamp("us")
    charge_le = Colonne("_charge_le", "timestamp with time zone")
    assert champ_bq(charge_le).field_type == "TIMESTAMP"
    assert schema_arrow([charge_le]).field("_charge_le").type.tz == "UTC"


def test_types_de_l_inventaire_tous_couverts() -> None:
    """Types de l'inventaire tous couverts ; un type inconnu fait échouer."""
    for type_pg in (
        "text",
        "character varying",
        "character",
        "bigint",
        "integer",
        "smallint",
        "numeric",
        "date",
        "timestamp with time zone",
        "timestamp without time zone",
    ):
        assert type_pg in CORRESPONDANCE
    with pytest.raises(ErreurIngestion, match="sans correspondance"):
        champ_bq(Colonne("x", "jsonb"))  # fmt: skip


def _parquet(tmp_path: Path) -> Path:
    schema = schema_arrow(COLONNES)
    lignes = [
        ["CRD1", 345000, 9, Decimal("0.1400"), dt.date(2025, 5, 10),
         dt.datetime(2025, 5, 10, 20, 0), dt.datetime(2025, 5, 11, tzinfo=dt.UTC), ["a", "b"]],
    ]  # fmt: skip
    tableau = pa.table(
        {c.nom: pa.array([ligne[i] for ligne in lignes], type=schema.field(c.nom).type)
         for i, c in enumerate(COLONNES)},
        schema=schema,
    )  # fmt: skip
    fichier = tmp_path / "bronze.ops_credits.parquet"
    pq.write_table(tableau, fichier)
    return fichier


def test_parquet_ecrit_avec_les_types_attendus(tmp_path: Path) -> None:
    lu = pq.read_schema(_parquet(tmp_path))
    assert lu.field("date_maj").type == pa.timestamp("us")
    assert lu.field("taux_annuel").type == pa.decimal128(6, 4)
    assert lu.field("noeuds_en_echec").type == pa.list_(pa.string())


def test_chargement_nombre_de_lignes_egal(tmp_path: Path) -> None:
    client = _client(lignes_bq=1)
    destination = f"{PROJET}.bronze.ops_credits"
    assert charger_table(client, destination, _parquet(tmp_path), COLONNES, nb_attendu=1) == 1
    ((dest, config),) = client.chargements  # type: ignore[attr-defined]
    assert dest == destination
    assert config.write_disposition == bigquery.WriteDisposition.WRITE_TRUNCATE


def test_ecart_de_lignes_fait_echouer(tmp_path: Path) -> None:
    with pytest.raises(ErreurIngestion, match="0 lignes dans BigQuery, 1 dans PostgreSQL"):
        charger_table(_client(lignes_bq=0), f"{PROJET}.bronze.x", _parquet(tmp_path), COLONNES, 1)


class ConnexionSansAudit:
    """PostgreSQL éphémère de la CI : les 14 tables du bronze, pas de audit.audit_runs."""

    def __init__(self) -> None:
        self.lignes: list[tuple[Any, ...]] = []

    def execute(self, requete: Any, parametres: tuple[str, str] | None = None) -> Any:
        schema = parametres[0] if parametres else None
        # information_schema.columns : une colonne pour le bronze, rien pour le schéma audit.
        self.lignes = [] if schema == "audit" else [("id", "text", "text", None, None)]
        return self

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self.lignes


def _charger(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sans_audit: bool) -> Any:
    """charger() avec la vraie lecture du catalogue ; Parquet écrit dans tmp_path (1 ligne)."""

    def ecrire(conn: Any, schema: str, table: str, colonnes: Any, dossier: Path) -> Any:
        fichier = tmp_path / f"{schema}.{table}.parquet"
        pq.write_table(pa.table({"id": pa.array(["x"], type=pa.string())}), fichier)
        return fichier, 1

    monkeypatch.setattr(charger_bq, "ecrire_parquet", ecrire)
    client = _client(lignes_bq=1)
    bilan = charger(client, PROJET, "EU", ConnexionSansAudit(), sans_audit=sans_audit)  # type: ignore[arg-type]
    return client, bilan


def test_sans_audit_14_tables_et_dataset_audit_intouche(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """L15 : --sans-audit charge les 14 tables du bronze, sans aucun appel sur le dataset audit."""
    client, bilan = _charger(tmp_path, monkeypatch, sans_audit=True)
    assert len(bilan) == 14
    assert all(table.startswith("bronze.") for table, *_ in bilan)
    destinations = [dest for dest, _ in client.chargements]
    assert len(destinations) == 14
    assert not [d for d in destinations if ".audit." in d]
    assert [d.dataset_id for d in client.datasets] == ["bronze"]


def test_sans_option_table_audit_absente_echoue(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sans l'option, comportement inchangé : audit.audit_runs absente de PostgreSQL = erreur."""
    with pytest.raises(ErreurIngestion, match="table PostgreSQL introuvable : audit.audit_runs"):
        _charger(tmp_path, monkeypatch, sans_audit=False)


def test_option_sans_audit_en_ligne_de_commande(monkeypatch: pytest.MonkeyPatch) -> None:
    """--sans-audit est une option explicite, désactivée par défaut."""
    recu: list[bool] = []

    def charger_simule(*args: Any, sans_audit: bool = False) -> list[Any]:
        recu.append(sans_audit)
        return []

    class ConnexionVide:
        def __enter__(self) -> "ConnexionVide":
            return self

        def __exit__(self, *exc: object) -> None:
            return None

    monkeypatch.setattr(charger_bq, "load_dotenv", lambda: None)
    monkeypatch.setenv("BQ_PROJECT", PROJET)
    monkeypatch.setenv("BQ_LOCATION", "EU")
    monkeypatch.setenv("POSTGRES_USER", "u")
    monkeypatch.setenv("POSTGRES_PASSWORD", "p")
    monkeypatch.setattr(bigquery, "Client", lambda **kwargs: object())
    monkeypatch.setattr(psycopg, "connect", lambda **kwargs: ConnexionVide())
    monkeypatch.setattr(charger_bq, "charger", charger_simule)
    assert charger_bq.main(["--sans-audit"]) == 0
    assert charger_bq.main([]) == 0
    assert recu == [True, False]


def test_main_sans_projet_ni_region(monkeypatch: pytest.MonkeyPatch) -> None:
    """Rien en dur : sans BQ_PROJECT / BQ_LOCATION, arrêt avant tout appel."""
    monkeypatch.setattr(charger_bq, "load_dotenv", lambda: None)
    monkeypatch.delenv("BQ_PROJECT", raising=False)
    monkeypatch.delenv("BQ_LOCATION", raising=False)
    assert charger_bq.main([]) == 2
