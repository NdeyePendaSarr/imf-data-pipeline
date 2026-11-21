"""Silver nettoyé = vérité propre du générateur (décision S12).

Pour chaque table slv_* : l'ensemble des lignes (colonnes métier, hors colonnes techniques _*)
est égal à data/_verite/<table>.csv, et le nombre de lignes à celui du manifeste. La vérité est
lue en fichier, jamais chargée dans l'entrepôt : c'est un oracle de test, pas une donnée.

Prérequis : make generate, make ingest-all (bronze complet au 31/12), puis make dbt-build.
"""

import csv
import json
from collections import Counter
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import psycopg
import pytest

from tests.conftest import RACINE, connect

pytestmark = pytest.mark.integration

DATA = RACINE / "data"

# Tables silver comparées à la vérité, et renommages de colonnes (S9).
TABLES = (
    "agences",
    "ouverture",
    "operations",
    "charges",
    "appro_caisse",
    "produits_credit",
    "clients",
    "comptes",
    "credits",
    "echeancier",
    "remboursements",
)
RENOMMAGES = {"credits": {"statut": "statut_au_31_12"}}


def texte(valeur: object) -> str:
    """Valeur PostgreSQL → texte au format des CSV de la vérité."""
    if valeur is None:
        return ""
    if isinstance(valeur, datetime):
        return valeur.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(valeur, date):
        return valeur.isoformat()
    if isinstance(valeur, Decimal):
        # NUMERIC(6,4) : 0.1500 → 0.15, comme dans la vérité.
        return format(valeur.normalize(), "f")
    return str(valeur)


def lire_verite(table: str) -> tuple[list[str], list[tuple[str, ...]]]:
    """En-tête et lignes de data/_verite/<table>.csv."""
    chemin = DATA / "_verite" / f"{table}.csv"
    if not chemin.exists():
        pytest.fail(f"{chemin} introuvable : lance `make generate`", pytrace=False)
    with chemin.open(encoding="utf-8", newline="") as fichier:
        lecteur = csv.reader(fichier)
        entete = next(lecteur)
        return entete, [tuple(ligne) for ligne in lecteur]


def lire_silver(table: str, colonnes: list[str]) -> list[tuple[str, ...]]:
    """Lignes de silver.slv_<table>, colonnes métier dans l'ordre de la vérité."""
    renommage = RENOMMAGES.get(table, {})
    liste = ", ".join(renommage.get(c, c) for c in colonnes)
    try:
        with connect("imf_dwh") as conn:
            lignes = conn.execute(f"SELECT {liste} FROM silver.slv_{table}".encode()).fetchall()
    except psycopg.errors.UndefinedTable:
        pytest.fail(
            f"silver.slv_{table} absente : lance `make ingest-all` puis `make dbt-build`",
            pytrace=False,
        )
    return [tuple(texte(v) for v in ligne) for ligne in lignes]


def ids_acceptes_null() -> set[str]:
    """Clients du catalogue ACCEPTER_NULL : leur NULL est attendu en silver."""
    with (DATA / "catalogue_anomalies.csv").open(encoding="utf-8", newline="") as fichier:
        return {
            ligne["id_ligne"]
            for ligne in csv.DictReader(fichier)
            if ligne["traitement_attendu"] == "ACCEPTER_NULL"
        }


@pytest.mark.parametrize("table", TABLES)
def test_silver_egal_verite(table: str) -> None:
    colonnes, verite = lire_verite(table)
    silver = lire_silver(table, colonnes)
    manifeste = json.loads((DATA / "_manifest.json").read_text(encoding="utf-8"))

    # Même nombre de lignes que la vérité du manifeste.
    assert len(silver) == manifeste["lignes"]["verite"][table]
    assert len(verite) == manifeste["lignes"]["verite"][table]

    if table == "clients":
        # ACCEPTER_NULL : le silver garde le NULL du brut là où la vérité a une valeur ; on
        # complète ces champs depuis la vérité, pour ces seuls clients, avant de comparer.
        nulls = ids_acceptes_null()
        assert nulls, "le catalogue doit contenir des NULL acceptés"
        par_id = {ligne[0]: ligne for ligne in verite}
        completees = []
        for ligne in silver:
            if ligne[0] in nulls:
                assert "" in ligne, ligne  # le NULL accepté est bien présent en silver
                ligne = tuple(v or par_id[ligne[0]][i] for i, v in enumerate(ligne))
            completees.append(ligne)
        silver = completees

    # Même ensemble de lignes (multiensemble : un doublon restant serait détecté).
    manquantes = Counter(verite) - Counter(silver)
    en_trop = Counter(silver) - Counter(verite)
    assert not manquantes and not en_trop, (
        f"{table} : {sum(manquantes.values())} ligne(s) de la vérité absentes du silver, "
        f"{sum(en_trop.values())} ligne(s) du silver absentes de la vérité ; "
        f"exemples {list(manquantes)[:2]} / {list(en_trop)[:2]}"
    )


def test_verite_non_chargee_dans_l_entrepot() -> None:
    """La vérité reste un fichier : aucune table de l'entrepôt ne s'appelle *verite*."""
    with connect("imf_dwh") as conn:
        tables = conn.execute(
            "SELECT table_schema || '.' || table_name FROM information_schema.tables "
            "WHERE table_name ILIKE '%verite%'"
        ).fetchall()
    assert tables == []


def test_dossier_data_present() -> None:
    assert Path(DATA / "_manifest.json").exists(), "lance `make generate`"
