"""Commandes de l'orchestration : fichiers, bronze, dbt (venv du projet, sans Airflow)."""

import csv
import importlib.util
import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any

import psycopg

from ingestion import __main__ as ingestion_cli
from ingestion.config import (
    MANIFESTE,
    PARTITIONS,
    TABLES_OPS,
    ErreurIngestion,
    Parametres,
    parametres_connexion,
)
from orchestration.resultats import (
    ECHEC_CONTROLE,
    ECHEC_TECHNIQUE,
    SUCCES,
    Resume,
    evaluer_completude,
    evaluer_run_results,
    evaluer_volume,
)

DBT_OPTIONS = ["--project-dir", "dbt", "--profiles-dir", "dbt"]


def _manifeste(parametres: Parametres) -> dict[str, Any]:
    chemin = parametres.source / MANIFESTE
    if not chemin.exists():
        raise FileNotFoundError(f"{chemin} introuvable : lance `make generate`")
    contenu: dict[str, Any] = json.loads(chemin.read_text(encoding="utf-8"))
    return contenu


def _fichiers_du_jour(manifeste: dict[str, Any], jour: date) -> list[str]:
    """Partitions CSV déclarées par le manifeste pour le jour J."""
    segment = f"/date={jour.isoformat()}/"
    return sorted(chemin for chemin in manifeste["fichiers"] if segment in chemin)


def _connexion(parametres: Parametres) -> psycopg.Connection[Any]:
    return psycopg.connect(**parametres_connexion(parametres.base_dwh))


def verifier(jour: date, parametres: Parametres) -> Resume:
    """dbt debug, CLI d'ingestion chargeable, et Airflow absent du venv du projet."""
    # « airflow.models » et non « airflow » : depuis /opt/pipeline, le dossier airflow/ du dépôt
    # (DAG, Dockerfile) serait pris pour un paquet d'espace de noms.
    if importlib.util.find_spec("airflow.models") is not None:
        return Resume(
            "verifier", jour.isoformat(), ECHEC_CONTROLE, "Airflow présent dans le venv du projet"
        )
    dbt = Path(sys.executable).parent / "dbt"
    debug = subprocess.run([str(dbt), "debug", *DBT_OPTIONS], stdout=sys.stderr, check=False)
    if debug.returncode != 0:
        return Resume(
            "verifier", jour.isoformat(), ECHEC_TECHNIQUE, f"dbt debug : code {debug.returncode}"
        )
    aide = subprocess.run(
        [sys.executable, "-m", "ingestion", "--help"], stdout=sys.stderr, check=False
    )
    if aide.returncode != 0:
        return Resume(
            "verifier", jour.isoformat(), ECHEC_TECHNIQUE, "python -m ingestion --help en échec"
        )
    return Resume(
        "verifier",
        jour.isoformat(),
        SUCCES,
        "dbt debug OK, CLI d'ingestion OK, Airflow absent du venv",
    )


def attendre(jour: date, parametres: Parametres) -> Resume:
    """Prêt si tous les fichiers déclarés par le manifeste pour le jour J existent."""
    fichiers = _fichiers_du_jour(_manifeste(parametres), jour)
    manquants = [f for f in fichiers if not (parametres.source / f).exists()]
    return Resume(
        "attendre",
        jour.isoformat(),
        SUCCES,
        f"{len(fichiers) - len(manquants)}/{len(fichiers)} fichier(s) présent(s)",
        details={"pret": not manquants, "manquants": manquants},
    )


def ingerer(jour: date, parametres: Parametres) -> Resume:
    """Ingestion bronze du jour J (même code que python -m ingestion --date J)."""
    try:
        lignes = ingestion_cli.ingerer([jour], parametres)
    except ErreurIngestion as erreur:
        # Base injoignable : transitoire, relançable ; sinon donnée incohérente : bloquant.
        transitoire = isinstance(erreur.__cause__, psycopg.OperationalError)
        statut = ECHEC_TECHNIQUE if transitoire else ECHEC_CONTROLE
        return Resume("ingerer", jour.isoformat(), statut, str(erreur))
    total = sum(ligne.nb_lignes for ligne in lignes)
    statuts = sorted({ligne.statut for ligne in lignes})
    return Resume(
        "ingerer", jour.isoformat(), SUCCES, f"{total} lignes chargées ({', '.join(statuts)})",
        lignes_chargees=total,
    )  # fmt: skip


