"""Calibrage de la configuration par défaut (tests longs, marqueur slow)."""

from collections import Counter
from datetime import date, timedelta

import pytest

from generator import config as cfg
from generator.__main__ import Generation
from generator.echeancier import ajouter_mois
from generator.simulation import est_ouvre, jours

pytestmark = pytest.mark.slow


def test_par30_entre_4_et_6_pourcent(generation_defaut: Generation) -> None:
    par30 = generation_defaut.manifeste["indicateurs"]["par30_31_12"]
    assert 0.04 <= par30 <= 0.06


def test_nombre_de_credits(generation_defaut: Generation) -> None:
    nb = len(generation_defaut.verite.credits)
    demande = generation_defaut.config.nb_credits
    assert demande == 3000
    assert abs(nb - demande) <= cfg.TOLERANCE_NB_CREDITS * demande


def test_tresorerie_positive(generation_defaut: Generation) -> None:
    indicateurs = generation_defaut.verite.indicateurs
    assert indicateurs.caisse_minimale >= 0
    assert indicateurs.banque_minimale >= 0
    assert indicateurs.nb_approvisionnements > 0


def _par_mois(generation: Generation) -> dict[int, int]:
    mois = Counter(c.date_decaissement.month for c in generation.verite.credits)
    return {m: mois.get(m, 0) for m in range(1, 13)}


def test_croissance_mensuelle_sans_saut(generation_defaut: Generation) -> None:
    """Aucun mois > 1,25 × le précédent, sauf février (1er mois avec crédits) et les mois
    qui ouvrent une saison (mai : AGRICOLE, août : SCOLAIRE)."""
    mois = _par_mois(generation_defaut)
    assert mois[1] == 0  # aucune ancienneté de 30 jours possible en janvier
    exemptes = {2, 5, 8}
    for m in range(3, 13):
        if m not in exemptes:
            assert mois[m] <= 1.25 * mois[m - 1], (m, mois)


def test_pas_de_rattrapage_en_decembre(generation_defaut: Generation) -> None:
    mois = _par_mois(generation_defaut)
    assert mois[12] <= 1.15 * mois[11], mois


def test_aucun_jour_de_pic(generation_defaut: Generation) -> None:
    """Aucun jour > 3 × la moyenne par jour ouvré de son mois."""
    par_jour = Counter(c.date_decaissement for c in generation_defaut.verite.credits)
    mois = _par_mois(generation_defaut)
    annee = generation_defaut.config.exercice
    for jour, nombre in par_jour.items():
        assert est_ouvre(jour)
        premier = date(annee, jour.month, 1)
        ouvres = sum(
            1 for j in jours(premier, ajouter_mois(premier, 1) - timedelta(days=1)) if est_ouvre(j)
        )
        assert nombre <= 3 * mois[jour.month] / ouvres, (jour, nombre)
