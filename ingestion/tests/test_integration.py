"""Tests d'intégration de l'ingestion bronze (PostgreSQL requis : make up)."""

import json
from collections.abc import Iterator
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from generator.__main__ import Generation
from ingestion import chargement
from ingestion.__main__ import main
from ingestion.config import (
    CHARGE,
    IGNORE,
    INSTANTANES,
    PARTITIONS,
    TABLES_OPS,
    VIDE,
    ErreurIngestion,
    ObjetCsv,
    ObjetOps,
)
from ingestion.fenetre import jours_entre, jours_exercice
from ingestion.tests.conftest import Environnement, creer_environnement, supprimer_base

pytestmark = pytest.mark.integration

TOUS: tuple[ObjetCsv | ObjetOps, ...] = (*INSTANTANES, *PARTITIONS, *TABLES_OPS)


def _jours_avec_fichier(env: Environnement, objet: str) -> list[date]:
    return sorted(
        date.fromisoformat(p.parent.name.removeprefix("date="))
        for p in (env.source / objet).glob(f"date=*/{objet}.csv")
    )


def test_colonnes_ddl_conformes_a_la_config(env: Environnement) -> None:
    """Les colonnes métier du DDL bronze sont celles que le chargeur attend."""
    env.ingerer([date(2025, 1, 1)])
    for objet in TOUS:
        colonnes = [
            r[0]
            for r in env.requete(
                "SELECT column_name FROM information_schema.columns WHERE table_schema = 'bronze' "
                "AND table_name = %s AND column_name NOT LIKE '\\_%%' ORDER BY ordinal_position",
                (objet.table,),
            )
        ]
        assert tuple(colonnes) == objet.colonnes, objet.table


def test_doublons_exacts_restent_visibles(env: Environnement) -> None:
    """DOUBLON_EXACT : chaque id dupliqué apparaît (nombre + 1) fois dans csv_operations."""
    catalogue = [c for c in env.generation.brut.catalogue if c.nature == "DOUBLON_EXACT"]
    dates = {o.id_operation: o.date_operation for o in env.generation.brut.operations}
    env.ingerer(sorted({dates[c.id_ligne] for c in catalogue}))
    for c in catalogue:
        nb = env.requete(
            "SELECT count(*) FROM bronze.csv_operations WHERE id_operation = %s", (c.id_ligne,)
        )[0][0]
        assert nb == c.nombre + 1, c.id_ligne


def test_fichier_modifie_remplace_la_partition(env: Environnement) -> None:
    """SHA-256 différent : la partition est remplacée (DELETE + COPY), pas ajoutée."""
    jour = _jours_avec_fichier(env, "operations")[10]
    relatif = f"operations/date={jour.isoformat()}/operations.csv"
    env.ingerer([jour])
    avant = env.compter("csv_operations")
    fichier = env.source / relatif
    lignes = fichier.read_text(encoding="utf-8").splitlines(keepends=True)
    assert len(lignes) >= 3
    fichier.write_text("".join(lignes[:-1]), encoding="utf-8")  # une ligne de moins

    journal = env.ingerer([jour])
    statut = {ligne.objet: ligne for ligne in journal}["operations"]
    assert statut.statut == CHARGE and statut.nb_lignes == len(lignes) - 2
    assert env.compter("csv_operations") == avant - 1
    shas = env.requete(
        "SELECT DISTINCT _sha256, _id_run FROM bronze.csv_operations WHERE _source = %s",
        (relatif,),
    )
    assert shas == [(chargement.sha256_fichier(fichier), f"{jour.isoformat()}#2")]


def test_mise_a_jour_d_un_credit_ajoute_une_version(env: Environnement) -> None:
    """UPDATE dans imf_ops (statut + date_maj plus tard) : 2e version, la 1re reste."""
    jour = date(2025, 6, 30)
    env.ingerer([jour])  # un seul run extrait tout jusqu'au 30/06 inclus
    id_credit, statut = env.requete(
        "SELECT id_credit, statut FROM bronze.ops_credits WHERE statut = 'EN_COURS' "
        "ORDER BY id_credit LIMIT 1"
    )[0]
    nouvelle_date = datetime.combine(jour + timedelta(days=1), datetime.min.time()).replace(hour=20)
    env.executer_ops(
        "UPDATE credits SET statut = 'SOLDE', date_maj = %s WHERE id_credit = %s",
        (nouvelle_date, id_credit),
    )
    env.ingerer([jour + timedelta(days=1)])
    versions = env.requete(
        "SELECT statut, date_maj FROM bronze.ops_credits WHERE id_credit = %s ORDER BY date_maj",
        (id_credit,),
    )
    assert len(versions) == 2
    assert versions[0][0] == statut and versions[0][1] < nouvelle_date
    assert versions[1] == ("SOLDE", nouvelle_date)


def test_panne_au_milieu_d_un_jour(env: Environnement, monkeypatch: pytest.MonkeyPatch) -> None:
    """Panne pendant le jour J : rien n'est commité (données, filigranes, journal)."""
    # Un jour avec une partition d'opérations ET des adhésions (lignes ops_clients à charger).
    adhesions = {c.date_adhesion for c in env.generation.brut.clients}
    jour = [j for j in _jours_avec_fichier(env, "operations") if j in adhesions][5]
    env.ingerer(jours_entre(date(2025, 1, 1), jour - timedelta(days=1)))
    avant = env.etat()

    vrai_chargeur = chargement.charger_fichier
    appels: list[str] = []

    def chargeur_en_panne(*args: Any, **kwargs: Any) -> chargement.Resultat:
        table: str = args[1]
        appels.append(table)
        # Panne au premier chargement imf_ops, après la partition CSV déjà chargée.
        if table.startswith("ops_"):
            raise RuntimeError("panne simulée")
        return vrai_chargeur(*args, **kwargs)

    monkeypatch.setattr(chargement, "charger_fichier", chargeur_en_panne)
    with pytest.raises(RuntimeError, match="panne simulée"):
        env.ingerer([jour])
    assert "csv_operations" in appels and appels[-1].startswith("ops_")
    assert env.etat() == avant

    monkeypatch.setattr(chargement, "charger_fichier", vrai_chargeur)
    journal = env.ingerer([jour])
    assert journal[0].id_run == f"{jour.isoformat()}#1"  # le run en panne n'a rien laissé
    assert env.etat() != avant


