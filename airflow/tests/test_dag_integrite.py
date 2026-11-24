"""Intégrité des DAG Airflow, lancée dans le conteneur Airflow (make test-airflow)."""

import os
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest
from airflow.dag_processing.dagbag import DagBag

# Demande Airflow installé : conteneur seulement (make test-airflow), jamais en CI.
pytestmark = pytest.mark.airflow

DOSSIER_DAGS = Path(__file__).resolve().parents[1] / "dags"


def charger() -> DagBag:
    """DagBag du dossier du projet (Airflow 3.3 : les exemples dépendent de LOAD_EXAMPLES)."""
    return DagBag(dag_folder=str(DOSSIER_DAGS))


def test_dagbag_sans_erreur_d_import() -> None:
    """Tous les DAG du dossier se chargent sans erreur d'import, sans DAG d'exemple."""
    dagbag = charger()
    assert dagbag.import_errors == {}
    assert set(dagbag.dag_ids) == {"imf_quotidien"}


ETAPES = [
    "verifier_environnement",
    "attendre_fichiers",
    "ingerer",
    "controler_completude",
    "controler_volume",
    "dbt_build",
]


def dag_imf() -> Any:
    dag = charger().get_dag("imf_quotidien")
    assert dag is not None
    return dag


def test_dag_imf_quotidien_present() -> None:
    """Le DAG imf_quotidien est présent et commence par verifier_environnement."""
    dag = dag_imf()
    assert "verifier_environnement" in dag.task_ids
    assert dag.get_task("verifier_environnement").upstream_task_ids == set()


def test_planning() -> None:
    """@daily, du 01/01 au 31/12 de l'exercice (configuration), sans rattrapage automatique."""
    dag = dag_imf()
    exercice = int(os.environ["IMF_EXERCICE"])
    # Airflow 3.3 : @daily devient un CronTriggerTimetable « 0 0 * * * ».
    assert dag.timetable.expression == "0 0 * * *"
    assert (dag.start_date.date(), dag.end_date.date()) == (
        date(exercice, 1, 1),
        date(exercice, 12, 31),
    )
    assert dag.catchup is False
    assert dag.max_active_runs == 1


def test_parametres_des_taches() -> None:
    """Chaque tâche : depends_on_past, 2 retries espacés de 2 min avec backoff exponentiel."""
    for t in dag_imf().tasks:
        assert t.depends_on_past is True, t.task_id
        assert t.retries == 2, t.task_id
        assert t.retry_delay == timedelta(minutes=2), t.task_id
        assert t.retry_exponential_backoff, t.task_id


def test_ordre_des_taches() -> None:
    """Chaîne verifier_environnement → … → dbt_build, chaque étape suivie de la précédente."""
    dag = dag_imf()
    for amont, aval in zip(ETAPES, ETAPES[1:], strict=False):
        assert dag.get_task(aval).upstream_task_ids >= {amont}, aval
    assert set(dag.task_ids) == {*ETAPES, "ecrire_audit"}


def test_teardown_present() -> None:
    """ecrire_audit est un teardown, en aval de toutes les étapes."""
    dag = dag_imf()
    fin = dag.get_task("ecrire_audit")
    assert fin.is_teardown
    assert fin.upstream_task_ids == set(ETAPES)


def test_capteur_en_mode_reschedule() -> None:
    capteur = dag_imf().get_task("attendre_fichiers")
    assert capteur.mode == "reschedule"
    assert capteur.poke_interval == 60
    assert capteur.timeout == 3600
