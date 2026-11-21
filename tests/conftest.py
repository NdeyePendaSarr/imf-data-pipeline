"""Configuration partagée des tests : lecture du .env et connexion à PostgreSQL."""

import os
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest
from dotenv import load_dotenv

# Racine du dépôt : le .env s'y trouve, quel que soit le dossier de lancement de pytest.
RACINE = Path(__file__).resolve().parent.parent

# Charge le .env sans écraser les variables déjà définies dans l'environnement.
load_dotenv(RACINE / ".env")


def connect(dbname: str) -> psycopg.Connection:
    """Ouvre une connexion à la base `dbname` avec les paramètres du .env.

    Échoue explicitement (jamais de skip) si le .env est incomplet ou si
    PostgreSQL est injoignable.
    """
    utilisateur = os.getenv("POSTGRES_USER")
    mot_de_passe = os.getenv("POSTGRES_PASSWORD")
    if not utilisateur or not mot_de_passe:
        pytest.fail(
            "POSTGRES_USER ou POSTGRES_PASSWORD absent : copie .env.example en .env",
            pytrace=False,
        )
    try:
        return psycopg.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=int(os.getenv("POSTGRES_PORT", "5433")),
            user=utilisateur,
            password=mot_de_passe,
            dbname=dbname,
            connect_timeout=5,
        )
    except psycopg.OperationalError as erreur:
        pytest.fail(
            f"PostgreSQL injoignable : lance `make up` (base {dbname} : {erreur})",
            pytrace=False,
        )


@pytest.fixture
def conn_dwh() -> Iterator[psycopg.Connection]:
    """Connexion à l'entrepôt imf_dwh, fermée après le test."""
    with connect("imf_dwh") as conn:
        yield conn


@pytest.fixture
def conn_ops() -> Iterator[psycopg.Connection]:
    """Connexion à la base opérationnelle imf_ops, fermée après le test."""
    with connect("imf_ops") as conn:
        yield conn
