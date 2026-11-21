"""Paramètres du générateur : options d'exécution et constantes métier.

Toutes les valeurs numériques du générateur (taux, seuils, montants, proportions) sont ici,
jamais en dur dans les autres modules. Les montants sont des entiers en francs CFA (XOF) ;
les taux stockés sont des Decimal (jamais de float stocké).
"""

from dataclasses import dataclass
from datetime import date, time
from decimal import Decimal
from pathlib import Path

# --------------------------------------------------------------------------------------------
# Options d'exécution (ligne de commande)
# --------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Config:
    """Options d'une exécution du générateur."""

    exercice: int = 2025
    nb_clients: int = 2000
    nb_credits: int = 3000
    seed: int = 42
    taux_anomalies: float = 0.01
    sortie: Path = Path("data")

    @property
    def debut(self) -> date:
        """Premier jour de l'exercice (année civile)."""
        return date(self.exercice, 1, 1)

    @property
    def fin(self) -> date:
        """Dernier jour de l'exercice, date d'arrêté des indicateurs."""
        return date(self.exercice, 12, 31)


# --------------------------------------------------------------------------------------------
# Calendrier
# --------------------------------------------------------------------------------------------

# Jours d'ouverture du guichet et des agents (lundi = 0 … samedi = 5) ; le mobile est ouvert
# tous les jours. Pas de jours fériés.
JOURS_OUVRES: frozenset[int] = frozenset({0, 1, 2, 3, 4, 5})

# Heure du date_maj déterministe : date de l'événement à 20:00:00.
HEURE_DATE_MAJ = time(20, 0, 0)

# --------------------------------------------------------------------------------------------
# Identifiants : préfixe + nombre de chiffres, tirés au hasard sans remise
# --------------------------------------------------------------------------------------------

CHIFFRES_IDS: dict[str, int] = {
    "AG": 3,
    "CLI": 7,
    "CPT": 7,
    "CRD": 7,
    "OPE": 8,
    "RMB": 8,
    "CHG": 7,
    "APP": 7,
}

# --------------------------------------------------------------------------------------------
# Agences : clés de referentiels.AGENCES
# --------------------------------------------------------------------------------------------

# Répartition des clients entre les agences régionales (le siège n'a pas de clients).
POIDS_CLIENTS_AGENCE: dict[str, float] = {
    "DAKAR": 0.30,
    "THIES": 0.20,
    "KAOLACK": 0.20,
    "SAINT_LOUIS": 0.15,
    "ZIGUINCHOR": 0.15,
}

# --------------------------------------------------------------------------------------------
# Clients et comptes
# --------------------------------------------------------------------------------------------

PART_FEMMES = 0.6
AGE_MIN_ADHESION = 18
AGE_MAX_ADHESION = 70

# Poids des secteurs d'activité, dans l'ordre de referentiels.SECTEURS.
POIDS_SECTEURS: tuple[float, ...] = (0.30, 0.18, 0.10, 0.07, 0.12, 0.08, 0.15)

# Part des clients qui ouvrent aussi un compte COURANT à l'adhésion.
PART_COMPTE_COURANT = 0.15

# --------------------------------------------------------------------------------------------
# Produits de crédit
# --------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class ParametresProduit:
    """Caractéristiques d'un produit de crédit."""

    code: str
    libelle: str
    taux_annuel: Decimal
    taux_frais_dossier: Decimal
    duree_min_mois: int
    duree_max_mois: int
    # Mois de décaissement autorisés (None : toute l'année)
    mois_decaissement: tuple[int, int] | None
    montant_min: int
    montant_max: int
    # Part du produit dans le nombre annuel de crédits (somme des parts = 1)
    part_annuelle: float


