"""Point d'entrée : uv run python -m ingestion (--date J | --du D --au A | --exercice)."""

import argparse
import json
import sys
import time
from collections import Counter
from collections.abc import Callable, Sequence
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import psycopg
from dotenv import load_dotenv
from psycopg import sql

from ingestion import chargement, extraction, journal
from ingestion.config import (
    CHARGE,
    DDL_BRONZE,
    IGNORE,
    INSTANTANES,
    MANIFESTE,
    PARTITIONS,
    SCHEMA,
    SOURCE_IMF_OPS,
    TABLES_OPS,
    VIDE,
    ErreurIngestion,
    ObjetCsv,
    Parametres,
    parametres_connexion,
)
from ingestion.fenetre import calculer_fenetre, jours_entre, jours_exercice, nouveau_filigrane
from ingestion.journal import LigneJournal


def maintenant() -> datetime:
    """Horodatage du journal (debut, fin) : seule dépendance à l'horloge."""
    return datetime.now(UTC)


def lire_manifeste(source: Path) -> dict[str, Any]:
    """Manifeste de la génération ; absent → erreur (rien à ingérer)."""
    chemin = source / MANIFESTE
    if not chemin.exists():
        raise ErreurIngestion(f"{chemin} introuvable : lance `make generate`")
    manifeste: dict[str, Any] = json.loads(chemin.read_text(encoding="utf-8"))
    return manifeste


def connecter(dbname: str) -> psycopg.Connection[Any]:
    """Connexion ; message clair si PostgreSQL est injoignable."""
    try:
        return psycopg.connect(**parametres_connexion(dbname))
    except psycopg.OperationalError as erreur:
        raise ErreurIngestion(
            f"PostgreSQL injoignable : lance `make up` (base {dbname} : {erreur})"
        ) from erreur


def _ingerer_csv(
    cur: psycopg.Cursor[Any],
    objet: ObjetCsv,
    jour: date,
    source: Path,
    manifeste: dict[str, Any],
    id_run: str,
    empreinte: str,
) -> LigneJournal:
    """Instantané ou partition du jour : IGNORE si le même SHA-256 est déjà chargé."""
    debut = maintenant()
    relatif = objet.chemin(jour)
    chemin = source / relatif

    def ligne(statut: str, nb: int, sha: str | None) -> LigneJournal:
        chemin_journal = relatif if sha is not None else None
        return LigneJournal(
            id_run, empreinte, jour, objet.source, objet.objet, chemin_journal, sha, nb,
            None, None, statut, debut, maintenant(),
        )  # fmt: skip

    if not chemin.exists():
        if relatif in manifeste.get("fichiers", {}):
            raise ErreurIngestion(f"{relatif} est listé dans le manifeste mais absent")
        return ligne(VIDE, 0, None)

    sha = chargement.sha256_fichier(chemin)
    table = sql.Identifier(SCHEMA, objet.table)
    # Instantané : toute la table ; partition : les lignes de ce fichier uniquement.
    filtre = (
        sql.SQL("WHERE _source = {}").format(sql.Literal(relatif))
        if objet.partitionne
        else sql.SQL("")
    )
    cur.execute(sql.SQL("SELECT DISTINCT _sha256 FROM {} {}").format(table, filtre))
    deja = {r[0] for r in cur.fetchall()}
    if deja == {sha}:
        return ligne(IGNORE, 0, sha)
    if deja:
        cur.execute(sql.SQL("DELETE FROM {} {}").format(table, filtre))
    resultat = chargement.charger_fichier(cur, objet.table, objet.colonnes, chemin, relatif, id_run)
    return ligne(CHARGE, resultat.nb_lignes, sha)


def _ingerer_ops(
    cur: psycopg.Cursor[Any],
    conn_ops: psycopg.Connection[Any],
    jour: date,
    source: Path,
    id_run: str,
    empreinte: str,
) -> list[LigneJournal]:
    """Tables de imf_ops : extraction de la fenêtre du jour vers landing, puis chargement."""
    lignes: list[LigneJournal] = []
    for objet in TABLES_OPS:
        debut = maintenant()
        avant = journal.lire_filigrane(cur, objet.objet)
        fenetre = calculer_fenetre(avant, jour)
        relatif = objet.chemin(jour)
        nb_extrait = extraction.extraire(conn_ops, objet, fenetre, source / relatif)
        if nb_extrait == 0:
            lignes.append(
                LigneJournal(
                    id_run,
                    empreinte,
                    jour,
                    SOURCE_IMF_OPS,
                    objet.objet,
                    None,
                    None,
                    0,
                    avant,
                    avant,
                    VIDE,
                    debut,
                    maintenant(),
                )  # fmt: skip
            )
            continue
        resultat = chargement.charger_fichier(
            cur, objet.table, objet.colonnes, source / relatif, relatif, id_run, objet.cle
        )
        apres = nouveau_filigrane(avant, resultat.max_date_maj)
        if apres is not None and apres != avant:
            journal.ecrire_filigrane(cur, objet.objet, apres)
        lignes.append(
            LigneJournal(
                id_run,
                empreinte,
                jour,
                SOURCE_IMF_OPS,
                objet.objet,
                relatif,
                resultat.sha256,
                resultat.nb_lignes,
                avant,
                apres,
                CHARGE,
                debut,
                maintenant(),
            )  # fmt: skip
        )
    return lignes


