"""Tests des règles d'évaluation de l'orchestration (sans base de données)."""

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from orchestration import audit
from orchestration.resultats import (
    AVERTISSEMENT,
    CODE_ECHEC_CONTROLE,
    CODE_ERREUR_TECHNIQUE,
    CODE_SUCCES,
    ECHEC_CONTROLE,
    ECHEC_TECHNIQUE,
    NON_EXECUTE,
    SUCCES,
    Resume,
    evaluer_completude,
    evaluer_run_results,
    evaluer_volume,
    statut_global,
)

DONNEES = Path(__file__).parent / "donnees"
JOUR = date(2025, 3, 12)  # un mercredi
RACINE = Path(__file__).resolve().parents[2]


def charger(nom: str) -> dict[str, Any]:
    contenu: dict[str, Any] = json.loads((DONNEES / nom).read_text(encoding="utf-8"))
    return contenu


# --- dbt : run_results.json ------------------------------------------------------------------


def test_run_results_tout_vert() -> None:
    resume = evaluer_run_results(JOUR, 0, charger("run_results_vert.json"))
    assert (resume.statut, resume.code) == (SUCCES, CODE_SUCCES)
    assert (resume.nb_pass, resume.nb_warn, resume.nb_error, resume.nb_skip) == (5, 0, 0, 0)
    assert resume.noeuds_en_echec == [] and resume.noeuds_sautes == []


def test_run_results_test_en_echec_et_noeuds_sautes() -> None:
    """Un test en échec et des modèles sautés : échec de contrôle, nœuds listés."""
    resume = evaluer_run_results(JOUR, 1, charger("run_results_echec.json"))
    assert (resume.statut, resume.code) == (ECHEC_CONTROLE, CODE_ECHEC_CONTROLE)
    assert resume.noeuds_en_echec == ["test.imf_dwh.evenements_rejetes_vide"]
    assert resume.noeuds_sautes == ["model.imf_dwh.fct_ecritures", "model.imf_dwh.mart_balance"]
    assert (resume.nb_pass, resume.nb_warn, resume.nb_error, resume.nb_skip) == (3, 1, 1, 2)


@pytest.mark.parametrize(
    ("code", "contenu"),
    [(2, {"results": []}), (1, None), (0, None)],
    ids=["code2", "absent1", "absent0"],
)
def test_run_results_erreur_technique(code: int, contenu: dict[str, Any] | None) -> None:
    """Code dbt 2 ou run_results.json absent : erreur technique, relançable."""
    resume = evaluer_run_results(JOUR, code, contenu)
    assert (resume.statut, resume.code) == (ECHEC_TECHNIQUE, CODE_ERREUR_TECHNIQUE)


def test_run_results_base_injoignable_est_technique() -> None:
    """Nœuds en erreur parce que PostgreSQL est arrêté : panne transitoire, relançable."""
    contenu = {
        "results": [
            {"unique_id": "model.a", "status": "error", "message": "connection to server at "
             "\"postgres\" (172.18.0.2), port 5432 failed: Connection refused"},
            {"unique_id": "model.b", "status": "skipped"},
        ]
    }  # fmt: skip
    resume = evaluer_run_results(JOUR, 1, contenu)
    assert (resume.statut, resume.code) == (ECHEC_TECHNIQUE, CODE_ERREUR_TECHNIQUE)
    assert resume.noeuds_en_echec == ["model.a"] and resume.noeuds_sautes == ["model.b"]


def test_run_results_avertissement() -> None:
    contenu = {
        "results": [
            {"unique_id": "test.a", "status": "warn"},
            {"unique_id": "m", "status": "success"},
        ]
    }
    resume = evaluer_run_results(JOUR, 0, contenu)
    assert (resume.statut, resume.code) == (AVERTISSEMENT, CODE_SUCCES)


# --- volume ----------------------------------------------------------------------------------


def historique(valeurs: list[int | None], jour: date = JOUR) -> dict[date, int | None]:
    """Historique des 4 mêmes jours de semaine précédents (J−7, J−14, J−21, J−28)."""
    return {jour - timedelta(days=7 * k): v for k, v in enumerate(valeurs, start=1)}


def test_volume_dimanche_a_zero_normal() -> None:
    dimanche = date(2025, 3, 16)
    resume = evaluer_volume(dimanche, 0, historique([40, 50, 45, 55], dimanche))
    assert (resume.statut, resume.code) == (SUCCES, CODE_SUCCES)
    assert "dimanche" in resume.message


