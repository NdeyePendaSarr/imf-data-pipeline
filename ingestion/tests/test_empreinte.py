"""Empreinte de génération : elle couvre le contenu de imf_ops (trou de I12, phase 4).

Scénario de la correction S16 : une génération qui ne change qu'une ligne de imf_ops, sans
toucher aux fichiers de data/. L'empreinte doit changer et l'ingestion doit refuser de mélanger
les deux générations dans le même bronze.
"""

import json
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from generator.__main__ import Generation
from generator.anomalies import Brut
from generator.ecriture import MANIFESTE, ecrire_sorties
from generator.imf_ops import charger as charger_imf_ops
from ingestion.config import ErreurIngestion
from ingestion.journal import empreinte_generation
from ingestion.tests.conftest import Environnement


def _une_ligne_modifiee(brut: Brut) -> Brut:
    """Même brut, un seul remboursement modifié (1 XOF de pénalité et de montant payé en plus)."""
    premier = brut.remboursements[0]
    modifie = replace(
        premier, montant_paye=premier.montant_paye + 1, penalites=premier.penalites + 1
    )
    return replace(brut, remboursements=(modifie, *brut.remboursements[1:]))


def _regenerer(generation: Generation, brut: Brut, sortie: Path) -> dict[str, Any]:
    """Réécrit data/ dans `sortie` avec ce brut ; renvoie le manifeste."""
    config = replace(generation.config, sortie=sortie)
    return ecrire_sorties(generation.verite, brut, config)


def test_une_ligne_d_imf_ops_change_l_empreinte(
    generation_petite: Generation, tmp_path: Path
) -> None:
    """Une ligne de imf_ops modifiée : fichiers de data/ identiques, empreinte différente."""
    avant = _regenerer(generation_petite, generation_petite.brut, tmp_path / "a")
    apres = _regenerer(
        generation_petite, _une_ligne_modifiee(generation_petite.brut), tmp_path / "b"
    )
    # Aucun fichier de data/ ne change : c'est exactement le cas que l'ancienne empreinte ratait.
    assert apres["fichiers"] == avant["fichiers"]
    # Seule l'empreinte de la table modifiée change dans le manifeste…
    differentes = {t for t in avant["imf_ops"] if avant["imf_ops"][t] != apres["imf_ops"][t]}
    assert differentes == {"remboursements"}
    # … et donc l'empreinte de génération.
    assert empreinte_generation(apres) != empreinte_generation(avant)
    # Même contenu → même empreinte (déterministe).
    encore = _regenerer(generation_petite, generation_petite.brut, tmp_path / "c")
    assert empreinte_generation(encore) == empreinte_generation(avant)


@pytest.mark.integration
def test_ingestion_refuse_une_generation_qui_ne_change_que_imf_ops(env: Environnement) -> None:
    """Bronze issu de la génération A, puis imf_ops et manifeste de la génération A' : refus."""
    env.ingerer([date(2025, 1, 1)])
    manifeste_a = json.loads((env.source / MANIFESTE).read_text(encoding="utf-8"))

    # Génération A' : une ligne de imf_ops modifiée, rechargée dans la base de l'environnement.
    brut = _une_ligne_modifiee(env.generation.brut)
    charger_imf_ops(brut, env.parametres.base_ops)
    manifeste_b = _regenerer(env.generation, brut, env.source)
    assert manifeste_b["fichiers"] == manifeste_a["fichiers"]

    with pytest.raises(ErreurIngestion, match="autre génération : make reset-bronze"):
        env.ingerer([date(2025, 1, 2)])
