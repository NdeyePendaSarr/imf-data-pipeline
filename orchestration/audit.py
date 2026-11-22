"""Écriture du journal d'exécution audit.audit_runs (table en ajout seul).

Si PostgreSQL est injoignable (panne transitoire), la ligne est mise en attente dans
data/_audit_en_attente.jsonl, puis écrite au prochain appel qui joint la base : la tentative
en échec technique reste ainsi tracée.
"""

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

import psycopg

from ingestion.config import Parametres, parametres_connexion
from orchestration.resultats import Resume

DDL_AUDIT = Path(__file__).parent / "sql" / "audit.sql"
FICHIER_ATTENTE = "_audit_en_attente.jsonl"
DBT_PROJECT = Path("dbt") / "dbt_project.yml"


@dataclass(frozen=True)
class LigneAudit:
    """Une ligne de audit.audit_runs (colonnes dans l'ordre de la table, hors id_audit)."""

    dag_id: str
    run_id: str
    date_logique: date
    etape: str
    tentative: int
    statut: str
    debut: datetime
    fin: datetime
    duree_s: float
    lignes_chargees: int | None = None
    nb_pass: int | None = None
    nb_warn: int | None = None
    nb_error: int | None = None
    nb_skip: int | None = None
    noeuds_en_echec: list[str] = field(default_factory=list)
    noeuds_sautes: list[str] = field(default_factory=list)
    version_mapping: str | None = None
    commit_git: str | None = None
    message: str = ""


def version_mapping(racine: Path = Path(".")) -> str | None:
    """Var dbt version_mapping lue dans dbt_project.yml (sans dépendance YAML)."""
    chemin = racine / DBT_PROJECT
    if not chemin.exists():
        return None
    trouve = re.search(r"^\s*version_mapping:\s*['\"]?([^'\"\s#]+)", chemin.read_text(), re.M)
    return trouve.group(1) if trouve else None


def commit_git(racine: Path = Path(".")) -> str | None:
    """Commit courant lu dans .git (dépôt monté en lecture seule, sans binaire git requis)."""
    tete = racine / ".git" / "HEAD"
    if not tete.exists():
        return None
    contenu = tete.read_text().strip()
    if not contenu.startswith("ref: "):
        return contenu[:40]
    ref = contenu.removeprefix("ref: ")
    fichier_ref = racine / ".git" / ref
    if fichier_ref.exists():
        return fichier_ref.read_text().strip()[:40]
    paquets = racine / ".git" / "packed-refs"
    if paquets.exists():
        for ligne in paquets.read_text().splitlines():
            if ligne.endswith(" " + ref):
                return ligne.split(" ", 1)[0][:40]
    return None


def construire_ligne(
    resume: Resume,
    *,
    dag_id: str,
    run_id: str,
    etape: str,
    tentative: int,
    debut: datetime,
    fin: datetime,
    statut: str | None = None,
    racine: Path = Path("."),
) -> LigneAudit:
    """Ligne d'audit d'une tentative, à partir du résumé de la commande."""
    return LigneAudit(
        dag_id=dag_id,
        run_id=run_id,
        date_logique=date.fromisoformat(resume.date),
        etape=etape,
        tentative=tentative,
        statut=statut or resume.statut,
        debut=debut,
        fin=fin,
        duree_s=round((fin - debut).total_seconds(), 3),
        lignes_chargees=resume.lignes_chargees,
        nb_pass=resume.nb_pass,
        nb_warn=resume.nb_warn,
        nb_error=resume.nb_error,
        nb_skip=resume.nb_skip,
        noeuds_en_echec=list(resume.noeuds_en_echec),
        noeuds_sautes=list(resume.noeuds_sautes),
        version_mapping=version_mapping(racine),
        commit_git=commit_git(racine),
        message=resume.message,
    )


def _vers_json(ligne: LigneAudit) -> str:
    return json.dumps(asdict(ligne), ensure_ascii=False, sort_keys=True, default=str)


def _depuis_json(texte: str) -> LigneAudit:
    valeurs: dict[str, Any] = json.loads(texte)
    valeurs["date_logique"] = date.fromisoformat(valeurs["date_logique"])
    valeurs["debut"] = datetime.fromisoformat(valeurs["debut"])
    valeurs["fin"] = datetime.fromisoformat(valeurs["fin"])
    return LigneAudit(**valeurs)


def _inserer(conn: psycopg.Connection[Any], lignes: list[LigneAudit]) -> None:
    colonnes = list(asdict(lignes[0]))
    with conn.cursor() as cur:
        cur.executemany(
            f"INSERT INTO audit.audit_runs ({', '.join(colonnes)}) "
            f"VALUES ({', '.join(['%s'] * len(colonnes))})",
            [list(asdict(ligne).values()) for ligne in lignes],
        )


def ecrire(ligne: LigneAudit, parametres: Parametres) -> str:
    """Écrit la ligne (et les lignes en attente) ; renvoie « ecrite » ou « en_attente »."""
    attente = parametres.source / FICHIER_ATTENTE
    en_attente = (
        [_depuis_json(t) for t in attente.read_text(encoding="utf-8").splitlines() if t.strip()]
        if attente.exists()
        else []
    )
    try:
        with psycopg.connect(**parametres_connexion(parametres.base_dwh)) as conn:
            conn.execute(DDL_AUDIT.read_text(encoding="utf-8").encode())
            _inserer(conn, [*en_attente, ligne])
    except psycopg.OperationalError:
        # Base injoignable : la ligne est conservée et sera écrite au prochain appel.
        with attente.open("a", encoding="utf-8") as fichier:
            fichier.write(_vers_json(ligne) + "\n")
        return "en_attente"
    if attente.exists():
        attente.unlink()
    return "ecrite"
