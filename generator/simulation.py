"""Simulation de la vérité propre de SenFinance Microcrédit sur un exercice.

La vérité est tirée avec un unique flux aléatoire, Random(f"{seed}-verite") : elle ne dépend
donc pas du taux d'anomalies. Ordre des étapes (l'ordre des tirages fixe la reproductibilité) :
agences → clients et comptes → crédits (échéancier, paiements) → profils à risque (PAR 30)
→ opérations et canaux des remboursements → charges → caisses (D18) → banque (D19).
"""

import random
from collections import defaultdict
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from decimal import Decimal
from fractions import Fraction

from generator import config as cfg
from generator.config import Config, ParametresProduit
from generator.echeancier import (
    LigneEcheance,
    ajouter_mois,
    arrondi,
    arrondi_superieur,
    calculer_echeancier,
)
from generator.referentiels import (
    AGENCES,
    NOMS,
    PRENOMS_FEMMES,
    PRENOMS_HOMMES,
    SECTEURS,
    SIEGE,
)

UN_JOUR = timedelta(days=1)

# --------------------------------------------------------------------------------------------
# Tables de la vérité (une dataclass par table, champs dans l'ordre des colonnes)
# --------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Agence:
    id_agence: str
    nom: str
    ville: str
    region: str
    type_agence: str


@dataclass(frozen=True)
class Client:
    id_client: str
    id_agence: str
    prenom: str
    nom: str
    sexe: str
    date_naissance: date | None
    secteur_activite: str | None
    date_adhesion: date
    date_maj: datetime


@dataclass(frozen=True)
class Compte:
    id_compte: str
    id_client: str
    type_compte: str
    date_ouverture: date
    statut: str
    date_maj: datetime


@dataclass(frozen=True)
class ProduitCredit:
    code_produit: str
    libelle: str
    taux_annuel: Decimal
    taux_frais_dossier: Decimal
    duree_min_mois: int
    duree_max_mois: int
    date_maj: datetime


@dataclass(frozen=True)
class Credit:
    id_credit: str
    id_client: str
    id_compte_epargne: str
    code_produit: str
    date_decaissement: date
    montant_accorde: int
    frais_dossier: int
    duree_mois: int
    taux_annuel: Decimal
    statut: str
    date_maj: datetime


@dataclass(frozen=True)
class Echeance:
    id_credit: str
    num_echeance: int
    date_echeance: date
    capital: int
    interets: int
    montant: int
    date_maj: datetime


@dataclass(frozen=True)
class Remboursement:
    id_remboursement: str
    id_credit: str
    date_remboursement: date
    montant_paye: int
    part_capital: int
    part_interets: int
    penalites: int
    canal: str
    date_maj: datetime


@dataclass(frozen=True)
class Operation:
    id_operation: str
    id_compte: str
    id_agence: str
    date_operation: date
    type_operation: str
    canal: str
    montant: int


@dataclass(frozen=True)
class Charge:
    id_charge: str
    id_agence: str
    date_charge: date
    categorie: str
    canal: str
    montant: int


@dataclass(frozen=True)
class Ouverture:
    id_agence: str
    date_ouverture: date
    canal: str
    montant: int


@dataclass(frozen=True)
class ApproCaisse:
    id_appro: str
    id_agence: str
    date_appro: date
    montant: int


@dataclass(frozen=True)
class Indicateurs:
    """Indicateurs de contrôle de la vérité, repris dans le manifeste."""

    encours_total: int
    encours_par30: int
    capital: int
    nb_approvisionnements: int
    caisse_minimale: int
    banque_minimale: int

    @property
    def par30(self) -> Fraction:
        """PAR 30 au 31/12 : encours en retard de plus de 30 jours / encours total."""
        return (
            Fraction(self.encours_par30, self.encours_total) if self.encours_total else Fraction(0)
        )


@dataclass(frozen=True)
class Verite:
    """Ensemble des tables de la vérité propre."""

    agences: tuple[Agence, ...]
    clients: tuple[Client, ...]
    comptes: tuple[Compte, ...]
    produits_credit: tuple[ProduitCredit, ...]
    credits: tuple[Credit, ...]
    echeancier: tuple[Echeance, ...]
    remboursements: tuple[Remboursement, ...]
    operations: tuple[Operation, ...]
    charges: tuple[Charge, ...]
    ouverture: tuple[Ouverture, ...]
    appro_caisse: tuple[ApproCaisse, ...]
    indicateurs: Indicateurs
    ids_utilises: frozenset[str]


# --------------------------------------------------------------------------------------------
# Outils : calendrier, identifiants, tirages
# --------------------------------------------------------------------------------------------


def jours(debut: date, fin: date) -> Iterator[date]:
    """Itère sur les jours de `debut` à `fin` inclus."""
    jour = debut
    while jour <= fin:
        yield jour
        jour += UN_JOUR


def est_ouvre(jour: date) -> bool:
    """Vrai si le guichet et les agents travaillent ce jour-là (lundi à samedi)."""
    return jour.weekday() in cfg.JOURS_OUVRES


def horodatage(jour: date) -> datetime:
    """date_maj déterministe : la date de l'événement à 20:00:00 (jamais now())."""
    return datetime.combine(jour, cfg.HEURE_DATE_MAJ)


