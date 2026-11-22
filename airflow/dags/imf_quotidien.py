"""DAG quotidien du pipeline SenFinance Microcrédit (phase 7).

Lot B : une seule tâche, verifier_environnement, qui restera la première tâche du DAG final.
Les commandes du projet tournent dans le venv du projet (/opt/pipeline-venv), séparé de
l'environnement d'Airflow ; le dépôt est monté sur /opt/pipeline.
"""

from datetime import datetime

from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import DAG

VENV = "/opt/pipeline-venv/bin"
DEPOT = "/opt/pipeline"

# Vérifie l'environnement avant toute ingestion : dbt joint imf_dwh (profil lu dans les
# variables d'environnement, hôte = service postgres), la CLI d'ingestion se charge, et les
# deux environnements Python restent séparés.
VERIFIER_ENVIRONNEMENT = f"""
set -euo pipefail
cd {DEPOT}
{VENV}/dbt debug --project-dir dbt --profiles-dir dbt
{VENV}/python -m ingestion --help
! {VENV}/python -c "import airflow" 2>/dev/null
! python -c "import dbt" 2>/dev/null
echo "Environnement vérifié : dbt et ingestion dans le venv projet, Airflow à part."
"""

with DAG(
    dag_id="imf_quotidien",
    description="Pipeline quotidien SenFinance : ingestion bronze, dbt build, contrôles.",
    start_date=datetime(2025, 1, 1),
    # Déclenchement manuel tant que le DAG n'a que sa tâche de vérification (lot B).
    schedule=None,
    catchup=False,
    max_active_runs=1,
    tags=["imf", "phase7"],
) as dag:
    verifier_environnement = BashOperator(
        task_id="verifier_environnement",
        bash_command=VERIFIER_ENVIRONNEMENT,
    )
