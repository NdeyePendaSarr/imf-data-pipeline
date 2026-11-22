"""DAG quotidien du pipeline SenFinance Microcrédit (phase 7).

Un run = un jour J (logical_date) : verifier_environnement → attendre_fichiers → ingerer →
controler_completude → controler_volume → dbt_build, puis ecrire_audit (teardown).
Chaque tâche lance `python -m orchestration <commande> --date J` dans le venv du projet
(/opt/pipeline-venv, séparé d'Airflow ; dépôt monté sur /opt/pipeline). Contrat de sortie :
0 succès ; 3 échec de contrôle → AirflowFailException (aucun retry) ; autre → exception
ordinaire (retry). Chaque tentative écrit sa ligne dans audit.audit_runs et pousse son résumé
en XCom ; le teardown écrit la ligne RUN à partir des XCom (en Airflow 3, une tâche ne lit
pas la base de métadonnées).
"""

import importlib.util
import json
import os
import subprocess
from datetime import UTC, date, datetime, timedelta
from typing import Any

from airflow.sdk import DAG, PokeReturnValue, get_current_context, task, teardown
from airflow.sdk.exceptions import AirflowFailException

VENV_PYTHON = "/opt/pipeline-venv/bin/python"
DEPOT = "/opt/pipeline"
DAG_ID = "imf_quotidien"
# Exercice lu dans la configuration (docker-compose, IMF_EXERCICE), jamais codé en dur.
EXERCICE = int(os.environ["IMF_EXERCICE"])
CODE_ECHEC_CONTROLE = 3

# Étape du DAG → commande de l'orchestration, dans l'ordre d'exécution.
COMMANDES = {
    "verifier_environnement": "verifier",
    "attendre_fichiers": "attendre",
    "ingerer": "ingerer",
    "controler_completude": "completude",
    "controler_volume": "volume",
    "dbt_build": "dbt",
}


def _jour(context: Any) -> date:
    """Jour traité : la date logique du run ; échec immédiat si elle est absente."""
    logical_date = context.get("logical_date")
    if logical_date is None:
        raise AirflowFailException(
            "logical_date absente : ce DAG traite un jour donné (planning ou backfill)"
        )
    jour: date = logical_date.date()
    return jour


def _orchestration(arguments: list[str]) -> tuple[int, dict[str, Any]]:
    """Lance le CLI dans le venv du projet ; renvoie le code et le résumé JSON (dernière ligne)."""
    execution = subprocess.run(
        [VENV_PYTHON, "-m", "orchestration", *arguments],
        cwd=DEPOT,
        stdout=subprocess.PIPE,
        text=True,
        check=False,
    )
    lignes = execution.stdout.strip().splitlines()
    for ligne in lignes[:-1]:
        print(ligne)
    try:
        resume: dict[str, Any] = json.loads(lignes[-1])
    except (IndexError, json.JSONDecodeError):
        resume = {"statut": "ECHEC_TECHNIQUE", "message": "résumé JSON illisible"}
        return (execution.returncode or 1), resume
    print(json.dumps(resume, ensure_ascii=False))
    return execution.returncode, resume


def _auditer(context: Any, etape: str, resume: dict[str, Any], debut: datetime) -> None:
    """Ligne d'audit de la tentative ; une panne de l'audit ne masque jamais l'étape."""
    ti = context["ti"]
    code, retour = _orchestration([
        "audit", "--date", _jour(context).isoformat(), "--dag-id", DAG_ID,
        "--run-id", context["run_id"], "--etape", etape, "--tentative", str(ti.try_number),
        "--debut", debut.isoformat(), "--fin", datetime.now(UTC).isoformat(),
        "--resume", json.dumps(resume, ensure_ascii=False),
    ])  # fmt: skip
    if code != 0:
        print(f"Audit non écrit : {retour.get('message')}")


