"""Reprise du DAG imf_quotidien après un échec (environnement Airflow, make airflow-reprendre).

Avec depends_on_past et max_active_runs = 1, un jour en échec bloque la suite : le run du jour
suivant démarre (backfill ou planning), mais ses tâches attendent la réussite de la veille ;
il occupe l'unique place active, et le jour en échec, remis à zéro, ne peut plus démarrer.
Ce script remet à zéro les tâches du jour à partir de l'étape indiquée (et leur aval), vérifie
qu'elles l'ont bien été, puis remet en file les runs actifs postérieurs au jour : le scheduler
reprend dans l'ordre des dates.

Usage : python airflow/reprendre.py AAAA-MM-JJ [etape]   (etape par défaut : toutes)
"""

import subprocess
import sys
from collections.abc import Mapping
from datetime import date
from pathlib import Path

from airflow.dag_processing.dagbag import DagBag
from airflow.models import DagRun, TaskInstance
from airflow.utils.session import create_session
from airflow.utils.state import DagRunState

DAG_ID = "imf_quotidien"
DOSSIER_DAGS = Path(__file__).resolve().parent / "dags"
# États d'une tâche terminée : une tâche visée encore dans l'un d'eux n'a pas été remise à zéro.
ETATS_TERMINES = frozenset({"success", "failed", "upstream_failed", "skipped", "removed"})


def commande_clear(jour: date, etape: str | None) -> list[str]:
    """airflow tasks clear du jour, limité à l'étape et à son aval si elle est donnée."""
    commande = ["airflow", "tasks", "clear", DAG_ID, "-s", jour.isoformat(), "-e", jour.isoformat()]
    # Nom de tâche sans ancres : avec « ^…$ », airflow tasks clear 3.3 ne sélectionne rien et
    # ne signale aucune erreur (constaté sur la panne a du lot C).
    return commande + ["-y"] + (["-t", etape, "--downstream"] if etape else [])


def taches_visees(etape: str | None) -> set[str]:
    """L'étape et son aval dans le DAG (toutes les tâches si aucune étape)."""
    dag = DagBag(dag_folder=str(DOSSIER_DAGS)).dags[DAG_ID]
    if etape is None:
        return set(dag.task_ids)
    if etape not in dag.task_ids:
        raise SystemExit(f"Étape inconnue : {etape} (étapes : {', '.join(dag.task_ids)})")
    return {etape} | set(dag.get_task(etape).get_flat_relative_ids(upstream=False))


def non_remises(etats: Mapping[str, str | None], visees: set[str]) -> list[str]:
    """Tâches visées absentes du run ou encore dans un état terminé après le clear."""
    return sorted(t for t in visees if t not in etats or etats[t] in ETATS_TERMINES)


def etats_du_jour(jour: date) -> dict[str, str | None]:
    """État de chaque tâche du run du jour (aucune si le run n'existe pas)."""
    etats: dict[str, str | None] = {}
    with create_session() as session:
        runs = session.query(DagRun).filter(DagRun.dag_id == DAG_ID).all()
        for run in runs:
            if run.logical_date is None or run.logical_date.date() != jour:
                continue
            instances = session.query(TaskInstance).filter(
                TaskInstance.dag_id == DAG_ID, TaskInstance.run_id == run.run_id
            )
            for instance in instances:
                etat = instance.state
                etats[instance.task_id] = (
                    None if etat is None else str(etat.value if hasattr(etat, "value") else etat)
                )
    return etats


def remettre_en_file(jour: date) -> list[str]:
    """Runs actifs dont la date logique suit le jour : repassés en file d'attente."""
    remis: list[str] = []
    with create_session() as session:
        actifs = (
            session.query(DagRun)
            .filter(DagRun.dag_id == DAG_ID, DagRun.state == DagRunState.RUNNING)
            .all()
        )
        for run in actifs:
            if run.logical_date is not None and run.logical_date.date() > jour:
                run.state = DagRunState.QUEUED
                remis.append(run.run_id)
    return remis


def main() -> int:
    jour = date.fromisoformat(sys.argv[1])
    etape = sys.argv[2] if len(sys.argv) > 2 else None
    visees = taches_visees(etape)
    # D'abord le jour en échec (remis en file par le clear), ensuite les runs suivants : dans
    # l'ordre inverse, le scheduler relancerait un jour suivant avant le jour à reprendre.
    code = subprocess.run(commande_clear(jour, etape), check=False).returncode
    if code != 0:
        print(f"Erreur : airflow tasks clear a échoué (code {code})", file=sys.stderr)
        return code
    restantes = non_remises(etats_du_jour(jour), visees)
    if restantes:
        print(
            f"Erreur : tâche(s) du {jour.isoformat()} non remise(s) à zéro par le clear : "
            f"{', '.join(restantes)}. Aucun run suivant n'a été remis en file.",
            file=sys.stderr,
        )
        return 1
    print(f"{len(visees)} tâche(s) du {jour.isoformat()} remise(s) à zéro")
    for run_id in remettre_en_file(jour):
        print(f"remis en file : {run_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