PRODUITS: tuple[ParametresProduit, ...] = (
    ParametresProduit(
        "AGR",
        "Activité génératrice de revenus",
        Decimal("0.15"),
        Decimal("0.015"),
        6,
        12,
        None,
        100_000,
        1_500_000,
        0.465,
    ),
    ParametresProduit(
        "AGRICOLE",
        "Crédit de campagne agricole",
        Decimal("0.14"),
        Decimal("0.015"),
        6,
        9,
        (5, 7),
        100_000,
        800_000,
        0.12,
    ),
    ParametresProduit(
        "SCOLAIRE",
        "Crédit rentrée scolaire",
        Decimal("0.12"),
        Decimal("0.01"),
        6,
        10,
        (8, 10),
        50_000,
        400_000,
        0.13,
    ),
    ParametresProduit(
        "EQUIPEMENT",
        "Crédit d'équipement",
        Decimal("0.16"),
        Decimal("0.02"),
        12,
        24,
        None,
        300_000,
        3_000_000,
        0.285,
    ),
)

# Montants accordés : multiples de ce pas.
PAS_MONTANT_CREDIT = 5_000
# Délai minimal entre l'ouverture du compte et le premier décaissement.
DELAI_MIN_CREDIT_JOURS = 30
# Nombre maximal de crédits actifs simultanément par client (et 1 par produit).
MAX_CREDITS_ACTIFS = 2
# Écart toléré entre le nombre de crédits demandé et obtenu.
TOLERANCE_NB_CREDITS = 0.05
# Nombre de tirages autorisés par crédit d'un quota mensuel avant d'y renoncer (jamais reporté
# sur un autre mois : aucun rattrapage de fin d'année).
MAX_TENTATIVES_PAR_CREDIT = 50

# Courbe mensuelle des décaissements : croissance régulière sur l'année. Chaque produit répartit
# sa part annuelle sur ses mois de décaissement au prorata de cette courbe (saisonnalité :
# AGRICOLE mai–juillet, SCOLAIRE août–octobre). Janvier vaut 0 : les premières adhésions datent
# du 01/01 et un crédit exige 30 jours d'ancienneté du compte.
CROISSANCE_MENSUELLE: dict[int, int] = {
    1: 0,
    2: 4,
    3: 5,
    4: 6,
    5: 7,
    6: 8,
    7: 9,
    8: 10,
    9: 11,
    10: 12,
    11: 13,
    12: 14,
}
# Plafond réglementaire du TEG (usure).
TEG_MAX = Decimal("0.24")

# --------------------------------------------------------------------------------------------
# Remboursements
# --------------------------------------------------------------------------------------------

A_JOUR = "A_JOUR"
RETARD_PONCTUEL = "RETARD_PONCTUEL"
RETARD_30 = "RETARD_30"
ARRET_PAIEMENT = "ARRET_PAIEMENT"

# Profils « sains », tirés à l'octroi du crédit.
POIDS_PROFILS_SAINS: dict[str, float] = {A_JOUR: 0.85, RETARD_PONCTUEL: 0.15}
# Profils « à risque », affectés ensuite pour atteindre la cible de PAR 30.
POIDS_PROFILS_RISQUE: dict[str, float] = {RETARD_30: 0.5, ARRET_PAIEMENT: 0.5}

PAR30_CIBLE = Decimal("0.05")
PAR30_SEUIL_JOURS = 30

# Délais de paiement en jours par rapport à la date d'échéance (bornes incluses).
DELAI_A_JOUR: tuple[int, int] = (-3, 3)
DELAI_RETARD_PONCTUEL: tuple[int, int] = (8, 30)
DELAI_RETARD_30: tuple[int, int] = (31, 60)
# Probabilité, pour un client en retard ponctuel, de payer une échéance en retard.
PROBA_ECHEANCE_EN_RETARD = 0.3
# Probabilité, pour un client en retard ponctuel, de régler une échéance en deux fois.
PROBA_PAIEMENT_PARTIEL = 0.15
PART_PAIEMENT_PARTIEL_PCT: tuple[int, int] = (30, 70)
DELAI_SOLDE_PARTIEL_JOURS: tuple[int, int] = (1, 10)

