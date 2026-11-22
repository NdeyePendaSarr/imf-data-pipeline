"""Reprise du DAG imf_quotidien après un échec (environnement Airflow, make airflow-reprendre).

Avec depends_on_past et max_active_runs = 1, un jour en échec bloque la suite : le run du jour
suivant démarre (backfill ou planning), mais ses tâches attendent la réussite de la veille ;
il occupe l'unique place active, et le jour en échec, remis à zéro, ne peut plus démarrer.
Ce script remet à zéro les tâches du jour à partir de l'étape indiquée (et leur aval), puis
remet en file les runs actifs postérieurs au jour : le scheduler reprend dans l'ordre des dates.

Usage : python airflow/reprendre.py AAAA-MM-JJ [etape]   (etape par défaut : toutes)
"""

import subprocess
import sys
from datetime import date

from airflow.models import DagRun
from airflow.utils.session import create_session
from airflow.utils.state import DagRunState

DAG_ID = "imf_quotidien"


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
    # D'abord le jour en échec (remis en file par le clear), ensuite les runs suivants : dans
    # l'ordre inverse, le scheduler relancerait un jour suivant avant le jour à reprendre.
    commande = ["airflow", "tasks", "clear", DAG_ID, "-s", jour.isoformat(), "-e", jour.isoformat()]
    # Nom de tâche sans ancres : avec « ^…$ », airflow tasks clear 3.3 ne sélectionne rien et
    # ne signale aucune erreur (constaté sur la panne a).
    commande += ["-y"] + (["-t", etape, "--downstream"] if etape else [])
    code = subprocess.run(commande, check=False).returncode
    for run_id in remettre_en_file(jour):
        print(f"remis en file : {run_id}")
    return code


if __name__ == "__main__":
    sys.exit(main())
