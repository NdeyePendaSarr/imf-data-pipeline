"""Gold = vérité du générateur au 31/12 (PAR 30 et soldes des comptes).

La vérité est lue en fichier (data/_verite/), jamais chargée dans l'entrepôt.
Prérequis : make generate, make ingest-all, puis make dbt-build.
"""

import csv
from collections import defaultdict
from pathlib import Path

import psycopg
import pytest

from tests.conftest import RACINE, connect

pytestmark = pytest.mark.integration

VERITE = RACINE / "data" / "_verite"


def lire(table: str) -> list[dict[str, str]]:
    chemin = VERITE / f"{table}.csv"
    if not chemin.exists():
        pytest.fail(f"{chemin} introuvable : lance `make generate`", pytrace=False)
    with chemin.open(encoding="utf-8", newline="") as fichier:
        return list(csv.DictReader(fichier))


def requete(sql: str) -> list[tuple[object, ...]]:
    try:
        with connect("imf_dwh") as conn:
            return conn.execute(sql.encode()).fetchall()
    except psycopg.errors.UndefinedTable:
        pytest.fail("gold absent : lance `make ingest-all` puis `make dbt-build`", pytrace=False)


def test_par30_au_31_12_egal_verite() -> None:
    """Σ encours et encours à plus de 30 jours au 31/12 = data/_verite/par30.csv, au franc près."""
    (attendu,) = lire("par30")
    (ligne,) = requete(
        "SELECT sum(encours), sum(encours) FILTER (WHERE jours_retard > 30), max(date) "
        "FROM gold.fct_portefeuille_quotidien "
        "WHERE date = (SELECT max(date) FROM gold.dim_date WHERE dans_exercice)"
    )
    total, a_risque, jour = ligne
    assert str(jour) == attendu["date_arrete"]
    assert (a_risque, total) == (int(attendu["encours_par30"]), int(attendu["encours_total"]))


def soldes_verite() -> dict[str, int]:
    """Soldes au 31/12 recalculés depuis les tables de la vérité (oracle indépendant de dbt)."""
    soldes: dict[str, int] = defaultdict(int)
    for c in lire("comptes"):
        soldes[c["id_compte"]] += 0
    for o in lire("operations"):
        signe = 1 if o["type_operation"] == "DEPOT" else -1
        soldes[o["id_compte"]] += signe * int(o["montant"])
    compte_credit = {}
    for c in lire("credits"):
        compte_credit[c["id_credit"]] = c["id_compte_epargne"]
        soldes[c["id_compte_epargne"]] += int(c["montant_accorde"]) - int(c["frais_dossier"])
    for r in lire("remboursements"):
        if r["canal"] == "PRELEVEMENT":
            soldes[compte_credit[r["id_credit"]]] -= int(r["montant_paye"])
    return dict(soldes)


def test_soldes_au_31_12_egaux_verite() -> None:
    """Soldes au 31/12 de fct_solde_compte_mensuel = soldes recalculés depuis la vérité."""
    lignes = requete(
        "SELECT id_compte, solde FROM gold.fct_solde_compte_mensuel "
        "WHERE date_fin_mois = (SELECT max(date) FROM gold.dim_date WHERE dans_exercice)"
    )
    gold = {str(i): int(str(s)) for i, s in lignes}
    attendu = soldes_verite()
    assert gold.keys() == attendu.keys()
    ecarts = {k: (gold[k], attendu[k]) for k in attendu if gold[k] != attendu[k]}
    assert not ecarts, f"{len(ecarts)} compte(s) en écart, ex. {list(ecarts.items())[:3]}"


def test_dossier_verite_present() -> None:
    assert Path(VERITE / "par30.csv").exists(), "lance `make generate`"


def produits_et_charges_verite() -> dict[str, int]:
    """Produits et charges de l'exercice recalculés depuis data/_verite/ (oracle hors dbt)."""
    remboursements = lire("remboursements")
    totaux = {
        "interets": sum(int(r["part_interets"]) for r in remboursements),
        "penalites": sum(int(r["penalites"]) for r in remboursements),
        "frais_dossier": sum(int(c["frais_dossier"]) for c in lire("credits")),
        "frais_tenue": sum(
            int(o["montant"]) for o in lire("operations") if o["type_operation"] == "FRAIS_TENUE"
        ),
    }
    for charge in lire("charges"):
        cle = f"charge_{charge['categorie'].lower()}"
        totaux[cle] = totaux.get(cle, 0) + int(charge["montant"])
    return totaux


def test_compte_de_resultat_egal_verite() -> None:
    """Cumul au 31/12 de mart_compte_resultat = produits et charges de la vérité, par rubrique."""
    v = produits_et_charges_verite()
    attendu = {
        "R1_PRODUITS_FINANCIERS": v["interets"] + v["penalites"],
        "R2_COMMISSIONS": v["frais_dossier"] + v["frais_tenue"],
        "R3_CHARGES_PERSONNEL": v["charge_personnel"],
        "R4_CHARGES_GENERALES": v["charge_loyers"]
        + v["charge_telecom_si"]
        + v["charge_fournitures"]
        + v["charge_commissions_mm"],
    }
    lignes = requete(
        "SELECT rubrique, montant_cumul, resultat_cumul FROM gold.mart_compte_resultat "
        "WHERE date_fin_mois = (SELECT max(date) FROM gold.dim_date WHERE dans_exercice)"
    )
    obtenu = {str(r): int(str(m)) for r, m, _ in lignes}
    assert obtenu == attendu
    produits = attendu["R1_PRODUITS_FINANCIERS"] + attendu["R2_COMMISSIONS"]
    charges = attendu["R3_CHARGES_PERSONNEL"] + attendu["R4_CHARGES_GENERALES"]
    assert sum(int(str(res)) for _, _, res in lignes) == produits - charges