def test_volume_historique_insuffisant() -> None:
    """Moins de 4 semaines d'historique ingéré : pas de contrôle."""
    resume = evaluer_volume(JOUR, 1000, historique([100, 100, None, None]))
    assert resume.statut == SUCCES and "pas de contrôle" in resume.message


@pytest.mark.parametrize(
    ("nb", "statut"),
    [(100, SUCCES), (50, SUCCES), (200, SUCCES), (49, AVERTISSEMENT), (201, AVERTISSEMENT)],
    ids=["moyenne", "borne_50", "borne_200", "sous_50", "au_dela_200"],
)
def test_volume_plage(nb: int, statut: str) -> None:
    """Plage [50 % ; 200 %] de la moyenne ; hors plage : avertissement, sortie 0."""
    resume = evaluer_volume(JOUR, nb, historique([80, 120, 90, 110]))
    assert (resume.statut, resume.code) == (statut, CODE_SUCCES)
    assert resume.details["moyenne_reference"] == 100.0


# --- complétude ------------------------------------------------------------------------------


def test_completude_ecart() -> None:
    attendu = {"operations/date=2025-03-12/operations.csv": 180, "landing/imf_ops/x.csv": 4}
    charge = {"operations/date=2025-03-12/operations.csv": 179, "landing/imf_ops/x.csv": 4}
    resume = evaluer_completude(JOUR, attendu, charge, jour_ingere=True)
    assert (resume.statut, resume.code) == (ECHEC_CONTROLE, CODE_ECHEC_CONTROLE)
    assert resume.details["ecarts"] == {
        "operations/date=2025-03-12/operations.csv": {"attendu": 180, "charge": 179}
    }


def test_completude_rejeu_ignore_compte_comme_charge() -> None:
    """Rejeu idempotent : les lignes du premier chargement sont en bronze, rien n'est rechargé."""
    attendu = {"operations/date=2025-03-12/operations.csv": 180}
    resume = evaluer_completude(JOUR, attendu, dict(attendu), jour_ingere=True)
    assert resume.statut == SUCCES and resume.lignes_chargees == 180


def test_completude_jour_non_ingere() -> None:
    resume = evaluer_completude(JOUR, {}, {}, jour_ingere=False)
    assert resume.statut == ECHEC_CONTROLE


# --- audit -----------------------------------------------------------------------------------


def test_construction_ligne_audit() -> None:
    resume = evaluer_run_results(JOUR, 1, charger("run_results_echec.json"))
    debut = datetime(2026, 11, 22, 10, 0, 0, tzinfo=UTC)
    ligne = audit.construire_ligne(
        resume, dag_id="imf_quotidien", run_id="backfill__2025-03-12", etape="dbt_build",
        tentative=1, debut=debut, fin=debut + timedelta(seconds=21.5), racine=RACINE,
    )  # fmt: skip
    assert ligne.date_logique == JOUR and ligne.etape == "dbt_build"
    assert (ligne.statut, ligne.duree_s, ligne.nb_error, ligne.nb_skip) == (
        ECHEC_CONTROLE,
        21.5,
        1,
        2,
    )
    assert ligne.noeuds_sautes == resume.noeuds_sautes
    assert ligne.version_mapping == "v0.5"
    assert ligne.commit_git is not None and len(ligne.commit_git) == 40


def test_ligne_audit_statut_impose() -> None:
    resume = Resume("ingerer", JOUR.isoformat(), SUCCES)
    debut = datetime(2026, 11, 22, tzinfo=UTC)
    ligne = audit.construire_ligne(
        resume, dag_id="d", run_id="r", etape="RUN", tentative=1, debut=debut, fin=debut,
        statut=ECHEC_TECHNIQUE,
    )  # fmt: skip
    assert ligne.statut == ECHEC_TECHNIQUE and ligne.etape == "RUN"


def test_statut_global() -> None:
    assert statut_global({"a": SUCCES, "b": AVERTISSEMENT}) == AVERTISSEMENT
    assert statut_global({"a": SUCCES, "b": None}) == NON_EXECUTE
    assert statut_global({"a": ECHEC_TECHNIQUE, "b": ECHEC_CONTROLE}) == ECHEC_CONTROLE
    assert statut_global({"a": SUCCES}) == SUCCES


def test_resume_json_derniere_ligne() -> None:
    texte = Resume("volume", JOUR.isoformat(), AVERTISSEMENT, "x", lignes_chargees=3).json()
    assert "\n" not in texte
    assert Resume(**json.loads(texte)).statut == AVERTISSEMENT