def test_fichier_liste_au_manifeste_mais_absent(env: Environnement) -> None:
    jour = _jours_avec_fichier(env, "charges")[0]
    (env.source / f"charges/date={jour.isoformat()}/charges.csv").unlink()
    with pytest.raises(ErreurIngestion, match="listé dans le manifeste mais absent"):
        env.ingerer([jour])
    assert env.compter("csv_charges") == 0
    assert env.requete("SELECT count(*) FROM bronze._ingestions")[0][0] == 0


def test_jour_sans_fichier_ni_entree(env: Environnement) -> None:
    """Aucune partition ce jour-là et rien dans le manifeste : statut VIDE, 0 ligne."""
    occupes = {j for p in PARTITIONS for j in _jours_avec_fichier(env, p.objet)}
    jour = next(j for j in jours_entre(date(2025, 1, 2), date(2025, 12, 31)) if j not in occupes)
    journal = {ligne.objet: ligne for ligne in env.ingerer([jour])}
    for p in PARTITIONS:
        assert (journal[p.objet].statut, journal[p.objet].nb_lignes) == (VIDE, 0)
        assert journal[p.objet].chemin is None


def test_instantanes_ignores_s_ils_n_ont_pas_change(env: Environnement) -> None:
    journal = env.ingerer([date(2025, 1, 1), date(2025, 1, 2)])
    statuts = {(ligne.jour, ligne.objet): ligne.statut for ligne in journal}
    for objet in INSTANTANES:
        assert statuts[date(2025, 1, 1), objet.objet] == CHARGE
        assert statuts[date(2025, 1, 2), objet.objet] == IGNORE
    assert env.compter("csv_agences") == 6


def test_empreinte_differente(env: Environnement) -> None:
    env.ingerer([date(2025, 1, 1)])
    chemin = env.source / "_manifest.json"
    manifeste = json.loads(chemin.read_text(encoding="utf-8"))
    manifeste["parametres"]["seed"] = 7
    chemin.write_text(json.dumps(manifeste), encoding="utf-8")
    with pytest.raises(ErreurIngestion, match="autre génération : make reset-bronze"):
        env.ingerer([date(2025, 1, 2)])


def test_cli_code_de_sortie(env: Environnement, monkeypatch: pytest.MonkeyPatch) -> None:
    """La CLI renvoie 0 si tout passe, 1 avec un message clair en cas d'erreur."""
    monkeypatch.setenv("POSTGRES_DB_OPS", env.parametres.base_ops)
    monkeypatch.setenv("POSTGRES_DB_DWH", env.parametres.base_dwh)
    source = str(env.source)
    assert main(["--du", "2025-01-01", "--au", "2025-01-03", "--source", source]) == 0
    jour = _jours_avec_fichier(env, "operations")[-1]
    (env.source / f"operations/date={jour.isoformat()}/operations.csv").unlink()
    assert main(["--date", jour.isoformat(), "--source", source]) == 1


def _ops_metier(env: Environnement) -> dict[str, list[tuple[Any, ...]]]:
    """Contenu métier des tables ops_* (sans colonnes techniques), trié."""
    contenu = {}
    for objet in TABLES_OPS:
        colonnes = ", ".join(objet.colonnes)
        contenu[objet.table] = env.requete(
            f"SELECT {colonnes} FROM bronze.{objet.table} ORDER BY {colonnes}"
        )
    return contenu


@pytest.fixture(scope="module")
def env_complet(
    generation_petite: Generation, tmp_path_factory: pytest.TempPathFactory
) -> Iterator[Environnement]:
    """Rattrapage complet jour par jour depuis le 01/01 (partagé par les tests slow)."""
    environnement = creer_environnement(
        generation_petite, "complet", tmp_path_factory.mktemp("complet")
    )
    environnement.ingerer(jours_exercice(generation_petite.config.exercice))
    yield environnement
    supprimer_base(environnement.parametres.base_ops)
    supprimer_base(environnement.parametres.base_dwh)


@pytest.mark.slow
def test_rattrapage_complet_volumes(env_complet: Environnement) -> None:
    """Nombre de lignes de chaque table bronze = volumes bruts du manifeste."""
    volumes = env_complet.generation.manifeste["lignes"]["brut"]
    for objet in TOUS:
        assert env_complet.compter(objet.table) == volumes[objet.objet], objet.table
    # Un run par jour, 12 objets par run.
    assert env_complet.requete("SELECT count(DISTINCT id_run) FROM bronze._ingestions")[0][0] == 365


@pytest.mark.slow
def test_run_au_31_12_puis_rattrapage(
    env_complet: Environnement, generation_petite: Generation, tmp_path: Path
) -> None:
    """Un run au 31/12 puis le rattrapage jour par jour = rattrapage depuis le 01/01."""
    autre = creer_environnement(generation_petite, "fin_annee", tmp_path)
    try:
        jours = jours_exercice(generation_petite.config.exercice)
        autre.ingerer([jours[-1]])
        autre.ingerer(jours)
        assert _ops_metier(autre) == _ops_metier(env_complet)
    finally:
        supprimer_base(autre.parametres.base_ops)
        supprimer_base(autre.parametres.base_dwh)
