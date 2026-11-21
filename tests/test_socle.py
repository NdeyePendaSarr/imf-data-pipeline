"""Tests d'intégration du socle : bases, schémas et version de PostgreSQL."""

import psycopg
import pytest

# Tous les tests de ce module nécessitent le conteneur PostgreSQL démarré.
pytestmark = pytest.mark.integration

# Couches du modèle médaillon attendues dans l'entrepôt.
SCHEMAS_ATTENDUS: set[str] = {"bronze", "silver", "gold"}


def test_connexion_imf_dwh(conn_dwh: psycopg.Connection) -> None:
    """La connexion à l'entrepôt aboutit sur la bonne base."""
    ligne = conn_dwh.execute("SELECT current_database()").fetchone()
    assert ligne is not None
    assert ligne[0] == "imf_dwh"


def test_schemas_medaillon_presents(conn_dwh: psycopg.Connection) -> None:
    """Les schémas bronze, silver et gold existent dans imf_dwh."""
    lignes = conn_dwh.execute(
        "SELECT schema_name FROM information_schema.schemata WHERE schema_name = ANY(%s)",
        (list(SCHEMAS_ATTENDUS),),
    ).fetchall()
    presents = {ligne[0] for ligne in lignes}
    assert presents == SCHEMAS_ATTENDUS, f"schémas manquants : {SCHEMAS_ATTENDUS - presents}"


def test_connexion_imf_ops(conn_ops: psycopg.Connection) -> None:
    """La base opérationnelle simulée imf_ops existe et accepte les connexions."""
    ligne = conn_ops.execute("SELECT current_database()").fetchone()
    assert ligne is not None
    assert ligne[0] == "imf_ops"


def test_version_serveur_au_moins_17(conn_dwh: psycopg.Connection) -> None:
    """Le serveur est en PostgreSQL 17 ou plus récent."""
    # server_version est encodé en entier : 170002 pour la 17.2.
    version = conn_dwh.info.server_version
    assert version >= 170000, f"PostgreSQL {version // 10000} détecté, 17 minimum attendu"
