"""Tests d'intégration du chargement de imf_ops (PostgreSQL requis : make up).

Le chargement se fait dans une base jetable, imf_ops_test, pour ne pas écraser imf_ops.
"""

from collections.abc import Iterator
from dataclasses import replace

import psycopg
import pytest

from generator.__main__ import Generation
from generator.imf_ops import TABLES_IMF_OPS, ErreurConnexion, charger, connecter

pytestmark = pytest.mark.integration

BASE_TEST = "imf_ops_test"


def _administrer(requete: str) -> None:
    """Exécute une commande hors transaction (CREATE/DROP DATABASE) depuis la base postgres."""
    with connecter("postgres") as conn:
        conn.autocommit = True
        conn.execute(requete.encode())


@pytest.fixture(scope="module")
def base_test() -> Iterator[str]:
    """Crée la base jetable, puis la supprime ; échec explicite si PostgreSQL est injoignable."""
    try:
        _administrer(f"DROP DATABASE IF EXISTS {BASE_TEST}")
        _administrer(f"CREATE DATABASE {BASE_TEST}")
    except ErreurConnexion as erreur:
        pytest.fail(str(erreur), pytrace=False)
    yield BASE_TEST
    _administrer(f"DROP DATABASE IF EXISTS {BASE_TEST} WITH (FORCE)")


def _etat(conn: psycopg.Connection) -> dict[str, tuple[int, str]]:
    """Nombre de lignes et empreinte MD5 du contenu trié de chaque table."""
    etat = {}
    for table in TABLES_IMF_OPS:
        ligne = conn.execute(
            f"SELECT count(*), md5(coalesce(string_agg(t::text, '|' ORDER BY t::text), '')) "
            f"FROM {table} t".encode()
        ).fetchone()
        assert ligne is not None
        etat[table] = (ligne[0], ligne[1])
    return etat


def test_nombre_de_lignes_egal_au_manifeste(petite_generation: Generation, base_test: str) -> None:
    charger(petite_generation.brut, base_test)
    attendu = petite_generation.manifeste["lignes"]["brut"]
    with connecter(base_test) as conn:
        for table, (nombre, _) in _etat(conn).items():
            assert nombre == attendu[table], table


def test_contraintes_pk_fk(petite_generation: Generation, base_test: str) -> None:
    charger(petite_generation.brut, base_test)
    with connecter(base_test) as conn:
        lignes = conn.execute(
            "SELECT table_name, constraint_type, count(*) "
            "FROM information_schema.table_constraints WHERE table_schema = 'public' "
            "AND constraint_type IN ('PRIMARY KEY', 'FOREIGN KEY') "
            "GROUP BY table_name, constraint_type"
        ).fetchall()
        colonnes = conn.execute(
            "SELECT table_name, column_name, data_type FROM information_schema.columns "
            "WHERE table_schema = 'public'"
        ).fetchall()
    contraintes = {(t, c): n for t, c, n in lignes}
    assert all(contraintes.get((t, "PRIMARY KEY")) == 1 for t in TABLES_IMF_OPS)
    assert contraintes[("comptes", "FOREIGN KEY")] == 1
    assert contraintes[("credits", "FOREIGN KEY")] == 3
    assert contraintes[("echeancier", "FOREIGN KEY")] == 1
    assert contraintes[("remboursements", "FOREIGN KEY")] == 1
    types = {(t, c): d for t, c, d in colonnes}
    assert all((t, "date_maj") in types for t in TABLES_IMF_OPS)
    for colonne in ("montant_paye", "part_capital", "part_interets", "penalites"):
        assert types[("remboursements", colonne)] == "bigint"
    assert types[("credits", "montant_accorde")] == "bigint"
    assert types[("clients", "date_maj")] == "timestamp without time zone"


def test_deux_chargements_meme_etat(petite_generation: Generation, base_test: str) -> None:
    charger(petite_generation.brut, base_test)
    with connecter(base_test) as conn:
        premier = _etat(conn)
    charger(petite_generation.brut, base_test)
    with connecter(base_test) as conn:
        assert _etat(conn) == premier


def test_chargement_atomique(petite_generation: Generation, base_test: str) -> None:
    """Une erreur pendant le rechargement laisse la base dans son état précédent."""
    charger(petite_generation.brut, base_test)
    with connecter(base_test) as conn:
        avant = _etat(conn)
    # Remboursement vers un crédit inexistant : la clé étrangère fait échouer le COPY.
    brut = petite_generation.brut
    fautif = replace(brut.remboursements[0], id_remboursement="RMB00000000", id_credit="CRD0000000")
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        charger(replace(brut, remboursements=brut.remboursements + (fautif,)), base_test)
    with connecter(base_test) as conn:
        assert _etat(conn) == avant
