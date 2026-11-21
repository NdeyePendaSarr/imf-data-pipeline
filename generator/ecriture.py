"""Écriture des sorties : CSV bruts, vérité propre et manifeste."""

import csv
import hashlib
import json
import shutil
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import astuple, fields
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from generator.anomalies import Brut, LigneCatalogue
from generator.config import Config
from generator.simulation import (
    Agence,
    ApproCaisse,
    Charge,
    Client,
    Compte,
    Credit,
    Echeance,
    Operation,
    Ouverture,
    ProduitCredit,
    Remboursement,
    Verite,
)

MANIFESTE = "_manifest.json"
DOSSIER_VERITE = "_verite"

# Tables communes à la vérité et aux sorties brutes, dans l'ordre d'écriture, et leur classe.
CLASSES: dict[str, type[Any]] = {
    "agences": Agence,
    "clients": Client,
    "comptes": Compte,
    "produits_credit": ProduitCredit,
    "credits": Credit,
    "echeancier": Echeance,
    "remboursements": Remboursement,
    "operations": Operation,
    "charges": Charge,
    "ouverture": Ouverture,
    "appro_caisse": ApproCaisse,
}
TABLES = tuple(CLASSES)
# Tables brutes livrées en CSV : fichiers uniques (instantanés) et partitions journalières (I11).
TABLES_CSV_BRUTES = ("agences", "ouverture")
TABLES_PARTITIONNEES: dict[str, str] = {
    "operations": "date_operation",
    "charges": "date_charge",
    "appro_caisse": "date_appro",
}


def formater(valeur: object) -> str:
    """Valeur → texte CSV (NULL → vide, dates ISO, horodatage à la seconde)."""
    if valeur is None:
        return ""
    if isinstance(valeur, datetime):
        return valeur.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(valeur, date):
        return valeur.isoformat()
    if isinstance(valeur, Decimal):
        return str(valeur)
    return str(valeur)


def ecrire_csv(chemin: Path, classe: type[Any], lignes: Sequence[Any]) -> None:
    """Écrit un CSV UTF-8, séparateur virgule, fin de ligne LF, en-tête compris."""
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with chemin.open("w", encoding="utf-8", newline="") as fichier:
        writer = csv.writer(fichier, lineterminator="\n")
        writer.writerow([f.name for f in fields(classe)])
        for ligne in lignes:
            writer.writerow([formater(v) for v in astuple(ligne)])


# Tables chargées dans imf_ops (aucun fichier dans data/ : leur contenu est haché à part).
TABLES_IMF_OPS = (
    "produits_credit",
    "clients",
    "comptes",
    "credits",
    "echeancier",
    "remboursements",
)


def empreinte_lignes(classe: type[Any], lignes: Sequence[Any]) -> str:
    """SHA-256 du contenu d'une table, au format CSV canonique (en-tête + lignes formatées).

    Sert à l'empreinte de génération : une seule ligne de imf_ops modifiée change le manifeste,
    même si aucun fichier de data/ ne change (trou de I12 relevé en phase 4).
    """
    empreinte = hashlib.sha256()
    empreinte.update((",".join(f.name for f in fields(classe)) + "\n").encode("utf-8"))
    for ligne in lignes:
        empreinte.update(("\x1f".join(formater(v) for v in astuple(ligne)) + "\n").encode("utf-8"))
    return empreinte.hexdigest()


def sha256(chemin: Path) -> str:
    """Empreinte SHA-256 d'un fichier."""
    return hashlib.sha256(chemin.read_bytes()).hexdigest()


def preparer_sortie(sortie: Path) -> None:
    """Vide le dossier de sortie (aucun reste d'une exécution précédente).

    Par sécurité, un dossier non vide n'est supprimé que s'il contient un manifeste du
    générateur.
    """
    if sortie.exists():
        if any(sortie.iterdir()) and not (sortie / MANIFESTE).exists():
            raise FileExistsError(
                f"{sortie} n'est pas vide et ne vient pas du générateur : choisis un autre --sortie"
            )
        shutil.rmtree(sortie)
    sortie.mkdir(parents=True)


def ecrire_sorties(verite: Verite, brut: Brut, config: Config) -> dict[str, Any]:
    """Écrit data/ entièrement et renvoie le manifeste (écrit en dernier)."""
    sortie = config.sortie
    preparer_sortie(sortie)

    for table in TABLES:
        ecrire_csv(sortie / DOSSIER_VERITE / f"{table}.csv", CLASSES[table], getattr(verite, table))
    for table in TABLES_CSV_BRUTES:
        ecrire_csv(sortie / f"{table}.csv", CLASSES[table], getattr(brut, table))
    ecrire_csv(sortie / "catalogue_anomalies.csv", LigneCatalogue, brut.catalogue)

    # Opérations, charges et approvisionnements partitionnés par jour (I11) : un fichier par
    # jour avec des lignes, data/<table>/date=AAAA-MM-JJ/<table>.csv.
    nb_partitions: dict[str, int] = {}
    for table, colonne_date in TABLES_PARTITIONNEES.items():
        par_jour: dict[date, list[Any]] = defaultdict(list)
        for ligne in getattr(brut, table):
            par_jour[getattr(ligne, colonne_date)].append(ligne)
        for jour in sorted(par_jour):
            chemin = sortie / table / f"date={jour.isoformat()}" / f"{table}.csv"
            ecrire_csv(chemin, CLASSES[table], par_jour[jour])
        nb_partitions[f"partitions_{table}"] = len(par_jour)

    empreintes = {
        chemin.relative_to(sortie).as_posix(): sha256(chemin)
        for chemin in sorted(sortie.rglob("*"))
        if chemin.is_file() and chemin.name != MANIFESTE
    }
    ind = verite.indicateurs
    manifeste: dict[str, Any] = {
        "parametres": {
            "exercice": config.exercice,
            "clients": config.nb_clients,
            "credits": config.nb_credits,
            "seed": config.seed,
            "taux_anomalies": config.taux_anomalies,
        },
        "lignes": {
            "verite": {t: len(getattr(verite, t)) for t in TABLES},
            "brut": {t: len(getattr(brut, t)) for t in TABLES}
            | {"catalogue_anomalies": len(brut.catalogue)}
            | nb_partitions,
        },
        "indicateurs": {
            "par30_31_12": round(float(ind.par30), 6),
            "encours_total": ind.encours_total,
            "encours_par30": ind.encours_par30,
            "capital": ind.capital,
            "nb_approvisionnements": ind.nb_approvisionnements,
            "caisse_minimale": ind.caisse_minimale,
            "banque_minimale": ind.banque_minimale,
        },
        "fichiers": empreintes,
        # Contenu des tables chargées dans imf_ops (brut, anomalies comprises).
        "imf_ops": {
            table: empreinte_lignes(CLASSES[table], getattr(brut, table))
            for table in TABLES_IMF_OPS
        },
    }
    with (sortie / MANIFESTE).open("w", encoding="utf-8", newline="\n") as fichier:
        json.dump(manifeste, fichier, ensure_ascii=False, indent=2, sort_keys=True)
        fichier.write("\n")
    return manifeste
