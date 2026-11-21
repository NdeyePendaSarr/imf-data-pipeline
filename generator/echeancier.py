"""Échéancier à annuités constantes et taux effectif global (TEG) actuariel.

Les calculs d'échéancier sont exacts (fractions) et produisent des montants entiers en XOF.
"""

import calendar
import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from fractions import Fraction


@dataclass(frozen=True)
class LigneEcheance:
    """Une échéance mensuelle théorique d'un crédit."""

    num_echeance: int
    date_echeance: date
    capital: int
    interets: int

    @property
    def montant(self) -> int:
        """Montant de l'échéance (capital + intérêts), hors pénalités."""
        return self.capital + self.interets


def arrondi(valeur: Fraction | Decimal | int) -> int:
    """Arrondit au franc le plus proche, moitié vers le haut, sans passer par un float."""
    return math.floor(Fraction(valeur) + Fraction(1, 2))


def arrondi_superieur(valeur: Fraction | Decimal | int, pas: int) -> int:
    """Arrondit au multiple de `pas` supérieur (ou égal)."""
    return math.ceil(Fraction(valeur) / pas) * pas


def ajouter_mois(jour: date, nb_mois: int) -> date:
    """Ajoute `nb_mois` mois à une date, en restant sur le dernier jour si le mois est court."""
    mois_total = jour.month - 1 + nb_mois
    annee = jour.year + mois_total // 12
    mois = mois_total % 12 + 1
    dernier_jour = calendar.monthrange(annee, mois)[1]
    return date(annee, mois, min(jour.day, dernier_jour))


def calculer_echeancier(
    montant: int, taux_annuel: Decimal, duree_mois: int, date_decaissement: date
) -> tuple[LigneEcheance, ...]:
    """Échéancier mensuel à annuités constantes sur le capital restant dû.

    Chaque échéance vaut l'annuité arrondie au franc ; les intérêts sont arrondis sur le
    capital restant dû et la dernière échéance solde le capital (elle absorbe l'arrondi).
    """
    if montant <= 0 or duree_mois <= 0:
        raise ValueError("montant et durée doivent être strictement positifs")
    taux_mensuel = Fraction(taux_annuel) / 12
    if taux_mensuel == 0:
        annuite = arrondi(Fraction(montant, duree_mois))
    else:
        annuite = arrondi(montant * taux_mensuel / (1 - (1 + taux_mensuel) ** -duree_mois))

    lignes: list[LigneEcheance] = []
    capital_restant = montant
    for num in range(1, duree_mois + 1):
        interets = arrondi(capital_restant * taux_mensuel)
        # La dernière échéance rembourse tout le capital restant (absorbe l'arrondi).
        capital = capital_restant if num == duree_mois else min(annuite - interets, capital_restant)
        capital_restant -= capital
        lignes.append(LigneEcheance(num, ajouter_mois(date_decaissement, num), capital, interets))
    return tuple(lignes)


def teg_actuariel(montant: int, frais_dossier: int, echeances: Sequence[LigneEcheance]) -> float:
    """TEG annuel actuariel, frais de dossier inclus, pénalités exclues.

    Taux mensuel t tel que montant − frais = Σ échéance_k / (1 + t)^k, annualisé en
    (1 + t)^12 − 1. Résolu par dichotomie (valeur calculée, jamais stockée).
    """
    net_recu = montant - frais_dossier

    def valeur_actuelle(taux: float) -> float:
        return sum(e.montant / (1 + taux) ** e.num_echeance for e in echeances) - net_recu

    bas, haut = 0.0, 1.0
    for _ in range(200):
        milieu = (bas + haut) / 2
        if valeur_actuelle(milieu) > 0:
            bas = milieu
        else:
            haut = milieu
    return float((1 + bas) ** 12 - 1)
