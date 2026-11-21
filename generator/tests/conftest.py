"""Fixtures partagées des tests du générateur."""

import csv
from pathlib import Path

import pytest
from dotenv import load_dotenv

from generator.__main__ import Generation, generer
from generator.config import Config

RACINE = Path(__file__).resolve().parents[2]
SEEDS = RACINE / "dbt" / "seeds"

# Le .env sert aux tests d'intégration (connexion à PostgreSQL).
load_dotenv(RACINE / ".env")


def petite_config(sortie: Path, seed: int = 42, taux_anomalies: float = 0.01) -> Config:
    """Petite configuration des tests rapides : 100 clients, 150 crédits."""
    return Config(
        nb_clients=100, nb_credits=150, seed=seed, taux_anomalies=taux_anomalies, sortie=sortie
    )


def lire_csv(chemin: Path) -> list[dict[str, str]]:
    """Lit un CSV en liste de dictionnaires (valeurs texte)."""
    with chemin.open(encoding="utf-8", newline="") as fichier:
        return list(csv.DictReader(fichier))


@pytest.fixture(scope="session")
def petite_generation(tmp_path_factory: pytest.TempPathFactory) -> Generation:
    """Génération sur la petite configuration, sans base de données."""
    sortie = tmp_path_factory.mktemp("petite") / "data"
    return generer(petite_config(sortie))


@pytest.fixture(scope="session")
def generation_defaut(tmp_path_factory: pytest.TempPathFactory) -> Generation:
    """Génération sur la configuration par défaut (tests « slow » uniquement)."""
    return generer(Config(sortie=tmp_path_factory.mktemp("defaut") / "data"))