def _etape(etape: str) -> dict[str, Any]:
    """Exécute une étape : CLI, audit de la tentative, XCom, puis succès ou exception."""
    context = get_current_context()
    debut = datetime.now(UTC)
    code, resume = _orchestration([COMMANDES[etape], "--date", _jour(context).isoformat()])
    _auditer(context, etape, resume, debut)
    context["ti"].xcom_push(key="resume", value=resume)
    if code == CODE_ECHEC_CONTROLE:
        raise AirflowFailException(f"{etape} : échec de contrôle — {resume.get('message')}")
    if code != 0:
        raise RuntimeError(f"{etape} : erreur technique (code {code}) — {resume.get('message')}")
    return resume


@task
def verifier_environnement() -> dict[str, Any]:
    """dbt debug, CLI d'ingestion, et séparation des environnements (dbt absent d'Airflow)."""
    if importlib.util.find_spec("dbt") is not None:
        raise AirflowFailException("dbt est installé dans l'environnement d'Airflow")
    return _etape("verifier_environnement")


@task.sensor(mode="reschedule", poke_interval=60, timeout=3600)
def attendre_fichiers() -> PokeReturnValue:
    """Attend que tous les fichiers déclarés par le manifeste pour le jour J soient présents."""
    context = get_current_context()
    debut = datetime.now(UTC)
    code, resume = _orchestration(["attendre", "--date", _jour(context).isoformat()])
    if code != 0:
        raise RuntimeError(f"attendre_fichiers : erreur technique — {resume.get('message')}")
    pret = bool(resume.get("details", {}).get("pret"))
    if pret:
        _auditer(context, "attendre_fichiers", resume, debut)
        context["ti"].xcom_push(key="resume", value=resume)
    return PokeReturnValue(is_done=pret, xcom_value=resume)


@task
def ingerer() -> dict[str, Any]:
    return _etape("ingerer")


@task
def controler_completude() -> dict[str, Any]:
    return _etape("controler_completude")


@task
def controler_volume() -> dict[str, Any]:
    return _etape("controler_volume")


@task
def dbt_build() -> dict[str, Any]:
    return _etape("dbt_build")


@teardown
def ecrire_audit() -> None:
    """Ligne etape = RUN : statut global à partir des résumés en XCom (NON_EXECUTE sans résumé)."""
    context = get_current_context()
    ti = context["ti"]
    statuts: dict[str, str | None] = {}
    for etape in COMMANDES:
        resume = ti.xcom_pull(task_ids=etape, key="resume")
        statuts[etape] = resume.get("statut") if isinstance(resume, dict) else None
    code, retour = _orchestration([
        "audit", "--date", _jour(context).isoformat(), "--dag-id", DAG_ID,
        "--run-id", context["run_id"], "--etape", "RUN", "--tentative", str(ti.try_number),
        "--statuts", json.dumps(statuts),
    ])  # fmt: skip
    if code != 0:
        raise RuntimeError(f"ecrire_audit : {retour.get('message')}")


with DAG(
    dag_id=DAG_ID,
    description="Pipeline quotidien SenFinance : ingestion bronze, contrôles, dbt build, audit.",
    schedule="@daily",
    start_date=datetime(EXERCICE, 1, 1),
    end_date=datetime(EXERCICE, 12, 31),
    catchup=False,
    max_active_runs=1,
    default_args={
        # Un jour ne démarre que si le jour précédent a réussi (et sa tâche suivante aussi) :
        # après un échec de contrôle, l'ingestion des jours suivants n'est pas lancée.
        "depends_on_past": True,
        "wait_for_downstream": True,
        "retries": 2,
        "retry_delay": timedelta(minutes=2),
        "retry_exponential_backoff": 2.0,
        "max_retry_delay": timedelta(minutes=10),
    },
    tags=["imf", "phase7"],
) as dag:
    etapes = [
        verifier_environnement(),
        attendre_fichiers(),
        ingerer(),
        controler_completude(),
        controler_volume(),
        dbt_build(),
    ]
    for amont, aval in zip(etapes, etapes[1:], strict=False):
        amont >> aval
    # Le teardown s'exécute quoi qu'il arrive aux étapes, une fois toutes terminées.
    etapes >> ecrire_audit()
