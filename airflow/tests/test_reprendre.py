"""Tests du script de reprise (airflow/reprendre.py), dans le conteneur Airflow."""

import importlib.util
import subprocess
from datetime import date
from pathlib import Path
from types import ModuleType

import pytest

# Demande Airflow installé (reprendre.py importe airflow) : conteneur seulement, jamais en CI.
pytestmark = pytest.mark.airflow

CHEMIN = Path(__file__).resolve().parents[1] / "reprendre.py"
JOUR = date(2025, 2, 12)


def _module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("reprendre", CHEMIN)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


reprendre = _module()


def test_commande_clear_sans_ancres_avec_aval() -> None:
    commande = reprendre.commande_clear(JOUR, "ingerer")
    assert commande[-3:] == ["-t", "ingerer", "--downstream"]
    assert "^ingerer$" not in commande
    assert reprendre.commande_clear(JOUR, None)[-1] == "-y"


def test_taches_visees_etape_et_aval() -> None:
    assert reprendre.taches_visees("dbt_build") == {"dbt_build", "ecrire_audit"}
    assert reprendre.taches_visees("ingerer") == {
        "ingerer", "controler_completude", "controler_volume", "dbt_build", "ecrire_audit"
    }  # fmt: skip
    assert len(reprendre.taches_visees(None)) == 7


def test_taches_visees_etape_inconnue() -> None:
    with pytest.raises(SystemExit, match="Étape inconnue"):
        reprendre.taches_visees("ingestion")


def test_toutes_remises_a_zero() -> None:
    etats = {"dbt_build": None, "ecrire_audit": "scheduled", "ingerer": "success"}
    assert reprendre.non_remises(etats, {"dbt_build", "ecrire_audit"}) == []


def test_taches_non_remises_listees() -> None:
    etats = {"dbt_build": "failed", "ecrire_audit": "success", "controler_volume": None}
    visees = {"controler_volume", "dbt_build", "ecrire_audit", "controler_completude"}
    # controler_completude absente du run : non remise non plus.
    assert reprendre.non_remises(etats, visees) == [
        "controler_completude", "dbt_build", "ecrire_audit"
    ]  # fmt: skip


def test_clear_sans_effet_sortie_en_erreur(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Clear sans effet (cas des ancres du lot C) : erreur, aucun run suivant remis en file."""
    remis: list[date] = []
    monkeypatch.setattr(reprendre.sys, "argv", ["reprendre.py", JOUR.isoformat(), "dbt_build"])
    monkeypatch.setattr(
        reprendre.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 0)
    )
    monkeypatch.setattr(
        reprendre, "etats_du_jour", lambda jour: {"dbt_build": "failed", "ecrire_audit": "success"}
    )

    def remettre_en_file(jour: date) -> list[str]:
        remis.append(jour)
        return []

    monkeypatch.setattr(reprendre, "remettre_en_file", remettre_en_file)
    assert reprendre.main() == 1
    erreur = capsys.readouterr().err
    assert "non remise(s) à zéro" in erreur and "dbt_build, ecrire_audit" in erreur
    assert remis == []


def test_clear_effectif_remet_en_file(monkeypatch: pytest.MonkeyPatch) -> None:
    remis: list[date] = []
    monkeypatch.setattr(reprendre.sys, "argv", ["reprendre.py", JOUR.isoformat(), "dbt_build"])
    monkeypatch.setattr(
        reprendre.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 0)
    )
    monkeypatch.setattr(
        reprendre, "etats_du_jour", lambda jour: {"dbt_build": None, "ecrire_audit": None}
    )

    def remettre_en_file(jour: date) -> list[str]:
        remis.append(jour)
        return ["backfill__2025-02-13T00:00:00+00:00"]

    monkeypatch.setattr(reprendre, "remettre_en_file", remettre_en_file)
    assert reprendre.main() == 0
    assert remis == [JOUR]