TAUX_PENALITE = Decimal("0.02")
DELAI_GRACE_PENALITE_JOURS = 7

POIDS_CANAUX_REMBOURSEMENT: dict[str, float] = {
    "GUICHET": 0.35,
    "AGENT": 0.20,
    "MOBILE": 0.25,
    "PRELEVEMENT": 0.20,
}

# --------------------------------------------------------------------------------------------
# Opérations sur les comptes
# --------------------------------------------------------------------------------------------

DEPOTS_PAR_MOIS = 2.0
RETRAITS_PAR_MOIS = 1.5
JOURS_PAR_MOIS = 30.4
PAS_MONTANT_OPERATION = 500
MONTANT_DEPOT_INITIAL: tuple[int, int] = (5_000, 50_000)
MONTANT_DEPOT: tuple[int, int] = (2_000, 150_000)
# Part du solde retirée lors d'un retrait courant, en pourcentage.
PART_RETRAIT_PCT: tuple[int, int] = (10, 60)
POIDS_CANAUX_OPERATIONS: dict[str, float] = {"GUICHET": 0.5, "AGENT": 0.2, "MOBILE": 0.3}

# Après un décaissement : le client retire l'essentiel du crédit en quelques jours.
PART_RETRAIT_CREDIT_PCT: tuple[int, int] = (70, 95)
NB_RETRAITS_CREDIT: tuple[int, int] = (1, 3)
DELAI_RETRAITS_CREDIT_JOURS: tuple[int, int] = (0, 5)
POIDS_CANAUX_RETRAIT_CREDIT: dict[str, float] = {"GUICHET": 0.75, "AGENT": 0.10, "MOBILE": 0.15}

FRAIS_TENUE_MENSUELS = 500

# --------------------------------------------------------------------------------------------
# Charges (montants mensuels en XOF, par clé d'agence)
# --------------------------------------------------------------------------------------------

LOYERS: dict[str, int] = {
    "SIEGE": 1_500_000,
    "DAKAR": 1_000_000,
    "THIES": 600_000,
    "KAOLACK": 550_000,
    "SAINT_LOUIS": 600_000,
    "ZIGUINCHOR": 500_000,
}
PERSONNEL: dict[str, int] = {
    "SIEGE": 12_000_000,
    "DAKAR": 6_000_000,
    "THIES": 4_500_000,
    "KAOLACK": 4_000_000,
    "SAINT_LOUIS": 4_000_000,
    "ZIGUINCHOR": 3_500_000,
}
TELECOM_SI_MENSUEL = 900_000
JOUR_TELECOM_SI = 10
TAUX_COMMISSION_MM = Decimal("0.01")
JOUR_COMMISSIONS_MM = 10
MONTANT_FOURNITURES: tuple[int, int] = (40_000, 150_000)
NB_FOURNITURES_PAR_MOIS = 1

# --------------------------------------------------------------------------------------------
# Trésorerie (D18 : caisses, D19 : banque)
# --------------------------------------------------------------------------------------------

SEUIL_CAISSE = 3_000_000
PLAFOND_CAISSE = 10_000_000
PAS_APPRO_CAISSE = 100_000
MARGE_CAPITAL = Decimal("0.10")
PAS_CAPITAL = 1_000_000

# --------------------------------------------------------------------------------------------
# Anomalies
# --------------------------------------------------------------------------------------------

NB_COPIES_DOUBLON: tuple[int, int] = (1, 2)
# Décalage d'une date de remboursement incohérente, avant le décaissement.
DECALAGE_DATE_INCOHERENTE_JOURS: tuple[int, int] = (1, 30)
# Écart ajouté au montant payé incohérent (multiple de PAS_MONTANT_OPERATION).
ECART_MONTANT_INCOHERENT: tuple[int, int] = (1, 20)
