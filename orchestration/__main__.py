"""CLI : python -m orchestration <commande> --date AAAA-MM-JJ [options].

Codes de sortie : 0 succès, 3 échec de contrôle (bloquant), 1 erreur technique (relançable).
La dernière ligne de stdout est le résumé JSON de la commande.
"""

import argparse
import json
import sys
from datetime import UTC, date, datetime
from pathlib import Path

import psycopg
from dotenv import load_dotenv

from ingestion.config import Parametres
from orchestration import audit
from orchestration.commandes import COMMANDES
from orchestration.resultats import (
    CODE_ERREUR_TECHNIQUE,
    ECHEC_TECHNIQUE,
    NON_EXECUTE,
    Resume,
    statut_global,
)


def lire_arguments(arguments: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m orchestration")
    parser.add_argument("commande", choices=[*COMMANDES, "audit"])
    parser.add_argument("--date", type=date.fromisoformat, required=True, help="jour J")
    parser.add_argument("--source", type=Path, default=Path("data"), help="dossier généré")
    # Options de la commande audit.
    parser.add_argument("--dag-id", default="imf_quotidien")
    parser.add_argument("--run-id", default="manuel")
    parser.add_argument("--etape", default="")
    parser.add_argument("--tentative", type=int, default=1)
    parser.add_argument("--statut", default=None, help="statut imposé (sinon celui du résumé)")
    parser.add_argument("--debut", type=datetime.fromisoformat, default=None)
    parser.add_argument("--fin", type=datetime.fromisoformat, default=None)
    parser.add_argument("--resume", default=None, help="résumé JSON de l'étape")
    parser.add_argument("--message", default=None)
    parser.add_argument(
        "--statuts",
        default=None,
        help="ligne RUN : JSON {étape: statut ou null}, statut global calculé",
    )
    return parser.parse_args(arguments)


def executer_audit(ns: argparse.Namespace, parametres: Parametres) -> Resume:
    """Écrit une ligne d'audit à partir du résumé JSON d'une étape (ou d'un statut imposé)."""
    maintenant = datetime.now(UTC)
    if ns.statuts:
        # Ligne RUN : statut global des étapes, détail de chaque étape dans le message.
        statuts: dict[str, str | None] = json.loads(ns.statuts)
        detail = ", ".join(f"{e}={s or NON_EXECUTE}" for e, s in statuts.items())
        resume = Resume("RUN", ns.date.isoformat(), statut_global(statuts), detail)
    elif ns.resume:
        valeurs = json.loads(ns.resume)
        resume = Resume(**valeurs)
    else:
        resume = Resume(ns.etape or "audit", ns.date.isoformat(), ns.statut or ECHEC_TECHNIQUE)
    if ns.message is not None:
        resume = Resume(**{**resume.__dict__, "message": ns.message})
    ligne = audit.construire_ligne(
        resume,
        dag_id=ns.dag_id,
        run_id=ns.run_id,
        etape=ns.etape or resume.commande,
        tentative=ns.tentative,
        debut=ns.debut or maintenant,
        fin=ns.fin or maintenant,
        statut=ns.statut,
    )
    etat = audit.ecrire(ligne, parametres)
    return Resume(
        "audit", ns.date.isoformat(), "SUCCES", f"ligne {ligne.etape}/{ligne.statut} {etat}"
    )


def main(arguments: list[str] | None = None) -> int:
    load_dotenv()
    ns = lire_arguments(arguments)
    parametres = Parametres.depuis_environnement(ns.source)
    try:
        if ns.commande == "audit":
            resume = executer_audit(ns, parametres)
        else:
            resume = COMMANDES[ns.commande](ns.date, parametres)
    except (psycopg.Error, OSError, ValueError) as erreur:
        # Erreur technique (base injoignable, fichier illisible…) : relançable.
        resume = Resume(
            ns.commande, ns.date.isoformat(), ECHEC_TECHNIQUE, f"{type(erreur).__name__} : {erreur}"
        )
        print(resume.json())
        return CODE_ERREUR_TECHNIQUE
    print(resume.json())
    return resume.code


if __name__ == "__main__":
    sys.exit(main())
