"""Intégrité des DAG Airflow, lancée dans le conteneur Airflow (make test-airflow)."""

from pathlib import Path

from airflow.dag_processing.dagbag import DagBag

DOSSIER_DAGS = Path(__file__).resolve().parents[1] / "dags"


def charger() -> DagBag:
    """DagBag du dossier du projet (Airflow 3.3 : les exemples dépendent de LOAD_EXAMPLES)."""
    return DagBag(dag_folder=str(DOSSIER_DAGS))


def test_dagbag_sans_erreur_d_import() -> None:
    """Tous les DAG du dossier se chargent sans erreur d'import, sans DAG d'exemple."""
    dagbag = charger()
    assert dagbag.import_errors == {}
    assert set(dagbag.dag_ids) == {"imf_quotidien"}


def test_dag_imf_quotidien_present() -> None:
    """Le DAG imf_quotidien est présent et commence par verifier_environnement."""
    dag = charger().get_dag("imf_quotidien")
    assert dag is not None
    assert "verifier_environnement" in dag.task_ids
    assert dag.get_task("verifier_environnement").upstream_task_ids == set()
