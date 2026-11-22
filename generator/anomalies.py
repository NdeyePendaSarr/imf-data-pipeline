"""Injection des anomalies dans les sorties brutes, après la vérité.

Flux aléatoire dédié, Random(f"{seed}-anomalies") : la vérité n'en dépend pas. Une vraie
ligne n'est altérée que pour STANDARDISER ou ACCEPTER_NULL ; les autres anomalies sont des
lignes ajoutées, avec des identifiants neufs (sauf les copies d'un doublon exact).
"""

import random
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import date, timedelta

from generator import config as cfg
from generator.config import Config
from generator.simulation import (
    Agence,
    ApproCaisse,
    Charge,
    Client,
    Compte,
    Credit,
    Echeance,
    GenerateurIds,
    Operation,
    Ouverture,
    ProduitCredit,
    Remboursement,
    Verite,
    tirer_cle,
)

DEDOUBLONNER = "DEDOUBLONNER"
REJETER = "REJETER"
STANDARDISER = "STANDARDISER"
ACCEPTER_NULL = "ACCEPTER_NULL"


@dataclass(frozen=True)
class LigneCatalogue:
    """Une ligne défectueuse des sorties brutes et le traitement attendu."""

    nature: str
    table: str
    id_ligne: str
    nombre: int
    traitement_attendu: str
    # Date de l'événement de la ligne visée (opération, charge) ; pour imf_ops, date à laquelle
    # la ligne devient visible (date_maj du remboursement, date d'adhésion du client). Permet de
    # restreindre les tests du catalogue à une date d'arrêté.
    date_ligne: date


@dataclass(frozen=True)
class Brut:
    """Sorties brutes : la vérité plus les anomalies, et leur catalogue."""

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
    catalogue: tuple[LigneCatalogue, ...]


def nombre_anomalies(taux: float, nb_lignes: int) -> int:
    """Nombre de lignes à rendre défectueuses pour un type d'anomalie (au moins 1 si taux > 0)."""
    if taux <= 0 or nb_lignes == 0:
        return 0
    return max(1, round(taux * nb_lignes))


def variante_canal(rng: random.Random, canal: str) -> str:
    """Variante mal formatée d'un canal (casse, espaces), toujours différente de l'original."""
    variantes = [f" {canal.lower()}", canal.capitalize(), f"{canal} ", canal.lower()]
    return rng.choice([v for v in variantes if v != canal])


def _anomalies_operations(
    rng: random.Random, ids: GenerateurIds, operations: Sequence[Operation], taux: float
) -> tuple[list[Operation], list[LigneCatalogue]]:
    lignes = list(operations)
    catalogue: list[LigneCatalogue] = []
    n = nombre_anomalies(taux, len(lignes))
    # Lignes distinctes pour FORMAT_CANAL et DOUBLON_EXACT.
    indices = rng.sample(range(len(lignes)), min(2 * n, len(lignes)))
    for i in indices[:n]:
        lignes[i] = replace(lignes[i], canal=variante_canal(rng, lignes[i].canal))
        catalogue.append(
            LigneCatalogue(
                "FORMAT_CANAL",
                "operations",
                lignes[i].id_operation,
                1,
                STANDARDISER,
                lignes[i].date_operation,
            )
        )
    ajouts: list[Operation] = []
    for i in indices[n:]:
        copies = rng.randint(*cfg.NB_COPIES_DOUBLON)
        ajouts.extend([lignes[i]] * copies)
        catalogue.append(
            LigneCatalogue(
                "DOUBLON_EXACT",
                "operations",
                lignes[i].id_operation,
                copies,
                DEDOUBLONNER,
                lignes[i].date_operation,
            )
        )
    for _ in range(n):
        modele = rng.choice(operations)
        orphelin = replace(modele, id_operation=ids.nouveau("OPE"), id_compte=ids.nouveau("CPT"))
        ajouts.append(orphelin)
        catalogue.append(
            LigneCatalogue(
                "ORPHELIN_COMPTE",
                "operations",
                orphelin.id_operation,
                1,
                REJETER,
                orphelin.date_operation,
            )
        )
    for _ in range(n):
        modele = rng.choice(operations)
        negatif = replace(modele, id_operation=ids.nouveau("OPE"), montant=-modele.montant)
        ajouts.append(negatif)
        catalogue.append(
            LigneCatalogue(
                "MONTANT_NEGATIF",
                "operations",
                negatif.id_operation,
                1,
                REJETER,
                negatif.date_operation,
            )
        )
    lignes.extend(ajouts)
    lignes.sort(key=lambda o: (o.date_operation, o.id_operation))
    return lignes, catalogue


def _anomalies_charges(
    rng: random.Random, ids: GenerateurIds, charges: Sequence[Charge], taux: float
) -> tuple[list[Charge], list[LigneCatalogue]]:
    lignes = list(charges)
    catalogue: list[LigneCatalogue] = []
    for _ in range(nombre_anomalies(taux, len(charges))):
        modele = rng.choice(charges)
        ligne = replace(modele, id_charge=ids.nouveau("CHG"), canal="PRELEVEMENT")
        lignes.append(ligne)
        catalogue.append(
            LigneCatalogue(
                "CANAL_NON_AUTORISE", "charges", ligne.id_charge, 1, REJETER, ligne.date_charge
            )
        )
    lignes.sort(key=lambda c: (c.date_charge, c.id_charge))
    return lignes, catalogue


