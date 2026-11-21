"""Tests unitaires des fenêtres d'extraction et de l'empreinte de génération."""

from datetime import date, datetime, timedelta

import pytest

from ingestion.config import INSTANTANES, PARTITIONS, TABLES_OPS
from ingestion.fenetre import (
    Fenetre,
    calculer_fenetre,
    fin_du_jour,
    jours_entre,
    jours_exercice,
    nouveau_filigrane,
)
from ingestion.journal import empreinte_generation

UNE_MICROSECONDE = timedelta(microseconds=1)


def test_filigrane_absent_depuis_l_origine() -> None:
    fenetre = calculer_fenetre(None, date(2025, 3, 15))
    assert fenetre == Fenetre(None, datetime(2025, 3, 16, 0, 0, 0))
    assert not fenetre.vide
    assert fenetre.contient(datetime(1900, 1, 1))
    assert fenetre.contient(datetime(2025, 3, 15, 20, 0, 0))


def test_premier_jour_de_l_exercice() -> None:
    fenetre = calculer_fenetre(None, date(2025, 1, 1))
    assert fenetre.fin_exclue == datetime(2025, 1, 2)
    assert fenetre.contient(datetime(2025, 1, 1, 20, 0, 0))
    assert not fenetre.contient(datetime(2025, 1, 2, 20, 0, 0))


def test_dernier_jour_de_l_exercice() -> None:
    """J = 31/12 : la borne haute passe à l'année suivante."""
    fenetre = calculer_fenetre(datetime(2025, 12, 30, 20, 0, 0), date(2025, 12, 31))
    assert fenetre.fin_exclue == datetime(2026, 1, 1, 0, 0, 0)
    assert fenetre.contient(datetime(2025, 12, 31, 20, 0, 0))
    assert fenetre.contient(datetime(2025, 12, 31, 23, 59, 59, 999_999))


def test_demi_ouverture() -> None:
    """]filigrane, J+1 00:00[ : filigrane exclu, J+1 00:00 exclu, J 23:59:59.999999 inclus."""
    filigrane = datetime(2025, 3, 14, 20, 0, 0)
    fenetre = calculer_fenetre(filigrane, date(2025, 3, 15))
    assert not fenetre.contient(filigrane)
    assert fenetre.contient(filigrane + UNE_MICROSECONDE)
    assert fenetre.contient(fin_du_jour(date(2025, 3, 15)) - UNE_MICROSECONDE)
    assert not fenetre.contient(fin_du_jour(date(2025, 3, 15)))


def test_fenetre_vide_pour_un_jour_deja_extrait() -> None:
    """Rejouer un jour passé : le filigrane est déjà au-delà de J+1 00:00."""
    assert calculer_fenetre(datetime(2025, 12, 31, 20, 0, 0), date(2025, 3, 15)).vide
    assert calculer_fenetre(datetime(2025, 3, 16, 0, 0, 0), date(2025, 3, 15)).vide
    assert not calculer_fenetre(datetime(2025, 3, 15, 20, 0, 0), date(2025, 3, 15)).vide


def test_nouveau_filigrane() -> None:
    avant = datetime(2025, 3, 14, 20, 0, 0)
    assert nouveau_filigrane(avant, None) == avant
    assert nouveau_filigrane(None, None) is None
    assert nouveau_filigrane(None, avant) == avant
    assert nouveau_filigrane(avant, avant + timedelta(days=1)) == avant + timedelta(days=1)
    assert nouveau_filigrane(avant, avant - timedelta(days=1)) == avant


def test_jours() -> None:
    assert jours_entre(date(2025, 12, 30), date(2026, 1, 1)) == [
        date(2025, 12, 30),
        date(2025, 12, 31),
        date(2026, 1, 1),
    ]
    assert len(jours_exercice(2025)) == 365
    assert len(jours_exercice(2024)) == 366
    with pytest.raises(ValueError, match="période vide"):
        jours_entre(date(2025, 2, 1), date(2025, 1, 31))


def test_chemins_des_objets() -> None:
    jour = date(2025, 3, 15)
    assert PARTITIONS[0].chemin(jour) == "operations/date=2025-03-15/operations.csv"
    assert INSTANTANES[0].chemin(jour) == "agences.csv"
    assert TABLES_OPS[1].chemin(jour) == "landing/imf_ops/clients/date=2025-03-15/clients.csv"


def test_empreinte_generation() -> None:
    """Déterministe, insensible à l'ordre des clés, sensible au contenu."""
    manifeste = {"parametres": {"seed": 42, "clients": 100}, "fichiers": {"a.csv": "0" * 64}}
    meme = {"fichiers": {"a.csv": "0" * 64}, "parametres": {"clients": 100, "seed": 42}}
    autre = {"parametres": {"seed": 7, "clients": 100}, "fichiers": {"a.csv": "0" * 64}}
    assert empreinte_generation(manifeste) == empreinte_generation(meme)
    assert empreinte_generation(manifeste) != empreinte_generation(autre)
    assert len(empreinte_generation(manifeste)) == 64
    # Une clé hors de la partie déterministe ne change pas l'empreinte.
    assert empreinte_generation(manifeste | {"execute_le": "2026-11-21"}) == empreinte_generation(
        manifeste
    )