def ingerer_jour(
    conn_dwh: psycopg.Connection[Any],
    conn_ops: psycopg.Connection[Any],
    parametres: Parametres,
    manifeste: dict[str, Any],
    jour: date,
) -> list[LigneJournal]:
    """Ingère le jour J dans UNE transaction : données, filigranes et journal, ou rien."""
    empreinte = journal.empreinte_generation(manifeste)
    with conn_dwh.transaction(), conn_dwh.cursor() as cur:
        journal.verifier_empreinte(cur, empreinte)
        id_run = journal.prochain_id_run(cur, jour)
        lignes = [
            _ingerer_csv(cur, objet, jour, parametres.source, manifeste, id_run, empreinte)
            for objet in (*INSTANTANES, *PARTITIONS)
        ]
        lignes += _ingerer_ops(cur, conn_ops, jour, parametres.source, id_run, empreinte)
        journal.enregistrer(cur, lignes)
    return lignes


def ingerer(
    jours: Sequence[date],
    parametres: Parametres,
    rapport: Callable[[date, list[LigneJournal]], None] | None = None,
) -> list[LigneJournal]:
    """Ingère les jours dans l'ordre (rattrapage jour par jour) ; s'arrête à la 1re erreur.

    Les jours déjà traités restent commités ; le jour en erreur est entièrement annulé.
    """
    manifeste = lire_manifeste(parametres.source)
    tout: list[LigneJournal] = []
    with connecter(parametres.base_dwh) as conn_dwh, connecter(parametres.base_ops) as conn_ops:
        conn_ops.autocommit = True  # lectures seules, une requête par table
        with conn_dwh.transaction():
            conn_dwh.execute(DDL_BRONZE.read_text(encoding="utf-8").encode())
        for jour in jours:
            lignes = ingerer_jour(conn_dwh, conn_ops, parametres, manifeste, jour)
            if rapport is not None:
                rapport(jour, lignes)
            tout += lignes
    return tout


def resumer(lignes: Sequence[LigneJournal]) -> str:
    """Résumé d'un run : nombre d'objets par statut et lignes chargées."""
    statuts = Counter(ligne.statut for ligne in lignes)
    total = sum(ligne.nb_lignes for ligne in lignes)
    detail = ", ".join(f"{s} {statuts[s]}" for s in (CHARGE, IGNORE, VIDE) if statuts[s])
    return f"{lignes[0].id_run} : {detail} ; {total} lignes chargées"


def lire_arguments(arguments: list[str] | None) -> tuple[list[date], Path]:
    """Analyse la ligne de commande ; renvoie les jours à ingérer et le dossier source."""
    parser = argparse.ArgumentParser(
        prog="python -m ingestion", description="Ingestion bronze incrémentale et idempotente."
    )
    groupe = parser.add_mutually_exclusive_group(required=True)
    groupe.add_argument("--date", type=date.fromisoformat, help="un jour J (AAAA-MM-JJ)")
    groupe.add_argument("--du", type=date.fromisoformat, help="premier jour d'une période")
    groupe.add_argument("--exercice", action="store_true", help="tous les jours de l'exercice")
    parser.add_argument("--au", type=date.fromisoformat, help="dernier jour (avec --du)")
    parser.add_argument("--source", type=Path, default=Path("data"), help="dossier généré")
    ns = parser.parse_args(arguments)
    if (ns.du is None) != (ns.au is None):
        parser.error("--du et --au vont ensemble")
    if ns.date is not None:
        return [ns.date], ns.source
    if ns.du is not None:
        try:
            return jours_entre(ns.du, ns.au), ns.source
        except ValueError as erreur:
            parser.error(str(erreur))
    exercice = int(lire_manifeste(ns.source)["parametres"]["exercice"])
    return jours_exercice(exercice), ns.source


def main(arguments: list[str] | None = None) -> int:
    """Exécute l'ingestion et affiche un résumé par jour ; code ≠ 0 en cas d'erreur."""
    load_dotenv()
    debut = time.perf_counter()
    try:
        jours, source = lire_arguments(arguments)
        parametres = Parametres.depuis_environnement(source)

        def afficher(jour: date, lignes: list[LigneJournal]) -> None:
            # Rattrapage long : un résumé par mois, plus le dernier jour.
            if len(jours) <= 31 or jour.day == 1 or jour == jours[-1]:
                print(resumer(lignes))

        ingerer(jours, parametres, afficher)
    except (ErreurIngestion, psycopg.Error) as erreur:
        print(
            f"Erreur : {erreur} (jour annulé, rien n'a été commité pour ce jour)", file=sys.stderr
        )
        return 1
    print(f"{len(jours)} jour(s) ingéré(s) en {time.perf_counter() - debut:.1f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
