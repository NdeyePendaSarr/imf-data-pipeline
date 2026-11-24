"""Logique de comparaison des moteurs (scripts/comparer_moteurs.py), sans réseau ni base."""

import datetime as dt
from decimal import Decimal
from typing import Any

import pytest

from scripts.comparer_moteurs import (
    BILAN_PAR_MOIS,
    DATE_GOLD,
    REQUETES_GOLD,
    TABLES_GOLD,
    TABLES_SILVER,
    ErreurComparaison,
    Mesure,
    comparer,
    normaliser,
    tableau_markdown,
    verifier_dates,
)

ARRETE = dt.date(2025, 12, 31)
COLONNES = {"slv_credits": ["montant_accorde", "taux_annuel"]}


def moteur(date: dt.date = ARRETE, taux: Any = Decimal("443.2500"), lignes_ecritures: int = 181193,
           passif_decembre: int = 2119584054) -> Any:  # fmt: skip
    """Moteur simulé : répond à chaque requête de comparer() par des valeurs fixes."""

    def executer(requete: str) -> list[tuple[Any, ...]]:
        if requete == DATE_GOLD:
            return [(date,)]
        if requete == BILAN_PAR_MOIS:
            return [(dt.date(2025, 11, 30), 2000, 2000), (ARRETE, 2119584054, passif_decembre)]
        if requete == REQUETES_GOLD["encours, encours PAR 30 (dernier jour)"]:
            return [(1850520623, 92511316)]
        if requete.startswith("select count(*) from {gold}.fct_ecritures"):
            return [(lignes_ecritures,)]
        if requete.startswith("select count(*) from {gold}."):
            return [(10,)]
        if "{silver}.slv_credits" in requete:
            return [(3000, 2747540000, taux)]
        if "{silver}." in requete:
            return [(5,)]
        return [(1, 0)]

    return executer


def test_egalite_complete() -> None:
    mesures = comparer(moteur(), moteur(taux=443.25), COLONNES)
    assert all(m.egale for m in mesures), [m for m in mesures if not m.egale]
    noms = {m.nom for m in mesures}
    assert {f"gold.{t} : lignes" for t in TABLES_GOLD} <= noms
    assert {f"silver.{t} : lignes" for t in TABLES_SILVER} <= noms
    assert "silver.slv_credits : taux_annuel" in noms


def test_443_2500_egal_443_25() -> None:
    """PostgreSQL rend numeric(6,4) avec ses zéros, BigQuery NUMERIC sans : même valeur."""
    assert Mesure("taux", Decimal("443.2500"), Decimal("443.25")).egale
    assert normaliser((Decimal("0.5700"), 3000)) == normaliser((0.57, Decimal(3000)))


def test_ecart_detecte() -> None:
    mesures = comparer(moteur(), moteur(lignes_ecritures=181192), COLONNES)
    ecarts = [m.nom for m in mesures if not m.egale]
    assert ecarts == ["gold.fct_ecritures : lignes"]


def test_desequilibre_du_bilan_detecte() -> None:
    mesures = comparer(moteur(), moteur(passif_decembre=1), COLONNES)
    ecarts = [m.nom for m in mesures if not m.egale]
    assert "bilan : mois déséquilibrés (bq)" in ecarts
    assert f"bilan {ARRETE} (actif, passif)" in ecarts


def test_resume_markdown() -> None:
    """Tableau pour $GITHUB_STEP_SUMMARY : une ligne par mesure, écart signalé en gras."""
    mesures = comparer(moteur(), moteur(lignes_ecritures=1), COLONNES)
    texte = tableau_markdown(mesures)
    assert f"**{len(mesures)} mesures, 1 écart(s)**" in texte
    assert "| gold.fct_ecritures : lignes | 181193 | 1 | **ÉCART** |" in texte
    assert texte.count("\n| ") == len(mesures) + 1  # en-tête + une ligne par mesure


def test_dates_differentes_refusees() -> None:
    with pytest.raises(ErreurComparaison, match="dates du gold différentes"):
        comparer(moteur(), moteur(date=dt.date(2025, 3, 15)), COLONNES)
    with pytest.raises(ErreurComparaison):
        verifier_dates(None, ARRETE)
