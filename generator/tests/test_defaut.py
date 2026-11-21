"""Calibrage de la configuration par défaut (tests longs, marqueur slow)."""

import pytest

from generator import config as cfg
from generator.__main__ import Generation

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
