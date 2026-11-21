"""Reproductibilité : même seed → mêmes fichiers ; la vérité ne dépend pas des anomalies."""

import json
from pathlib import Path

import pytest

from generator.__main__ import Generation, generer
from generator.config import Config
from generator.ecriture import MANIFESTE, sha256
from generator.tests.conftest import petite_config


def empreintes(sortie: Path, sous_dossier: str = "") -> dict[str, str]:
    """SHA-256 de tous les fichiers de data/ (ou d'un sous-dossier), hors _manifest.json."""
    racine = sortie / sous_dossier
    return {
        f.relative_to(sortie).as_posix(): sha256(f)
        for f in sorted(racine.rglob("*"))
        if f.is_file() and f.name != MANIFESTE
    }


def test_meme_seed_memes_fichiers(petite_generation: Generation, tmp_path: Path) -> None:
    seconde = generer(petite_config(tmp_path / "data"))
    premiere = empreintes(petite_generation.config.sortie)
    assert premiere == empreintes(seconde.config.sortie)
    # Le manifeste liste exactement ces fichiers, avec les mêmes empreintes.
    assert seconde.manifeste["fichiers"] == premiere
    # Mêmes date_maj d'une exécution à l'autre.
    assert [c.date_maj for c in seconde.verite.credits] == [
        c.date_maj for c in petite_generation.verite.credits
    ]


def test_seed_differente_fichiers_differents(petite_generation: Generation, tmp_path: Path) -> None:
    autre = generer(petite_config(tmp_path / "data", seed=7))
    premiere = empreintes(petite_generation.config.sortie, "_verite")
    seconde = empreintes(autre.config.sortie, "_verite")
    differents = {f for f in premiere if premiere[f] != seconde[f]}
    # Seul le catalogue des produits, fixé dans config.py, ne dépend pas de la seed.
    assert set(premiere) - differents == {"_verite/produits_credit.csv"}


def test_taux_d_anomalies_sans_effet_sur_la_verite(
    petite_generation: Generation, tmp_path: Path
) -> None:
    autre = generer(petite_config(tmp_path / "data", taux_anomalies=0.05))
    assert empreintes(autre.config.sortie, "_verite") == empreintes(
        petite_generation.config.sortie, "_verite"
    )
    assert len(autre.brut.catalogue) > len(petite_generation.brut.catalogue)


def test_sans_anomalie(tmp_path: Path) -> None:
    """Taux nul : catalogue vide, sorties brutes identiques à la vérité."""
    generation = generer(petite_config(tmp_path / "data", taux_anomalies=0.0))
    assert generation.brut.catalogue == ()
    assert generation.brut.operations == generation.verite.operations


def test_data_reecrit_entierement(tmp_path: Path) -> None:
    """Une nouvelle exécution ne laisse aucun reste de la précédente."""
    sortie = tmp_path / "data"
    generer(petite_config(sortie))
    (sortie / "operations" / "date=1999-01-01").mkdir()
    (sortie / "reste.csv").write_text("x\n")
    generer(petite_config(sortie))
    assert not (sortie / "reste.csv").exists()
    assert not (sortie / "operations" / "date=1999-01-01").exists()


def test_refuse_un_dossier_etranger(tmp_path: Path) -> None:
    """Par sécurité, un dossier non vide sans manifeste n'est jamais supprimé."""
    (tmp_path / "important.txt").write_text("à garder\n")
    with pytest.raises(FileExistsError):
        generer(petite_config(tmp_path))
    assert (tmp_path / "important.txt").exists()


def test_manifeste_cles_triees(petite_generation: Generation) -> None:
    texte = (petite_generation.config.sortie / MANIFESTE).read_text(encoding="utf-8")
    assert (
        texte == json.dumps(json.loads(texte), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )


@pytest.mark.slow
def test_configuration_par_defaut_reproductible(
    generation_defaut: Generation, tmp_path: Path
) -> None:
    """Deux exécutions avec la configuration par défaut : SHA-256 identiques."""
    seconde = generer(Config(sortie=tmp_path / "data"))
    assert empreintes(seconde.config.sortie) == empreintes(generation_defaut.config.sortie)