def _lignes_csv(chemin: Path) -> int:
    with chemin.open(encoding="utf-8", newline="") as fichier:
        return max(sum(1 for _ in csv.reader(fichier)) - 1, 0)


def completude(jour: date, parametres: Parametres) -> Resume:
    """Lignes en bronze = lignes du manifeste (CSV du jour) et = lignes de landing (imf_ops)."""
    manifeste = _manifeste(parametres)
    lignes_fichiers: dict[str, int] = manifeste.get("lignes_fichiers", {})
    attendu: dict[str, int] = {}
    tables: dict[str, str] = {}
    for objet in PARTITIONS:
        chemin = objet.chemin(jour)
        if chemin in lignes_fichiers:
            attendu[chemin] = lignes_fichiers[chemin]
            tables[chemin] = objet.table
    for objet_ops in TABLES_OPS:
        chemin = objet_ops.chemin(jour)
        if (parametres.source / chemin).exists():
            attendu[chemin] = _lignes_csv(parametres.source / chemin)
            tables[chemin] = objet_ops.table
    with _connexion(parametres) as conn:
        ligne = conn.execute(
            "SELECT count(*) FROM bronze._ingestions WHERE jour = %s", (jour,)
        ).fetchone()
        jour_ingere = bool(ligne and ligne[0])
        charge = {}
        for chemin, table in tables.items():
            resultat = conn.execute(
                f"SELECT count(*) FROM bronze.{table} WHERE _source = %s".encode(), (chemin,)
            ).fetchone()
            charge[chemin] = int(resultat[0]) if resultat else 0
    return evaluer_completude(jour, attendu, charge, jour_ingere)


def volumes_ingeres(conn: psycopg.Connection[Any], du: date, au: date) -> dict[date, int]:
    """Opérations par jour ingéré entre du et au (0 pour un jour ingéré sans fichier)."""
    ingeres = conn.execute(
        "SELECT DISTINCT jour FROM bronze._ingestions WHERE jour BETWEEN %s AND %s", (du, au)
    ).fetchall()
    volumes: dict[date, int] = {ligne[0]: 0 for ligne in ingeres}
    comptes = conn.execute(
        "SELECT substring(_source from 'date=([0-9-]+)/')::date AS jour, count(*) "
        "FROM bronze.csv_operations WHERE _source LIKE 'operations/date=%%' GROUP BY 1"
    ).fetchall()
    for jour_source, nombre in comptes:
        if jour_source in volumes:
            volumes[jour_source] = int(nombre)
    return volumes


def volume(jour: date, parametres: Parametres) -> Resume:
    """Opérations du jour vs référence corrigée de la tendance (avertissement seulement)."""
    with _connexion(parametres) as conn:
        volumes = volumes_ingeres(conn, date(jour.year, 1, 1), jour)
    return evaluer_volume(jour, dict(volumes))


def dbt(jour: date, parametres: Parametres) -> Resume:
    """dbt build arrêté au jour J, puis lecture de run_results.json."""
    cible = Path(os.getenv("DBT_TARGET_PATH", "dbt/target"))
    run_results = cible / "run_results.json"
    if run_results.exists():
        run_results.unlink()  # jamais le résultat d'un build précédent
    commande = [
        str(Path(sys.executable).parent / "dbt"),
        "build",
        *DBT_OPTIONS,
        "--vars",
        json.dumps({"date_arrete": jour.isoformat()}),
    ]
    execution = subprocess.run(commande, stdout=sys.stderr, check=False)
    contenu = json.loads(run_results.read_text(encoding="utf-8")) if run_results.exists() else None
    return evaluer_run_results(jour, execution.returncode, contenu)


COMMANDES = {
    "verifier": verifier,
    "attendre": attendre,
    "ingerer": ingerer,
    "completude": completude,
    "volume": volume,
    "dbt": dbt,
}
