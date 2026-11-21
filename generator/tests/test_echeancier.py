"""Tests unitaires de l'échéancier et du TEG."""

from datetime import date
from decimal import Decimal

import pytest

from generator import config as cfg
from generator.echeancier import arrondi, calculer_echeancier, teg_actuariel

CAS = [
    (montant, p.taux_annuel, duree)
    for p in cfg.PRODUITS
    for montant in (p.montant_min, 777_777, p.montant_max)
    for duree in (p.duree_min_mois, p.duree_max_mois)
]


@pytest.mark.parametrize(("montant", "taux", "duree"), CAS)
def test_capital_rembourse_et_montants_entiers(montant: int, taux: Decimal, duree: int) -> None:
    """Σ capital = montant accordé ; montants entiers ≥ 0 ; une échéance par mois."""
    echeances = calculer_echeancier(montant, taux, duree, date(2025, 3, 15))
    assert len(echeances) == duree
    assert sum(e.capital for e in echeances) == montant
    for e in echeances:
        assert isinstance(e.capital, int) and isinstance(e.interets, int)
        assert e.capital >= 0 and e.interets >= 0


@pytest.mark.parametrize(("montant", "taux", "duree"), CAS)
def test_annuites_constantes_derniere_absorbe_arrondi(
    montant: int, taux: Decimal, duree: int
) -> None:
    """Toutes les échéances valent l'annuité arrondie, sauf la dernière (arrondi)."""
    echeances = calculer_echeancier(montant, taux, duree, date(2025, 3, 15))
    annuites = {e.montant for e in echeances[:-1]}
    assert len(annuites) == 1
    assert abs(echeances[-1].montant - annuites.pop()) <= duree


def test_cas_calcule_a_la_main() -> None:
    """120 000 XOF à 12 % sur 3 mois : taux mensuel 1 %, annuité 40 802,65 → 40 803.

    Échéance 1 : intérêts 1 200, capital 39 603, reste 80 397.
    Échéance 2 : intérêts 803,97 → 804, capital 39 999, reste 40 398.
    Échéance 3 : intérêts 403,98 → 404, capital 40 398 (absorbe l'arrondi : 40 802).
    """
    echeances = calculer_echeancier(120_000, Decimal("0.12"), 3, date(2025, 1, 31))
    assert [(e.capital, e.interets) for e in echeances] == [
        (39_603, 1_200),
        (39_999, 804),
        (40_398, 404),
    ]
    # Dates : même jour chaque mois, ramené au dernier jour des mois courts.
    assert [e.date_echeance for e in echeances] == [
        date(2025, 2, 28),
        date(2025, 3, 31),
        date(2025, 4, 30),
    ]


def test_arrondi_moitie_superieure() -> None:
    assert arrondi(Decimal("0.5")) == 1
    assert arrondi(Decimal("1.49")) == 1
    assert arrondi(Decimal("2.5")) == 3


def test_teg_contre_exemple_au_dela_du_plafond() -> None:
    """15 % + 2 % de frais sur 6 mois : TEG actuariel > 24 % (détecté)."""
    echeances = calculer_echeancier(1_000_000, Decimal("0.15"), 6, date(2025, 1, 15))
    teg = teg_actuariel(1_000_000, 20_000, echeances)
    assert teg > float(cfg.TEG_MAX)


def test_teg_sans_frais_egal_au_taux_effectif() -> None:
    """Sans frais, le TEG est le taux nominal mensuel annualisé (1 + t/12)^12 − 1."""
    echeances = calculer_echeancier(1_000_000, Decimal("0.12"), 12, date(2025, 1, 15))
    assert teg_actuariel(1_000_000, 0, echeances) == pytest.approx(1.01**12 - 1, abs=1e-4)


@pytest.mark.parametrize("produit", cfg.PRODUITS, ids=lambda p: p.code)
def test_teg_produits_sous_le_plafond(produit: cfg.ParametresProduit) -> None:
    """Pire cas de chaque produit (durée minimale, frais maximaux) : TEG ≤ 24 %."""
    montant = produit.montant_min
    echeances = calculer_echeancier(
        montant, produit.taux_annuel, produit.duree_min_mois, date(2025, 1, 15)
    )
    frais = arrondi(produit.taux_frais_dossier * montant)
    assert teg_actuariel(montant, frais, echeances) <= float(cfg.TEG_MAX)