def _anomalies_remboursements(
    rng: random.Random,
    ids: GenerateurIds,
    config: Config,
    verite: Verite,
    taux: float,
) -> tuple[list[Remboursement], list[LigneCatalogue]]:
    """Remboursements ajoutés sur des crédits existants (clés étrangères respectées)."""
    lignes = list(verite.remboursements)
    catalogue: list[LigneCatalogue] = []
    n = nombre_anomalies(taux, len(lignes))
    premiere: dict[str, Echeance] = {
        e.id_credit: e for e in verite.echeancier if e.num_echeance == 1
    }
    canaux = {k: v for k, v in cfg.POIDS_CANAUX_REMBOURSEMENT.items() if k != "PRELEVEMENT"}
    decalage_max = cfg.DECALAGE_DATE_INCOHERENTE_JOURS[1]
    # Date antérieure au décaissement mais dans l'exercice.
    credits_tardifs = [
        c for c in verite.credits if (c.date_decaissement - config.debut).days > decalage_max
    ]

    def ligne(credit: Credit, jour_decalage: int, ecart: int) -> Remboursement:
        echeance = premiere[credit.id_credit]
        return Remboursement(
            ids.nouveau("RMB"),
            credit.id_credit,
            credit.date_decaissement + timedelta(days=jour_decalage),
            echeance.capital + echeance.interets + ecart,
            echeance.capital,
            echeance.interets,
            0,
            tirer_cle(rng, canaux),
            credit.date_maj,  # date_maj de la ligne de référence : le crédit visé
        )

    for _ in range(n):
        decalage = rng.randint(*cfg.DECALAGE_DATE_INCOHERENTE_JOURS)
        r = ligne(rng.choice(credits_tardifs), -decalage, 0)
        lignes.append(r)
        catalogue.append(
            LigneCatalogue(
                "DATE_INCOHERENTE",
                "remboursements",
                r.id_remboursement,
                1,
                REJETER,
                r.date_maj.date(),
            )
        )
    for _ in range(n):
        credit = rng.choice(verite.credits)
        delai = rng.randint(1, max(1, (config.fin - credit.date_decaissement).days))
        ecart = rng.randint(*cfg.ECART_MONTANT_INCOHERENT) * cfg.PAS_MONTANT_OPERATION
        signe = rng.choice((-1, 1))
        # Une anomalie n'enfreint que sa propre règle : un écart négatif ne doit jamais rendre
        # montant_paye ≤ 0 (ce serait aussi un MONTANT_NEGATIF, prioritaire en silver). Même
        # nombre de tirages qu'avant : le reste de la génération est inchangé.
        if premiere[credit.id_credit].montant - ecart <= 0:
            signe = 1
        r = ligne(credit, delai, ecart * signe)
        lignes.append(r)
        catalogue.append(
            LigneCatalogue(
                "MONTANT_PAYE_INCOHERENT",
                "remboursements",
                r.id_remboursement,
                1,
                REJETER,
                r.date_maj.date(),
            )
        )
    lignes.sort(key=lambda r: r.id_remboursement)
    return lignes, catalogue


def _anomalies_clients(
    rng: random.Random, clients: Sequence[Client], taux: float
) -> tuple[list[Client], list[LigneCatalogue]]:
    lignes = list(clients)
    catalogue: list[LigneCatalogue] = []
    for i in sorted(rng.sample(range(len(lignes)), nombre_anomalies(taux, len(lignes)))):
        if rng.random() < 0.5:
            lignes[i] = replace(lignes[i], secteur_activite=None)
        else:
            lignes[i] = replace(lignes[i], date_naissance=None)
        catalogue.append(
            LigneCatalogue(
                "NULL_NON_CRITIQUE",
                "clients",
                lignes[i].id_client,
                1,
                ACCEPTER_NULL,
                lignes[i].date_adhesion,
            )
        )
    return lignes, catalogue


def injecter(verite: Verite, config: Config) -> Brut:
    """Construit les sorties brutes à partir de la vérité et du taux d'anomalies."""
    rng = random.Random(f"{config.seed}-anomalies")
    ids = GenerateurIds(rng, verite.ids_utilises)
    taux = config.taux_anomalies
    operations, cat_ops = _anomalies_operations(rng, ids, verite.operations, taux)
    charges, cat_charges = _anomalies_charges(rng, ids, verite.charges, taux)
    remboursements, cat_remb = _anomalies_remboursements(rng, ids, config, verite, taux)
    clients, cat_clients = _anomalies_clients(rng, verite.clients, taux)
    catalogue = sorted(
        cat_ops + cat_charges + cat_remb + cat_clients,
        key=lambda c: (c.table, c.nature, c.id_ligne),
    )
    return Brut(
        agences=verite.agences,
        clients=tuple(clients),
        comptes=verite.comptes,
        produits_credit=verite.produits_credit,
        credits=verite.credits,
        echeancier=verite.echeancier,
        remboursements=tuple(remboursements),
        operations=tuple(operations),
        charges=tuple(charges),
        ouverture=verite.ouverture,
        appro_caisse=verite.appro_caisse,
        catalogue=tuple(catalogue),
    )