def premier_jour_ouvre(annee: int, mois: int) -> date:
    """Premier jour ouvré du mois."""
    jour = date(annee, mois, 1)
    while not est_ouvre(jour):
        jour += UN_JOUR
    return jour


def dernier_jour_ouvre(annee: int, mois: int) -> date:
    """Dernier jour ouvré du mois."""
    jour = ajouter_mois(date(annee, mois, 1), 1) - UN_JOUR
    while not est_ouvre(jour):
        jour -= UN_JOUR
    return jour


def jour_ouvre_suivant(jour: date) -> date:
    """Le jour lui-même s'il est ouvré, sinon le prochain jour ouvré."""
    while not est_ouvre(jour):
        jour += UN_JOUR
    return jour


def tirer_pas(rng: random.Random, bornes: tuple[int, int], pas: int) -> int:
    """Tire un montant entier multiple de `pas` dans les bornes."""
    return rng.randint(bornes[0] // pas, bornes[1] // pas) * pas


def tirer_cle(rng: random.Random, poids: dict[str, float]) -> str:
    """Tire une clé d'un dictionnaire de poids (ordre d'insertion fixe)."""
    return rng.choices(list(poids), weights=list(poids.values()))[0]


class GenerateurIds:
    """Identifiants non séquentiels : préfixe + chiffres tirés au hasard, sans remise."""

    def __init__(self, rng: random.Random, deja_utilises: Iterable[str] = ()) -> None:
        self._rng = rng
        self._utilises: set[str] = set(deja_utilises)

    def nouveau(self, prefixe: str) -> str:
        """Tire un identifiant jamais attribué (vérité et anomalies comprises)."""
        chiffres = cfg.CHIFFRES_IDS[prefixe]
        while True:
            candidat = f"{prefixe}{self._rng.randrange(10 ** (chiffres - 1), 10**chiffres)}"
            if candidat not in self._utilises:
                self._utilises.add(candidat)
                return candidat

    @property
    def utilises(self) -> frozenset[str]:
        """Identifiants déjà attribués."""
        return frozenset(self._utilises)


# --------------------------------------------------------------------------------------------
# Remboursement d'un crédit : imputation pénalités → intérêts → capital
# --------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Paiement:
    """Un paiement imputé sur un crédit."""

    jour: date
    montant: int
    capital: int
    interets: int
    penalites: int


class EtatCredit:
    """État de remboursement d'un crédit (objet mutable, interne à la simulation).

    Imputation par échéance, la plus ancienne d'abord : pénalité, puis intérêts, puis capital.
    La pénalité (2 % de l'échéance) est constatée quand un paiement touche l'échéance plus de
    7 jours après sa date.
    """

    def __init__(self, echeances: Sequence[LigneEcheance]) -> None:
        self.echeances = tuple(echeances)
        self._reste_interets = [e.interets for e in echeances]
        self._reste_capital = [e.capital for e in echeances]
        self._reste_penalite = [0] * len(echeances)
        self._penalite_constatee = [False] * len(echeances)
        self._reglee = [False] * len(echeances)
        self.paiements: list[Paiement] = []

    def _penalite_a_constater(self, indice: int, jour: date) -> int:
        echeance = self.echeances[indice]
        delai = (jour - echeance.date_echeance).days
        if self._penalite_constatee[indice] or delai <= cfg.DELAI_GRACE_PENALITE_JOURS:
            return 0
        return arrondi(cfg.TAUX_PENALITE * echeance.montant)

    def du_jusqu_a(self, indice: int, jour: date) -> int:
        """Montant à payer le `jour` pour solder les échéances 0 à `indice`."""
        total = 0
        for i in range(indice + 1):
            if not self._reglee[i]:
                total += self._reste_penalite[i] + self._reste_interets[i]
                total += self._reste_capital[i] + self._penalite_a_constater(i, jour)
        return total

    def payer(self, jour: date, montant: int) -> Paiement:
        """Impute un paiement et l'enregistre."""
        reste = montant
        parts = {"penalites": 0, "interets": 0, "capital": 0}
        for i in range(len(self.echeances)):
            if reste == 0:
                break
            if self._reglee[i]:
                continue
            penalite = self._penalite_a_constater(i, jour)
            if penalite:
                self._reste_penalite[i] += penalite
                self._penalite_constatee[i] = True
            for nom, restes in (
                ("penalites", self._reste_penalite),
                ("interets", self._reste_interets),
                ("capital", self._reste_capital),
            ):
                pris = min(reste, restes[i])
                restes[i] -= pris
                parts[nom] += pris
                reste -= pris
            if self._reste_penalite[i] + self._reste_interets[i] + self._reste_capital[i] == 0:
                self._reglee[i] = True
        if reste:
            raise ValueError("paiement supérieur au montant dû")
        paiement = Paiement(jour, montant, parts["capital"], parts["interets"], parts["penalites"])
        self.paiements.append(paiement)
        return paiement

    @property
    def date_solde(self) -> date | None:
        """Date du dernier paiement si tout est réglé, sinon None (crédit en cours)."""
        if all(self._reglee) and self.paiements:
            return self.paiements[-1].jour
        return None

    @property
    def capital_rembourse(self) -> int:
        return sum(p.capital for p in self.paiements)


def en_retard_30(
    echeances: Iterable[tuple[date, int]], principal_et_interets_payes: int, arrete: date
) -> bool:
    """Vrai si une échéance échue depuis plus de 30 jours n'est pas entièrement payée.

    L'imputation se fait de la plus ancienne à la plus récente : il suffit de comparer le
    cumul payé (capital + intérêts) au cumul dû des échéances échues depuis plus de 30 jours.
    """
    du = sum(montant for jour, montant in echeances if (arrete - jour).days > cfg.PAR30_SEUIL_JOURS)
    return principal_et_interets_payes < du


def calculer_par30(
    credits: Iterable[Credit],
    echeancier: Iterable[Echeance],
    remboursements: Iterable[Remboursement],
    arrete: date,
) -> tuple[int, int]:
    """Encours en retard de plus de 30 jours et encours total des crédits EN_COURS."""
    echeances_par_credit: dict[str, list[tuple[date, int]]] = defaultdict(list)
    for e in echeancier:
        echeances_par_credit[e.id_credit].append((e.date_echeance, e.capital + e.interets))
    capital_paye: dict[str, int] = defaultdict(int)
    principal_interets: dict[str, int] = defaultdict(int)
    for r in remboursements:
        if r.date_remboursement <= arrete:
            capital_paye[r.id_credit] += r.part_capital
            principal_interets[r.id_credit] += r.part_capital + r.part_interets
    encours_par30 = encours_total = 0
    for c in credits:
        if c.statut != "EN_COURS":
            continue
        encours = c.montant_accorde - capital_paye[c.id_credit]
        encours_total += encours
        if en_retard_30(echeances_par_credit[c.id_credit], principal_interets[c.id_credit], arrete):
            encours_par30 += encours
    return encours_par30, encours_total


def _delai(rng: random.Random, profil: str) -> int:
    """Délai de paiement d'une échéance selon le profil du client."""
    if profil == cfg.RETARD_30:
        return rng.randint(*cfg.DELAI_RETARD_30)
    if profil == cfg.RETARD_PONCTUEL and rng.random() < cfg.PROBA_ECHEANCE_EN_RETARD:
        return rng.randint(*cfg.DELAI_RETARD_PONCTUEL)
    return rng.randint(*cfg.DELAI_A_JOUR)


def simuler_paiements(
    rng: random.Random,
    echeances: Sequence[LigneEcheance],
    profil: str,
    date_decaissement: date,
    arrete: date,
) -> EtatCredit:
    """Paiements d'un crédit jusqu'à l'arrêté selon le profil (aucun après le 31/12)."""
    etat = EtatCredit(echeances)
    nb_echues = sum(1 for e in echeances if (arrete - e.date_echeance).days > cfg.PAR30_SEUIL_JOURS)
    # Arrêt de paiement : le client cesse de payer à une échéance échue depuis plus de 30 j.
    arret = rng.randint(0, nb_echues - 1) if nb_echues else 0
    dernier = date_decaissement
    for indice, echeance in enumerate(echeances):
        if profil == cfg.ARRET_PAIEMENT and indice >= arret:
            break
        jour = max(echeance.date_echeance + timedelta(days=_delai(rng, profil)), dernier)
        if jour > arrete:
            break
        if profil == cfg.RETARD_PONCTUEL and rng.random() < cfg.PROBA_PAIEMENT_PARTIEL:
            du = etat.du_jusqu_a(indice, jour)
            acompte = arrondi(Fraction(du * rng.randint(*cfg.PART_PAIEMENT_PARTIEL_PCT), 100))
            if 0 < acompte < du:
                etat.payer(jour, acompte)
                # Le solde de l'échéance reste dans la limite des 30 jours de retard.
                limite = echeance.date_echeance + timedelta(days=cfg.PAR30_SEUIL_JOURS)
                suite = jour + timedelta(days=rng.randint(*cfg.DELAI_SOLDE_PARTIEL_JOURS))
                jour = max(min(suite, limite), jour)
                if jour > arrete:
                    break
        etat.payer(jour, etat.du_jusqu_a(indice, jour))
        dernier = jour
    return etat


# --------------------------------------------------------------------------------------------
# Crédits : attribution sous contraintes
# --------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class _Pret:
    """Crédit en cours de simulation (l'état de remboursement est mutable)."""

    id_credit: str
    client: Client
    id_compte_epargne: str
    produit: ParametresProduit
    debut: date
    montant: int
    frais: int
    echeances: tuple[LigneEcheance, ...]
    profil: str
    etat: EtatCredit

    @property
    def fin_activite(self) -> date:
        """Fin (exclue) de la période d'activité : date du solde, sinon jamais."""
        return self.etat.date_solde or date.max

    def actif(self, jour: date) -> bool:
        return self.debut <= jour < self.fin_activite

    def encours(self) -> int:
        return self.montant - self.etat.capital_rembourse

    def en_retard_30(self, arrete: date) -> bool:
        paye = sum(p.capital + p.interets for p in self.etat.paiements)
        return en_retard_30(((e.date_echeance, e.montant) for e in self.echeances), paye, arrete)


def _compatible(existants: Sequence[_Pret], nouveau: _Pret) -> bool:
    """Au plus 1 crédit actif par produit et MAX_CREDITS_ACTIFS actifs en même temps."""
    for pret in existants:
        chevauche = pret.debut < nouveau.fin_activite and nouveau.debut < pret.fin_activite
        if chevauche and pret.produit.code == nouveau.produit.code:
            return False
    # Le nombre d'actifs est maximal au début d'une période : on teste ces instants.
    instants = [nouveau.debut] + [
        p.debut for p in existants if nouveau.debut <= p.debut < nouveau.fin_activite
    ]
    return all(
        1 + sum(1 for p in existants if p.actif(t)) <= cfg.MAX_CREDITS_ACTIFS for t in instants
    )


def _fenetre(produit: ParametresProduit, annee: int) -> tuple[date, date]:
    """Période de décaissement autorisée du produit sur l'exercice."""
    if produit.mois_decaissement is None:
        return date(annee, 1, 1), date(annee, 12, 31)
    premier, dernier = produit.mois_decaissement
    return date(annee, premier, 1), ajouter_mois(date(annee, dernier, 1), 1) - UN_JOUR


def _attribuer_credits(
    rng: random.Random,
    ids: GenerateurIds,
    config: Config,
    clients: Sequence[Client],
    epargne_par_client: dict[str, Compte],
) -> list[_Pret]:
    """Tire les crédits un par un, en respectant les contraintes d'octroi."""
    prets: list[_Pret] = []
    par_client: dict[str, list[_Pret]] = defaultdict(list)
    poids_produits = [p.poids for p in cfg.PRODUITS]
    tentatives = 0
    while (
        len(prets) < config.nb_credits
        and tentatives < cfg.MAX_TENTATIVES_PAR_CREDIT * config.nb_credits
    ):
        tentatives += 1
        produit = rng.choices(cfg.PRODUITS, weights=poids_produits)[0]
        client = rng.choice(clients)
        compte = epargne_par_client[client.id_client]
        debut_fenetre, fin_fenetre = _fenetre(produit, config.exercice)
        debut_min = max(
            compte.date_ouverture + timedelta(days=cfg.DELAI_MIN_CREDIT_JOURS), debut_fenetre
        )
        fin_max = min(fin_fenetre, config.fin)
        if debut_min > fin_max:
            continue
        jour = jour_ouvre_suivant(
            debut_min + timedelta(days=rng.randint(0, (fin_max - debut_min).days))
        )
        if jour > fin_max:
            continue
        montant = tirer_pas(rng, (produit.montant_min, produit.montant_max), cfg.PAS_MONTANT_CREDIT)
        duree = rng.randint(produit.duree_min_mois, produit.duree_max_mois)
        profil = tirer_cle(rng, cfg.POIDS_PROFILS_SAINS)
        echeances = calculer_echeancier(montant, produit.taux_annuel, duree, jour)
        etat = simuler_paiements(rng, echeances, profil, jour, config.fin)
        pret = _Pret(
            id_credit="",
            client=client,
            id_compte_epargne=compte.id_compte,
            produit=produit,
            debut=jour,
            montant=montant,
            frais=arrondi(produit.taux_frais_dossier * montant),
            echeances=echeances,
            profil=profil,
            etat=etat,
        )
        if not _compatible(par_client[client.id_client], pret):
            continue
        pret = replace(pret, id_credit=ids.nouveau("CRD"))
        prets.append(pret)
        par_client[client.id_client].append(pret)

    ecart = abs(len(prets) - config.nb_credits)
    if ecart > cfg.TOLERANCE_NB_CREDITS * config.nb_credits:
        raise ValueError(
            f"{len(prets)} crédits générés pour {config.nb_credits} demandés (écart > "
            f"{cfg.TOLERANCE_NB_CREDITS:.0%}) : augmente --clients ou réduis --credits"
        )
    return prets


def _calibrer_par30(rng: random.Random, prets: list[_Pret], arrete: date) -> list[_Pret]:
    """Affecte des profils à risque à des crédits en cours pour viser le PAR 30 cible.

    Seuls des crédits non soldés au 31/12 changent de profil : leur période d'activité reste
    ouverte, les contraintes d'octroi restent donc respectées.
    """
    resultat = list(prets)
    total = sum(p.encours() for p in prets if p.etat.date_solde is None)
    en_risque = 0
    indices = [i for i, p in enumerate(prets) if p.etat.date_solde is None]
    rng.shuffle(indices)
    for i in indices:
        if Fraction(en_risque, total or 1) >= cfg.PAR30_CIBLE:
            break
        pret = resultat[i]
        profil = tirer_cle(rng, cfg.POIDS_PROFILS_RISQUE)
        etat = simuler_paiements(rng, pret.echeances, profil, pret.debut, arrete)
        candidat = replace(pret, profil=profil, etat=etat)
        if candidat.etat.date_solde is not None or not candidat.en_retard_30(arrete):
            continue
        nouveau_total = total - pret.encours() + candidat.encours()
        if Fraction(en_risque + candidat.encours(), nouveau_total) > cfg.PAR30_CIBLE:
            continue
        resultat[i] = candidat
        total = nouveau_total
        en_risque += candidat.encours()
    return resultat


# --------------------------------------------------------------------------------------------
# Comptes : opérations et canaux des remboursements
# --------------------------------------------------------------------------------------------

# Ordre de traitement des mouvements d'une même journée sur un compte.
_PRIORITES = {
    "DECAISSEMENT": 0,
    "FRAIS_DOSSIER": 1,
    "DEPOT": 2,
    "REMBOURSEMENT": 3,
    "RETRAIT": 4,
    "FRAIS_TENUE": 5,
}


@dataclass(frozen=True)
class _Mouvement:
    """Mouvement prévu sur un compte, appliqué dans l'ordre chronologique."""

    jour: date
    nature: str
    ordre: int
    montant: int = 0
    part_solde_pct: int = 0
    canal: str = ""
    pret: _Pret | None = None
    paiement: Paiement | None = None

    @property
    def cle(self) -> tuple[date, int, int]:
        return self.jour, _PRIORITES[self.nature], self.ordre


def _mouvements_compte(
    rng: random.Random, compte: Compte, prets: Sequence[_Pret], arrete: date
) -> list[_Mouvement]:
    """Mouvements prévus sur un compte (montants des retraits fixés au moment du retrait)."""
    mouvements: list[_Mouvement] = []

    def ajouter(
        jour: date,
        nature: str,
        montant: int = 0,
        part_solde_pct: int = 0,
        canal: str = "",
        pret: _Pret | None = None,
        paiement: Paiement | None = None,
    ) -> None:
        mouvements.append(
            _Mouvement(
                jour, nature, len(mouvements), montant, part_solde_pct, canal, pret, paiement
            )
        )

    pas = cfg.PAS_MONTANT_OPERATION
    ajouter(
        compte.date_ouverture,
        "DEPOT",
        montant=tirer_pas(rng, cfg.MONTANT_DEPOT_INITIAL, pas),
        canal="GUICHET",
    )
    proba_depot = cfg.DEPOTS_PAR_MOIS / cfg.JOURS_PAR_MOIS
    proba_retrait = cfg.RETRAITS_PAR_MOIS / cfg.JOURS_PAR_MOIS
    for jour in jours(compte.date_ouverture + UN_JOUR, arrete):
        if rng.random() < proba_depot:
            canal = tirer_cle(rng, cfg.POIDS_CANAUX_OPERATIONS)
            montant = tirer_pas(rng, cfg.MONTANT_DEPOT, pas)
            if canal == "MOBILE" or est_ouvre(jour):
                ajouter(jour, "DEPOT", montant=montant, canal=canal)
        if rng.random() < proba_retrait:
            canal = tirer_cle(rng, cfg.POIDS_CANAUX_OPERATIONS)
            part = rng.randint(*cfg.PART_RETRAIT_PCT)
            if canal == "MOBILE" or est_ouvre(jour):
                ajouter(jour, "RETRAIT", part_solde_pct=part, canal=canal)
    for mois in range(compte.date_ouverture.month, 13):
        jour = dernier_jour_ouvre(arrete.year, mois)
        if jour > compte.date_ouverture:
            ajouter(jour, "FRAIS_TENUE", montant=cfg.FRAIS_TENUE_MENSUELS, canal="GUICHET")

    for pret in prets:
        ajouter(pret.debut, "DECAISSEMENT", montant=pret.montant, pret=pret)
        ajouter(pret.debut, "FRAIS_DOSSIER", montant=pret.frais, pret=pret)
        # Le client retire l'essentiel du crédit en quelques jours, surtout au guichet.
        total = arrondi(Fraction(pret.montant * rng.randint(*cfg.PART_RETRAIT_CREDIT_PCT), 100))
        nb = rng.randint(*cfg.NB_RETRAITS_CREDIT)
        for k in range(nb):
            part = total // nb + (total % nb if k == nb - 1 else 0)
            jour = pret.debut + timedelta(days=rng.randint(*cfg.DELAI_RETRAITS_CREDIT_JOURS))
            canal = tirer_cle(rng, cfg.POIDS_CANAUX_RETRAIT_CREDIT)
            if canal != "MOBILE":
                jour = jour_ouvre_suivant(jour)
            if jour <= arrete:
                ajouter(jour, "RETRAIT", montant=part, canal=canal)
        for paiement in pret.etat.paiements:
            canal = tirer_cle(rng, cfg.POIDS_CANAUX_REMBOURSEMENT)
            ajouter(paiement.jour, "REMBOURSEMENT", canal=canal, pret=pret, paiement=paiement)
    mouvements.sort(key=lambda m: m.cle)
    return mouvements


def _simuler_comptes(
    rng: random.Random,
    ids: GenerateurIds,
    clients: Sequence[Client],
    comptes: Sequence[Compte],
    prets: Sequence[_Pret],
    arrete: date,
) -> tuple[list[Operation], list[Remboursement]]:
    """Applique les mouvements compte par compte ; le solde reste ≥ 0 à chaque mouvement."""
    agence_client = {c.id_client: c.id_agence for c in clients}
    prets_par_compte: dict[str, list[_Pret]] = defaultdict(list)
    for pret in prets:
        prets_par_compte[pret.id_compte_epargne].append(pret)
    canaux_hors_prelevement = {
        k: v for k, v in cfg.POIDS_CANAUX_REMBOURSEMENT.items() if k != "PRELEVEMENT"
    }
    pas = cfg.PAS_MONTANT_OPERATION
    operations: list[Operation] = []
    remboursements: list[Remboursement] = []

    for compte in comptes:
        agence = agence_client[compte.id_client]
        solde = 0

        def operation(
            jour: date,
            nature: str,
            canal: str,
            montant: int,
            compte: Compte = compte,
            agence: str = agence,
        ) -> None:
            operations.append(
                Operation(
                    ids.nouveau("OPE"), compte.id_compte, agence, jour, nature, canal, montant
                )
            )

        for m in _mouvements_compte(rng, compte, prets_par_compte[compte.id_compte], arrete):
            if m.nature == "DEPOT":
                solde += m.montant
                operation(m.jour, "DEPOT", m.canal, m.montant)
            elif m.nature == "RETRAIT":
                voulu = m.montant if m.montant else solde * m.part_solde_pct // 100
                montant = min(voulu, solde) // pas * pas
                if montant > 0:
                    solde -= montant
                    operation(m.jour, "RETRAIT", m.canal, montant)
            elif m.nature == "FRAIS_TENUE":
                if solde >= m.montant:
                    solde -= m.montant
                    operation(m.jour, "FRAIS_TENUE", m.canal, m.montant)
            elif m.nature == "DECAISSEMENT":
                solde += m.montant
            elif m.nature == "FRAIS_DOSSIER":
                solde -= m.montant
            else:  # REMBOURSEMENT
                assert m.pret is not None and m.paiement is not None
                canal = m.canal
                if canal == "PRELEVEMENT":
                    # Prélèvement seulement si le solde du compte suffit.
                    if solde >= m.paiement.montant:
                        solde -= m.paiement.montant
                    else:
                        canal = tirer_cle(rng, canaux_hors_prelevement)
                if canal in ("GUICHET", "AGENT") and not est_ouvre(m.jour):
                    canal = "MOBILE"
                remboursements.append(
                    Remboursement(
                        ids.nouveau("RMB"),
                        m.pret.id_credit,
                        m.jour,
                        m.paiement.montant,
                        m.paiement.capital,
                        m.paiement.interets,
                        m.paiement.penalites,
                        canal,
                        horodatage(m.jour),
                    )
                )
            if solde < 0:
                raise AssertionError(f"solde négatif sur {compte.id_compte} le {m.jour}")
    return operations, remboursements


# --------------------------------------------------------------------------------------------
# Charges, caisses (D18) et banque (D19)
# --------------------------------------------------------------------------------------------


def _simuler_charges(
    rng: random.Random,
    ids: GenerateurIds,
    config: Config,
    agences: dict[str, Agence],
    operations: Sequence[Operation],
    remboursements: Sequence[Remboursement],
) -> list[Charge]:
    """Charges mensuelles : loyers, personnel, télécoms et SI, commissions mobile, fournitures."""
    annee = config.exercice
    siege = agences[SIEGE].id_agence
    volume_mobile: dict[int, int] = defaultdict(int)
    for op in operations:
        if op.canal == "MOBILE":
            volume_mobile[op.date_operation.month] += op.montant
    for r in remboursements:
        if r.canal == "MOBILE":
            volume_mobile[r.date_remboursement.month] += r.montant_paye

    charges: list[Charge] = []

    def charge(agence: str, jour: date, categorie: str, canal: str, montant: int) -> None:
        if montant > 0:
            charges.append(Charge(ids.nouveau("CHG"), agence, jour, categorie, canal, montant))

    for mois in range(1, 13):
        for cle, agence in agences.items():
            charge(
                agence.id_agence,
                premier_jour_ouvre(annee, mois),
                "LOYERS",
                "VIREMENT",
                cfg.LOYERS[cle],
            )
        charge(
            siege,
            jour_ouvre_suivant(date(annee, mois, cfg.JOUR_TELECOM_SI)),
            "TELECOM_SI",
            "VIREMENT",
            cfg.TELECOM_SI_MENSUEL,
        )
        if mois > 1:
            charge(
                siege,
                jour_ouvre_suivant(date(annee, mois, cfg.JOUR_COMMISSIONS_MM)),
                "COMMISSIONS_MM",
                "VIREMENT",
                arrondi(cfg.TAUX_COMMISSION_MM * volume_mobile[mois - 1]),
            )
        jours_ouvres = [
            j for j in jours(date(annee, mois, 1), dernier_jour_ouvre(annee, mois)) if est_ouvre(j)
        ]
        for cle, agence in agences.items():
            if cle == SIEGE:
                continue
            for _ in range(cfg.NB_FOURNITURES_PAR_MOIS):
                charge(
                    agence.id_agence,
                    rng.choice(jours_ouvres),
                    "FOURNITURES",
                    "GUICHET",
                    tirer_pas(rng, cfg.MONTANT_FOURNITURES, cfg.PAS_MONTANT_OPERATION),
                )
        for cle, agence in agences.items():
            charge(
                agence.id_agence,
                dernier_jour_ouvre(annee, mois),
                "PERSONNEL",
                "VIREMENT",
                cfg.PERSONNEL[cle],
            )
    return charges


def flux_caisse(
    ouverture: Iterable[Ouverture],
    operations: Iterable[Operation],
    remboursements: Iterable[Remboursement],
    charges: Iterable[Charge],
    agence_credit: dict[str, str],
) -> dict[tuple[str, date], int]:
    """Entrées − sorties d'espèces du jour par agence (canal GUICHET), hors approvisionnements."""
    flux: dict[tuple[str, date], int] = defaultdict(int)
    for o in ouverture:
        if o.canal == "GUICHET":
            flux[o.id_agence, o.date_ouverture] += o.montant
    for op in operations:
        if op.canal == "GUICHET" and op.type_operation in ("DEPOT", "RETRAIT"):
            signe = 1 if op.type_operation == "DEPOT" else -1
            flux[op.id_agence, op.date_operation] += signe * op.montant
    for r in remboursements:
        if r.canal == "GUICHET":
            flux[agence_credit[r.id_credit], r.date_remboursement] += r.montant_paye
    for c in charges:
        if c.canal == "GUICHET":
            flux[c.id_agence, c.date_charge] -= c.montant
    return flux


def _approvisionner_caisses(
    ids: GenerateurIds,
    config: Config,
    agences_regionales: Sequence[Agence],
    flux: dict[tuple[str, date], int],
) -> tuple[list[ApproCaisse], int]:
    """D18 : appro en début de journée si la caisse prévisionnelle passe sous le seuil."""
    appros: list[ApproCaisse] = []
    caisse_min: int | None = None
    for agence in agences_regionales:
        solde = 0
        for jour in jours(config.debut, config.fin):
            previsionnel = solde + flux.get((agence.id_agence, jour), 0)
            if previsionnel < cfg.SEUIL_CAISSE:
                montant = arrondi_superieur(cfg.PLAFOND_CAISSE - previsionnel, cfg.PAS_APPRO_CAISSE)
                appros.append(ApproCaisse(ids.nouveau("APP"), agence.id_agence, jour, montant))
                previsionnel += montant
            solde = previsionnel
            caisse_min = solde if caisse_min is None else min(caisse_min, solde)
    return appros, caisse_min or 0


def flux_banque(charges: Iterable[Charge], appros: Iterable[ApproCaisse]) -> dict[date, int]:
    """Mouvements du compte bancaire de l'IMF par jour, hors capital d'ouverture."""
    flux: dict[date, int] = defaultdict(int)
    for c in charges:
        if c.canal == "VIREMENT":
            flux[c.date_charge] -= c.montant
    for a in appros:
        flux[a.date_appro] -= a.montant
    return flux


# --------------------------------------------------------------------------------------------
# Simulation complète
# --------------------------------------------------------------------------------------------


def _moins_annees(jour: date, annees: int) -> date:
    """Recule de `annees` années (le 29 février devient le 28)."""
    try:
        return jour.replace(year=jour.year - annees)
    except ValueError:
        return jour.replace(year=jour.year - annees, day=28)


def _generer_clients(
    rng: random.Random, ids: GenerateurIds, config: Config, agences: Sequence[Agence]
) -> tuple[list[Client], list[Compte]]:
    """Clients des agences régionales et leurs comptes ouverts à l'adhésion."""
    regionales = [a for a in agences if a.type_agence != SIEGE]
    cles = {a.id_agence: d.cle for a, d in zip(agences, AGENCES, strict=True)}
    poids = [cfg.POIDS_CLIENTS_AGENCE[cles[a.id_agence]] for a in regionales]
    jours_ouvres = [j for j in jours(config.debut, config.fin) if est_ouvre(j)]
    clients: list[Client] = []
    comptes: list[Compte] = []
    for _ in range(config.nb_clients):
        agence = rng.choices(regionales, weights=poids)[0]
        adhesion = rng.choice(jours_ouvres)
        sexe = "F" if rng.random() < cfg.PART_FEMMES else "M"
        prenom = rng.choice(PRENOMS_FEMMES if sexe == "F" else PRENOMS_HOMMES)
        nom = rng.choice(NOMS)
        # Âge révolu à l'adhésion entre AGE_MIN et AGE_MAX.
        age = rng.randint(cfg.AGE_MIN_ADHESION, cfg.AGE_MAX_ADHESION)
        naissance_max = _moins_annees(adhesion, age)
        naissance_min = _moins_annees(adhesion, age + 1) + UN_JOUR
        naissance = naissance_min + timedelta(
            days=rng.randint(0, (naissance_max - naissance_min).days)
        )
        secteur = rng.choices(SECTEURS, weights=cfg.POIDS_SECTEURS)[0]
        client = Client(
            ids.nouveau("CLI"),
            agence.id_agence,
            prenom,
            nom,
            sexe,
            naissance,
            secteur,
            adhesion,
            horodatage(adhesion),
        )
        clients.append(client)
        types = ["EPARGNE"] + (["COURANT"] if rng.random() < cfg.PART_COMPTE_COURANT else [])
        for type_compte in types:
            comptes.append(
                Compte(
                    ids.nouveau("CPT"),
                    client.id_client,
                    type_compte,
                    adhesion,
                    "ACTIF",
                    horodatage(adhesion),
                )
            )
    return clients, comptes


def simuler(config: Config) -> Verite:
    """Génère la vérité propre de l'exercice."""
    rng = random.Random(f"{config.seed}-verite")
    ids = GenerateurIds(rng)

    agences = [Agence(ids.nouveau("AG"), d.nom, d.ville, d.region, d.type_agence) for d in AGENCES]
    agences_par_cle = {d.cle: a for d, a in zip(AGENCES, agences, strict=True)}
    produits = [
        ProduitCredit(
            p.code,
            p.libelle,
            p.taux_annuel,
            p.taux_frais_dossier,
            p.duree_min_mois,
            p.duree_max_mois,
            horodatage(config.debut),
        )
        for p in cfg.PRODUITS
    ]

    clients, comptes = _generer_clients(rng, ids, config, agences)
    epargne = {c.id_client: c for c in comptes if c.type_compte == "EPARGNE"}
    prets = _attribuer_credits(rng, ids, config, clients, epargne)
    prets = _calibrer_par30(rng, prets, config.fin)
    operations, remboursements = _simuler_comptes(rng, ids, clients, comptes, prets, config.fin)

    credits: list[Credit] = []
    echeancier: list[Echeance] = []
    for p in prets:
        solde = p.etat.date_solde
        credits.append(
            Credit(
                p.id_credit,
                p.client.id_client,
                p.id_compte_epargne,
                p.produit.code,
                p.debut,
                p.montant,
                p.frais,
                len(p.echeances),
                p.produit.taux_annuel,
                "SOLDE" if solde else "EN_COURS",
                # I10 : date_maj = décaissement pour tous les crédits, SOLDE compris. Le statut
                # au 31/12 n'est pas historisé (la base simulée ne garde que l'état final).
                horodatage(p.debut),
            )
        )
        # L'échéancier est connu dès le décaissement : date_maj = date de décaissement.
        echeancier.extend(
            Echeance(
                p.id_credit,
                e.num_echeance,
                e.date_echeance,
                e.capital,
                e.interets,
                e.montant,
                horodatage(p.debut),
            )
            for e in p.echeances
        )

    charges = _simuler_charges(rng, ids, config, agences_par_cle, operations, remboursements)

    # D18 : fonds de caisse d'ouverture puis approvisionnements quotidiens.
    regionales = [a for a in agences if a.type_agence != SIEGE]
    ouverture = [
        Ouverture(a.id_agence, config.debut, "GUICHET", cfg.PLAFOND_CAISSE) for a in regionales
    ]
    agence_credit = {p.id_credit: p.client.id_agence for p in prets}
    flux = flux_caisse(ouverture, operations, remboursements, charges, agence_credit)
    appros, caisse_min = _approvisionner_caisses(ids, config, regionales, flux)

    # D19 : capital = besoin maximal de la banque × (1 + marge), arrondi au million supérieur.
    cumul = besoin = 0
    mouvements_banque = flux_banque(charges, appros)
    for jour in jours(config.debut, config.fin):
        cumul += mouvements_banque.get(jour, 0)
        besoin = max(besoin, -cumul)
    capital = arrondi_superieur(besoin * (1 + cfg.MARGE_CAPITAL), cfg.PAS_CAPITAL)
    ouverture.insert(
        0, Ouverture(agences_par_cle[SIEGE].id_agence, config.debut, "VIREMENT", capital)
    )
    banque = banque_min = capital
    for jour in jours(config.debut, config.fin):
        banque += mouvements_banque.get(jour, 0)
        banque_min = min(banque_min, banque)

    encours_par30, encours_total = calculer_par30(credits, echeancier, remboursements, config.fin)
    indicateurs = Indicateurs(
        encours_total=encours_total,
        encours_par30=encours_par30,
        capital=capital,
        nb_approvisionnements=len(appros),
        caisse_minimale=caisse_min,
        banque_minimale=banque_min,
    )

    return Verite(
        agences=tuple(sorted(agences, key=lambda a: a.id_agence)),
        clients=tuple(sorted(clients, key=lambda c: c.id_client)),
        comptes=tuple(sorted(comptes, key=lambda c: c.id_compte)),
        produits_credit=tuple(sorted(produits, key=lambda p: p.code_produit)),
        credits=tuple(sorted(credits, key=lambda c: c.id_credit)),
        echeancier=tuple(sorted(echeancier, key=lambda e: (e.id_credit, e.num_echeance))),
        remboursements=tuple(sorted(remboursements, key=lambda r: r.id_remboursement)),
        operations=tuple(sorted(operations, key=lambda o: (o.date_operation, o.id_operation))),
        charges=tuple(sorted(charges, key=lambda c: (c.date_charge, c.id_charge))),
        ouverture=tuple(sorted(ouverture, key=lambda o: (o.id_agence, o.canal))),
        appro_caisse=tuple(sorted(appros, key=lambda a: (a.date_appro, a.id_appro))),
        indicateurs=indicateurs,
        ids_utilises=ids.utilises,
    )
