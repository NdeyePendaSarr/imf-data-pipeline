"""Paramètres de l'ingestion bronze : objets ingérés, chemins et connexions."""

import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

DDL_BRONZE = Path(__file__).parent / "sql" / "bronze.sql"
SCHEMA = "bronze"
MANIFESTE = "_manifest.json"
# Extractions de imf_ops, sous le dossier source : landing/imf_ops/<table>/date=J/<table>.csv
DOSSIER_LANDING = "landing/imf_ops"

# Sources du journal bronze._ingestions
SOURCE_CSV = "csv"
SOURCE_IMF_OPS = "imf_ops"
SOURCE_META = "meta"

# Statuts du journal
CHARGE = "CHARGE"
IGNORE = "IGNORE"
VIDE = "VIDE"


class ErreurIngestion(RuntimeError):
    """Erreur d'ingestion : le jour est annulé (rollback) et la commande sort en erreur."""


@dataclass(frozen=True)
class ObjetCsv:
    """Fichier CSV des agences : instantané (fichier unique) ou partition journalière."""

    objet: str
    table: str
    colonnes: tuple[str, ...]
    source: str
    partitionne: bool

    def chemin(self, jour: date) -> str:
        """Chemin relatif au dossier source (partition du jour J ou fichier unique)."""
        if self.partitionne:
            return f"{self.objet}/date={jour.isoformat()}/{self.objet}.csv"
        return f"{self.objet}.csv"


@dataclass(frozen=True)
class ObjetOps:
    """Table de imf_ops extraite par filigrane sur date_maj."""

    objet: str
    table: str
    colonnes: tuple[str, ...]
    cle: tuple[str, ...]

    def chemin(self, jour: date) -> str:
        """Fichier d'atterrissage (landing) de l'extraction du jour J."""
        return f"{DOSSIER_LANDING}/{self.objet}/date={jour.isoformat()}/{self.objet}.csv"


INSTANTANES: tuple[ObjetCsv, ...] = (
    ObjetCsv(
        "agences",
        "csv_agences",
        ("id_agence", "nom", "ville", "region", "type_agence"),
        SOURCE_CSV,
        False,
    ),
    ObjetCsv(
        "ouverture",
        "csv_ouverture",
        ("id_agence", "date_ouverture", "canal", "montant"),
        SOURCE_CSV,
        False,
    ),
    ObjetCsv(
        "catalogue_anomalies",
        "meta_catalogue_anomalies",
        ("nature", "table", "id_ligne", "nombre", "traitement_attendu"),
        SOURCE_META,
        False,
    ),
)

PARTITIONS: tuple[ObjetCsv, ...] = (
    ObjetCsv(
        "operations",
        "csv_operations",
        (
            "id_operation",
            "id_compte",
            "id_agence",
            "date_operation",
            "type_operation",
            "canal",
            "montant",
        ),
        SOURCE_CSV,
        True,
    ),
    ObjetCsv(
        "charges",
        "csv_charges",
        ("id_charge", "id_agence", "date_charge", "categorie", "canal", "montant"),
        SOURCE_CSV,
        True,
    ),
    ObjetCsv(
        "appro_caisse",
        "csv_appro_caisse",
        ("id_appro", "id_agence", "date_appro", "montant"),
        SOURCE_CSV,
        True,
    ),
)

# Tables de imf_ops, parents avant enfants.
TABLES_OPS: tuple[ObjetOps, ...] = (
    ObjetOps(
        "produits_credit",
        "ops_produits_credit",
        (
            "code_produit",
            "libelle",
            "taux_annuel",
            "taux_frais_dossier",
            "duree_min_mois",
            "duree_max_mois",
            "date_maj",
        ),
        ("code_produit",),
    ),
    ObjetOps(
        "clients",
        "ops_clients",
        (
            "id_client",
            "id_agence",
            "prenom",
            "nom",
            "sexe",
            "date_naissance",
            "secteur_activite",
            "date_adhesion",
            "date_maj",
        ),
        ("id_client",),
    ),
    ObjetOps(
        "comptes",
        "ops_comptes",
        ("id_compte", "id_client", "type_compte", "date_ouverture", "statut", "date_maj"),
        ("id_compte",),
    ),
    ObjetOps(
        "credits",
        "ops_credits",
        (
            "id_credit",
            "id_client",
            "id_compte_epargne",
            "code_produit",
            "date_decaissement",
            "montant_accorde",
            "frais_dossier",
            "duree_mois",
            "taux_annuel",
            "statut",
            "date_maj",
        ),
        ("id_credit",),
    ),
    ObjetOps(
        "echeancier",
        "ops_echeancier",
        (
            "id_credit",
            "num_echeance",
            "date_echeance",
            "capital",
            "interets",
            "montant",
            "date_maj",
        ),
        ("id_credit", "num_echeance"),
    ),
    ObjetOps(
        "remboursements",
        "ops_remboursements",
        (
            "id_remboursement",
            "id_credit",
            "date_remboursement",
            "montant_paye",
            "part_capital",
            "part_interets",
            "penalites",
            "canal",
            "date_maj",
        ),
        ("id_remboursement",),
    ),
)


@dataclass(frozen=True)
class Parametres:
    """Paramètres d'une exécution : dossier source et bases (lues dans l'environnement)."""

    source: Path
    base_ops: str
    base_dwh: str

    @classmethod
    def depuis_environnement(cls, source: Path) -> "Parametres":
        return cls(
            source=source,
            base_ops=os.getenv("POSTGRES_DB_OPS", "imf_ops"),
            base_dwh=os.getenv("POSTGRES_DB_DWH", "imf_dwh"),
        )


def parametres_connexion(dbname: str) -> dict[str, Any]:
    """Paramètres de connexion lus uniquement dans les variables d'environnement (.env)."""
    utilisateur = os.getenv("POSTGRES_USER")
    mot_de_passe = os.getenv("POSTGRES_PASSWORD")
    if not utilisateur or not mot_de_passe:
        raise ErreurIngestion(
            "POSTGRES_USER ou POSTGRES_PASSWORD absent : copie .env.example en .env"
        )
    return {
        "host": os.getenv("POSTGRES_HOST", "localhost"),
        "port": int(os.getenv("POSTGRES_PORT", "5433")),
        "user": utilisateur,
        "password": mot_de_passe,
        "dbname": dbname,
        "connect_timeout": 5,
    }
