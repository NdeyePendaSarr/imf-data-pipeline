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
    VOLUME_REFERENCE_MIN,
    Resume,
    est_dernier_jour_ouvre,
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


EXERCICE = [date(2025, 1, 1) + timedelta(days=i) for i in range(365)]
MARDI_JUIN = date(2025, 6, 10)
FIN_SEPTEMBRE = date(2025, 9, 30)  # dernier jour ouvré de septembre (un mardi)


def serie_lineaire() -> dict[date, int | None]:
    """Portefeuille en croissance linéaire régulière, comme le générateur : jours ouvrés
    20 + t opérations, dimanches au cinquième, fins de mois au quintuple."""
    volumes: dict[date, int | None] = {}
    for t, jour in enumerate(EXERCICE):
        base = 20 + t
        if jour.isoweekday() == 7:
            base //= 5
        elif est_dernier_jour_ouvre(jour):
            base *= 5
        volumes[jour] = base
    return volumes


def serie_plate(valeur: int = 100) -> dict[date, int | None]:
    return dict.fromkeys(EXERCICE, valeur)


def avertissements(volumes: dict[date, int | None]) -> list[date]:
    return [j for j in EXERCICE if evaluer_volume(j, volumes).statut == AVERTISSEMENT]


def test_derniers_jours_ouvres() -> None:
    assert est_dernier_jour_ouvre(date(2025, 1, 31))  # vendredi
    assert est_dernier_jour_ouvre(date(2025, 5, 31))  # samedi
    assert est_dernier_jour_ouvre(date(2025, 11, 29))  # samedi, le 30 est un dimanche
    assert not est_dernier_jour_ouvre(date(2025, 11, 30))
    assert not est_dernier_jour_ouvre(date(2025, 1, 30))


def test_volume_croissance_lineaire_sans_alerte() -> None:
    """Croissance régulière du portefeuille, fins de mois comprises : aucune alerte."""
    assert avertissements(serie_lineaire()) == []


def test_volume_chute_jour_ordinaire() -> None:
    volumes = serie_lineaire()
    volumes[MARDI_JUIN] = int((volumes[MARDI_JUIN] or 0) * 0.4)  # −60 %
    resume = evaluer_volume(MARDI_JUIN, volumes)
    assert (resume.statut, resume.code) == (AVERTISSEMENT, CODE_SUCCES)
    assert resume.details["nature"] == "jour ordinaire"
    assert resume.details["ratio"] < 0.5
    assert avertissements(volumes)[0] == MARDI_JUIN


def test_volume_pic_jour_ordinaire() -> None:
    volumes = serie_lineaire()
    volumes[MARDI_JUIN] = (volumes[MARDI_JUIN] or 0) * 3
    resume = evaluer_volume(MARDI_JUIN, volumes)
    assert (resume.statut, resume.code) == (AVERTISSEMENT, CODE_SUCCES)
    assert resume.details["ratio"] > 2.0


def test_volume_chute_fin_de_mois() -> None:
    volumes = serie_lineaire()
    volumes[FIN_SEPTEMBRE] = int((volumes[FIN_SEPTEMBRE] or 0) * 0.4)
    resume = evaluer_volume(FIN_SEPTEMBRE, volumes)
    assert (resume.statut, resume.code) == (AVERTISSEMENT, CODE_SUCCES)
    assert resume.details["nature"] == "fin de mois"
    assert resume.details["ratio"] < 0.5


def test_volume_dimanche_a_zero_normal() -> None:
    dimanche = date(2025, 3, 16)
    volumes = serie_lineaire()
    volumes[dimanche] = 0
    resume = evaluer_volume(dimanche, volumes)
    assert (resume.statut, resume.code) == (SUCCES, CODE_SUCCES)
    assert "dimanche" in resume.message


@pytest.mark.parametrize(
    "jour",
    [date(2025, 1, 20), date(2025, 1, 31), JOUR],
    ids=["moins_de_4_semaines", "premiere_fin_de_mois", "jour_non_ingere"],
)
def test_volume_historique_insuffisant(jour: date) -> None:
    """Moins de 4 semaines, aucune fin de mois précédente ou jour manquant : pas de contrôle."""
    volumes = serie_lineaire()
    volumes[JOUR - timedelta(days=3)] = None
    volumes[jour] = 10_000
    resume = evaluer_volume(jour, volumes)
    assert resume.statut == SUCCES and "pas de contrôle" in resume.message


@pytest.mark.parametrize(
    ("nb", "statut"),
    [(100, SUCCES), (50, SUCCES), (200, SUCCES), (49, AVERTISSEMENT), (201, AVERTISSEMENT)],
    ids=["reference", "borne_50", "borne_200", "sous_50", "au_dela_200"],
)
@pytest.mark.parametrize("jour", [JOUR, date(2025, 3, 31)], ids=["ordinaire", "fin_de_mois"])
def test_volume_plage(jour: date, nb: int, statut: str) -> None:
    """Série plate : référence 100, facteur 1 ; hors de [50 % ; 200 %] : avertissement, sortie 0."""
    volumes = serie_plate()
    volumes[jour] = nb
    resume = evaluer_volume(jour, volumes)
    assert (resume.statut, resume.code) == (statut, CODE_SUCCES)
    assert (resume.details["reference"], resume.details["facteur_tendance"]) == (100.0, 1.0)


DIMANCHE_16_02 = date(2025, 2, 16)


@pytest.mark.parametrize(
    ("reference", "jour", "nb"),
    [(8, DIMANCHE_16_02, 16), (19, JOUR, 57)],
    ids=["reference_8_dimanche_16_02", "reference_19"],
)
def test_volume_reference_trop_faible_pas_de_controle(reference: int, jour: date, nb: int) -> None:
    """K11 : référence < 20 → pas de contrôle (même statut que sans historique), même à 200 % et
    plus (16 pour 8, comme le 16/02/2025 ; 57 pour 19, soit 300 %)."""
    assert VOLUME_REFERENCE_MIN == 20
    volumes = serie_plate(reference)
    volumes[jour] = nb
    resume = evaluer_volume(jour, volumes)
    assert (resume.statut, resume.code) == (SUCCES, CODE_SUCCES)
    assert "pas de contrôle" in resume.message
    assert resume.details == {"reference": float(reference)}
    assert "ratio" not in resume.details


def test_volume_reference_20_controle_normal() -> None:
    """Référence = 20 : contrôle normal (ratio calculé, dans la plage)."""
    volumes = serie_plate(20)
    volumes[JOUR] = 25
    resume = evaluer_volume(JOUR, volumes)
    assert resume.statut == SUCCES and "pas de contrôle" not in resume.message
    assert (resume.details["reference"], resume.details["ratio"]) == (20.0, 1.25)


@pytest.mark.parametrize("nb", [9, 41], ids=["sous_50", "au_dela_200"])
def test_volume_reference_20_hors_plage_avertissement(nb: int) -> None:
    """Référence ≥ 20 et volume hors de [50 % ; 200 %] : avertissement inchangé, sortie 0."""
    volumes = serie_plate(20)
    volumes[JOUR] = nb
    resume = evaluer_volume(JOUR, volumes)
    assert (resume.statut, resume.code) == (AVERTISSEMENT, CODE_SUCCES)
    assert resume.details["reference"] == 20.0


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
