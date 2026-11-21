"""Idempotence de l'ingestion bronze (PostgreSQL requis : make up)."""

from datetime import date
from typing import Any

import pytest

from ingestion.tests.conftest import TABLES_BRONZE, Environnement

pytestmark = pytest.mark.integration

# Colonnes techniques exclues de la comparaison : elles décrivent le run, pas la donnée.
COLONNES_EXCLUES = ("_charge_le", "_id_run")


def _donnees_et_filigranes(env: Environnement) -> dict[str, Any]:
    """Photographie des tables de données bronze (hors _charge_le et _id_run) et des filigranes.

    Le journal bronze._ingestions est volontairement exclu : il grandit à chaque run.
    """
    photo: dict[str, Any] = {}
    for table in TABLES_BRONZE:
        colonnes = [
            ligne[0]
            for ligne in env.requete(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'bronze' AND table_name = %s ORDER BY ordinal_position",
                (table,),
            )
            if ligne[0] not in COLONNES_EXCLUES
        ]
        liste = ", ".join(f'"{c}"' for c in colonnes)
        # Contenu complet trié : toute ligne ajoutée, supprimée ou modifiée change la photo.
        photo[table] = env.requete(f"SELECT {liste} FROM bronze.{table} ORDER BY {liste}")
    photo["_filigranes"] = env.requete(
        "SELECT table_source, filigrane FROM bronze._filigranes ORDER BY table_source"
    )
    return photo


def _jour_avec_les_deux_sources(env: Environnement) -> date:
    """Premier jour à partir du 01/03 avec un fichier operations ET des lignes imf_ops datées."""
    brut = env.generation.brut
    jours_ops: set[date] = set()
    for table in ("clients", "comptes", "credits", "echeancier", "remboursements"):
        jours_ops |= {ligne.date_maj.date() for ligne in getattr(brut, table)}
    candidats = sorted(
        j
        for j in jours_ops
        if j >= date(env.generation.config.exercice, 3, 1)
        and (env.source / f"operations/date={j.isoformat()}/operations.csv").exists()
    )
    assert candidats, "aucun jour n'a de données dans les deux sources"
    return candidats[0]


def test_relance_meme_jour(env: Environnement) -> None:
    """Relancer l'ingestion d'un jour déjà ingéré ne modifie pas le bronze.

    Préparer : un jour J avec des données dans les deux sources (CSV des agences et imf_ops).
    Agir : ingérer J deux fois, en photographiant le bronze après chaque run.
    Vérifier : le 1er run charge des lignes ; données et filigranes sont identiques après les
    deux runs ; le 2e run (« J#2 ») n'a que des statuts IGNORE ou VIDE dans le journal.
    """
    # --- Préparer -------------------------------------------------------------------------
    jour = _jour_avec_les_deux_sources(env)
    fichier = env.source / f"operations/date={jour.isoformat()}/operations.csv"
    # Le fichier du jour existe et contient au moins une ligne de données (en-tête exclu).
    assert fichier.exists() and len(fichier.read_text(encoding="utf-8").splitlines()) > 1
    # imf_ops contient des lignes dont date_maj tombe ce jour-là (vérifié en base, pas supposé).
    lignes_ops_du_jour = sum(
        env.requete_ops(f"SELECT count(*) FROM {table} WHERE date_maj::date = %s", (jour,))[0][0]
        for table in ("clients", "comptes", "credits", "echeancier", "remboursements")
    )
    assert lignes_ops_du_jour > 0

    # --- Agir -----------------------------------------------------------------------------
    premier_run = env.ingerer([jour])
    apres_premier = _donnees_et_filigranes(env)
    env.ingerer([jour])
    apres_second = _donnees_et_filigranes(env)

    # --- Vérifier -------------------------------------------------------------------------
    # Le 1er run a réellement chargé des lignes : sans cela le test prouverait « 0 = 0 ».
    assert sum(ligne.nb_lignes for ligne in premier_run) > 0
    # Il a chargé le fichier operations du jour et au moins une table de imf_ops.
    charges = {ligne.objet for ligne in premier_run if ligne.statut == "CHARGE"}
    assert "operations" in charges and charges & {"clients", "credits", "remboursements"}
    # Données bronze et filigranes strictement identiques après la relance.
    assert apres_second == apres_premier
    # Le journal du 2e run existe (un run a bien eu lieu) …
    statuts = env.requete(
        "SELECT objet, statut, nb_lignes FROM bronze._ingestions WHERE id_run = %s",
        (f"{jour.isoformat()}#2",),
    )
    assert len(statuts) == len(TABLES_BRONZE)
    # … et ne contient aucune ligne CHARGE : uniquement IGNORE ou VIDE, sans aucune ligne chargée.
    assert {statut for _, statut, _ in statuts} <= {"IGNORE", "VIDE"}
    assert all(nb == 0 for _, _, nb in statuts)
