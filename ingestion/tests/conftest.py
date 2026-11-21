"""Fixtures des tests d'ingestion : petite génération et bases jetables.

Les tests d'intégration n'utilisent jamais imf_ops ni imf_dwh : chaque environnement crée
ses propres bases (imf_ops_<nom>, imf_dwh_<nom>) et sa copie du dossier data/.
"""

import shutil
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import psycopg
import pytest
from dotenv import load_dotenv
from psycopg import sql

from generator.__main__ import Generation, generer
from generator.config import Config
from generator.imf_ops import charger as charger_imf_ops
from ingestion.__main__ import connecter, ingerer
from ingestion.config import ErreurIngestion, Parametres, parametres_connexion
from ingestion.journal import LigneJournal

RACINE = Path(__file__).resolve().parents[2]
load_dotenv(RACINE / ".env")

TABLES_BRONZE = (
    "csv_agences",
    "csv_ouverture",
    "csv_operations",
    "csv_charges",
    "csv_appro_caisse",
    "meta_catalogue_anomalies",
    "ops_produits_credit",
    "ops_clients",
    "ops_comptes",
    "ops_credits",
    "ops_echeancier",
    "ops_remboursements",
)


def _administrer(requete: sql.Composed) -> None:
    """CREATE/DROP DATABASE depuis la base postgres (hors transaction)."""
    try:
        with connecter("postgres") as conn:
            conn.autocommit = True
            conn.execute(requete)
    except ErreurIngestion as erreur:
        pytest.fail(str(erreur), pytrace=False)


def recreer_base(nom: str) -> None:
    _administrer(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(nom)))
    _administrer(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(nom)))


def supprimer_base(nom: str) -> None:
    _administrer(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(nom)))


@dataclass(frozen=True)
class Environnement:
    """Une copie de data/, une base imf_ops chargée et un entrepôt vide."""

    generation: Generation
    parametres: Parametres

    @property
    def source(self) -> Path:
        return self.parametres.source

    def ingerer(self, jours: Sequence[date]) -> list[LigneJournal]:
        return ingerer(jours, self.parametres)

    def requete(self, requete: str, params: Sequence[Any] = ()) -> list[tuple[Any, ...]]:
        """Exécute une requête de lecture sur l'entrepôt."""
        with psycopg.connect(**parametres_connexion(self.parametres.base_dwh)) as conn:
            return conn.execute(requete.encode(), params).fetchall()

    def executer_ops(self, requete: str, params: Sequence[Any] = ()) -> None:
        """Modifie la base imf_ops de l'environnement (simulation d'un changement source)."""
        with psycopg.connect(**parametres_connexion(self.parametres.base_ops)) as conn:
            conn.execute(requete.encode(), params)

    def compter(self, table: str) -> int:
        return int(self.requete(f"SELECT count(*) FROM bronze.{table}")[0][0])

    def etat(self) -> dict[str, Any]:
        """Photographie de bronze : contenu des tables (hors _charge_le), filigranes, journal."""
        existe = self.requete("SELECT count(*) FROM pg_tables WHERE schemaname = 'bronze'")[0][0]
        if not existe:
            return {}
        photo: dict[str, Any] = {}
        for table in TABLES_BRONZE:
            photo[table] = self.requete(
                f"SELECT md5(coalesce(string_agg((t)::text, '|' ORDER BY (t)::text), '')), "
                f"count(*) FROM (SELECT * FROM bronze.{table}) t"
            )[0]
        photo["_filigranes"] = self.requete("SELECT * FROM bronze._filigranes ORDER BY 1")
        photo["_ingestions"] = self.requete(
            "SELECT id_run, objet, statut, nb_lignes FROM bronze._ingestions ORDER BY 1, 2"
        )
        return photo


@pytest.fixture(scope="session")
def generation_petite(tmp_path_factory: pytest.TempPathFactory) -> Generation:
    """Petite génération (100 clients, 150 crédits), sans base de données."""
    sortie = tmp_path_factory.mktemp("generation") / "data"
    return generer(Config(nb_clients=100, nb_credits=150, sortie=sortie))


def creer_environnement(generation: Generation, nom: str, dossier: Path) -> Environnement:
    """Copie data/, recrée imf_ops_<nom> (chargée) et imf_dwh_<nom> (vide)."""
    source = dossier / "data"
    shutil.copytree(generation.config.sortie, source)
    base_ops, base_dwh = f"imf_ops_{nom}", f"imf_dwh_{nom}"
    recreer_base(base_ops)
    recreer_base(base_dwh)
    charger_imf_ops(generation.brut, base_ops)
    return Environnement(generation, Parametres(source, base_ops, base_dwh))


@pytest.fixture
def env(generation_petite: Generation, tmp_path: Path) -> Iterator[Environnement]:
    """Environnement neuf pour un test d'intégration."""
    environnement = creer_environnement(generation_petite, "test_ing", tmp_path)
    yield environnement
    supprimer_base(environnement.parametres.base_ops)
    supprimer_base(environnement.parametres.base_dwh)
