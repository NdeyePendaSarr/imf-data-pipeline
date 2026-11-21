"""Invariants de la vérité propre, sur la petite configuration (100 clients, 150 crédits).

Les contrôles sont recalculés à partir des tables, indépendamment de la simulation.
"""

from collections import defaultdict
from datetime import date, datetime, timedelta

import pytest

from generator import config as cfg
from generator.__main__ import Generation, generer
from generator.echeancier import LigneEcheance, arrondi, teg_actuariel
from generator.referentiels import SIEGE
from generator.simulation import calculer_par30, est_ouvre, quotas_mensuels
from generator.tests.conftest import SEEDS, lire_csv, petite_config


def _cumul_positif(flux: dict[tuple[str, date], int]) -> dict[str, int]:
    """Solde minimal de fin de journée par entité, à partir des flux journaliers."""
    minimum: dict[str, int] = {}
    soldes: dict[str, int] = defaultdict(int)
    for entite, jour in sorted(flux):
        soldes[entite] += flux[entite, jour]
        minimum[entite] = min(minimum.get(entite, soldes[entite]), soldes[entite])
    return minimum


def test_solde_des_comptes_positif_chaque_jour(petite_generation: Generation) -> None:
    """Opérations, virement du crédit, frais de dossier et prélèvements compris."""
    v = petite_generation.verite
    flux: dict[tuple[str, date], int] = defaultdict(int)
    for op in v.operations:
        signe = 1 if op.type_operation == "DEPOT" else -1
        flux[op.id_compte, op.date_operation] += signe * op.montant
    compte_credit = {}
    for c in v.credits:
        compte_credit[c.id_credit] = c.id_compte_epargne
        flux[c.id_compte_epargne, c.date_decaissement] += c.montant_accorde - c.frais_dossier
    for r in v.remboursements:
        if r.canal == "PRELEVEMENT":
            flux[compte_credit[r.id_credit], r.date_remboursement] -= r.montant_paye
    minimums = _cumul_positif(flux)
    assert minimums and min(minimums.values()) >= 0


def test_caisse_positive_par_agence_et_par_jour(petite_generation: Generation) -> None:
    v = petite_generation.verite
    agence_client = {c.id_client: c.id_agence for c in v.clients}
    agence_credit = {c.id_credit: agence_client[c.id_client] for c in v.credits}
    flux: dict[tuple[str, date], int] = defaultdict(int)
    for o in v.ouverture:
        if o.canal == "GUICHET":
            flux[o.id_agence, o.date_ouverture] += o.montant
    for a in v.appro_caisse:
        flux[a.id_agence, a.date_appro] += a.montant
    for op in v.operations:
        if op.canal == "GUICHET" and op.type_operation != "FRAIS_TENUE":
            signe = 1 if op.type_operation == "DEPOT" else -1
            flux[op.id_agence, op.date_operation] += signe * op.montant
    for r in v.remboursements:
        if r.canal == "GUICHET":
            flux[agence_credit[r.id_credit], r.date_remboursement] += r.montant_paye
    for ch in v.charges:
        if ch.canal == "GUICHET":
            flux[ch.id_agence, ch.date_charge] -= ch.montant
    assert min(_cumul_positif(flux).values()) >= 0
    assert v.indicateurs.caisse_minimale >= 0


def test_banque_positive_chaque_jour(petite_generation: Generation) -> None:
    v = petite_generation.verite
    flux: dict[tuple[str, date], int] = defaultdict(int)
    for o in v.ouverture:
        if o.canal == "VIREMENT":
            flux["banque", o.date_ouverture] += o.montant
    for ch in v.charges:
        if ch.canal == "VIREMENT":
            flux["banque", ch.date_charge] -= ch.montant
    for a in v.appro_caisse:
        flux["banque", a.date_appro] -= a.montant
    assert _cumul_positif(flux)["banque"] >= 0
    assert v.indicateurs.banque_minimale >= 0


def test_capital_d19(petite_generation: Generation) -> None:
    """Capital = besoin maximal × (1 + marge), arrondi au million supérieur."""
    v = petite_generation.verite
    capital = [o for o in v.ouverture if o.canal == "VIREMENT"]
    assert len(capital) == 1 and capital[0].montant % cfg.PAS_CAPITAL == 0
    assert v.indicateurs.banque_minimale < capital[0].montant


def test_remboursements_coherents(petite_generation: Generation) -> None:
    """montant_paye = somme des parts ; date entre le décaissement et le 31/12."""
    v = petite_generation.verite
    decaissement = {c.id_credit: c.date_decaissement for c in v.credits}
    for r in v.remboursements:
        assert r.montant_paye == r.part_capital + r.part_interets + r.penalites
        assert min(r.part_capital, r.part_interets, r.penalites) >= 0
        assert decaissement[r.id_credit] <= r.date_remboursement <= petite_generation.config.fin


def test_penalites_et_capital(petite_generation: Generation) -> None:
    """Capital remboursé ≤ montant accordé ; SOLDE ⇔ tout le capital est remboursé."""
    v = petite_generation.verite
    capital: dict[str, int] = defaultdict(int)
    for r in v.remboursements:
        capital[r.id_credit] += r.part_capital
    for c in v.credits:
        assert capital[c.id_credit] <= c.montant_accorde
        assert (c.statut == "SOLDE") == (capital[c.id_credit] == c.montant_accorde)


def test_regles_d_octroi(petite_generation: Generation) -> None:
    """Décaissement ≥ ouverture + 30 j sur l'épargne du client ; frais = taux × montant."""
    v = petite_generation.verite
    comptes = {c.id_compte: c for c in v.comptes}
    produits = {p.code_produit: p for p in v.produits_credit}
    for c in v.credits:
        compte = comptes[c.id_compte_epargne]
        assert compte.type_compte == "EPARGNE" and compte.id_client == c.id_client
        assert (c.date_decaissement - compte.date_ouverture).days >= cfg.DELAI_MIN_CREDIT_JOURS
        assert c.frais_dossier == arrondi(
            produits[c.code_produit].taux_frais_dossier * c.montant_accorde
        )
        assert c.date_decaissement.year == petite_generation.config.fin.year


def test_regle_des_credits_actifs(petite_generation: Generation) -> None:
    """Au plus 1 crédit actif par produit et 2 actifs en même temps par client."""
    v = petite_generation.verite
    dernier_paiement: dict[str, date] = {}
    for r in v.remboursements:
        dernier_paiement[r.id_credit] = max(
            r.date_remboursement, dernier_paiement.get(r.id_credit, r.date_remboursement)
        )
    periodes: dict[str, list[tuple[date, date, str]]] = defaultdict(list)
    for c in v.credits:
        fin = dernier_paiement[c.id_credit] if c.statut == "SOLDE" else date.max
        periodes[c.id_client].append((c.date_decaissement, fin, c.code_produit))
    for credits in periodes.values():
        for debut, _, _ in credits:
            actifs = [p for d, f, p in credits if d <= debut < f]
            assert len(actifs) <= cfg.MAX_CREDITS_ACTIFS
            assert len(actifs) == len(set(actifs))


def test_echeancier_et_teg(petite_generation: Generation) -> None:
    """Σ capital = montant accordé, une échéance par mois ; TEG ≤ 24 % pour chaque crédit."""
    v = petite_generation.verite
    echeances: dict[str, list[LigneEcheance]] = defaultdict(list)
    for e in v.echeancier:
        assert e.montant == e.capital + e.interets
        echeances[e.id_credit].append(
            LigneEcheance(e.num_echeance, e.date_echeance, e.capital, e.interets)
        )
    for c in v.credits:
        lignes = echeances[c.id_credit]
        assert len(lignes) == c.duree_mois
        assert sum(e.capital for e in lignes) == c.montant_accorde
        assert teg_actuariel(c.montant_accorde, c.frais_dossier, lignes) <= float(cfg.TEG_MAX)
    # Les échéances après le 31/12 sont présentes.
    assert any(e.date_echeance > petite_generation.config.fin for e in v.echeancier)


def test_canaux_autorises(petite_generation: Generation) -> None:
    """Chaque canal utilisé figure dans dbt/seeds/canaux_autorises.csv pour sa source."""
    v = petite_generation.verite
    autorises: dict[str, set[str]] = defaultdict(set)
    for ligne in lire_csv(SEEDS / "canaux_autorises.csv"):
        autorises[ligne["source"]].add(ligne["canal"])
    assert {o.canal for o in v.operations} <= autorises["operations"]
    assert {r.canal for r in v.remboursements} <= autorises["remboursements"]
    assert {c.canal for c in v.charges} <= autorises["charges"]
    assert {o.canal for o in v.ouverture} <= autorises["ouverture"]


def test_jours_d_ouverture(petite_generation: Generation) -> None:
    """Guichet et agents du lundi au samedi ; le mobile tous les jours."""
    v = petite_generation.verite
    dates = [(o.canal, o.date_operation) for o in v.operations]
    dates += [(r.canal, r.date_remboursement) for r in v.remboursements]
    assert all(est_ouvre(j) for canal, j in dates if canal in ("GUICHET", "AGENT"))


def test_types_d_evenements_dans_le_mapping(petite_generation: Generation) -> None:
    """Chaque type d'événement généré a une règle dans mapping_comptable.csv."""
    v = petite_generation.verite
    regles = {ligne["type_evenement"] for ligne in lire_csv(SEEDS / "mapping_comptable.csv")}
    generes = {o.type_operation for o in v.operations}
    generes |= {f"CHARGE_{c.categorie}" for c in v.charges}
    generes |= {"OUVERTURE"} if v.ouverture else set()
    generes |= {"APPRO_CAISSE"} if v.appro_caisse else set()
    generes |= {"DECAISSEMENT"} if v.credits else set()
    generes |= {"FRAIS_DOSSIER"} if any(c.frais_dossier for c in v.credits) else set()
    generes |= {"REMBOURSEMENT"} if v.remboursements else set()
    assert "APPRO_CAISSE" in generes
    assert generes <= regles


def test_agences_et_ouvertures(petite_generation: Generation) -> None:
    """Le siège n'a pas de clients ; les ouvertures sont datées du 01/01."""
    v = petite_generation.verite
    siege = [a.id_agence for a in v.agences if a.type_agence == SIEGE]
    assert len(siege) == 1 and len(v.agences) == 6
    assert all(c.id_agence != siege[0] for c in v.clients)
    assert {o.date_ouverture for o in v.ouverture} == {
        date(petite_generation.config.fin.year, 1, 1)
    }
    fonds = {o.id_agence: o.montant for o in v.ouverture if o.canal == "GUICHET"}
    assert set(fonds) == {a.id_agence for a in v.agences if a.type_agence != SIEGE}
    assert set(fonds.values()) == {cfg.PLAFOND_CAISSE}


def test_clients_et_comptes(petite_generation: Generation) -> None:
    """Âge à l'adhésion, un compte EPARGNE par client ouvert à l'adhésion, statut ACTIF."""
    v = petite_generation.verite
    epargne: dict[str, int] = defaultdict(int)
    adhesion = {c.id_client: c.date_adhesion for c in v.clients}
    for compte in v.comptes:
        assert compte.statut == "ACTIF"
        assert compte.date_ouverture == adhesion[compte.id_client]
        epargne[compte.id_client] += compte.type_compte == "EPARGNE"
    assert set(epargne.values()) == {1} and len(epargne) == len(v.clients)
    for c in v.clients:
        assert c.date_naissance is not None and c.secteur_activite is not None
        age = c.date_adhesion.year - c.date_naissance.year
        age -= (c.date_adhesion.month, c.date_adhesion.day) < (
            c.date_naissance.month,
            c.date_naissance.day,
        )
        assert cfg.AGE_MIN_ADHESION <= age <= cfg.AGE_MAX_ADHESION


def test_identifiants_uniques_et_prefixes(petite_generation: Generation) -> None:
    v = petite_generation.verite
    colonnes = [
        ("AG", [a.id_agence for a in v.agences]),
        ("CLI", [c.id_client for c in v.clients]),
        ("CPT", [c.id_compte for c in v.comptes]),
        ("CRD", [c.id_credit for c in v.credits]),
        ("OPE", [o.id_operation for o in v.operations]),
        ("RMB", [r.id_remboursement for r in v.remboursements]),
        ("CHG", [c.id_charge for c in v.charges]),
        ("APP", [a.id_appro for a in v.appro_caisse]),
    ]
    tous = [i for _, ids in colonnes for i in ids]
    assert len(tous) == len(set(tous))
    for prefixe, ids in colonnes:
        assert all(i.startswith(prefixe) and i[len(prefixe) :].isdigit() for i in ids)
    # Non séquentiels : les identifiants triés ne sont pas consécutifs.
    nombres = sorted(int(i[3:]) for i in [c.id_client for c in v.clients])
    assert any(b - a > 1 for a, b in zip(nombres, nombres[1:], strict=False))


def test_date_maj_dans_l_exercice(petite_generation: Generation) -> None:
    """Aucun date_maj hors de l'exercice, ni dans la vérité ni dans les sorties brutes."""
    v, b = petite_generation.verite, petite_generation.brut
    annee = petite_generation.config.fin.year
    for source in (v, b):
        for table in (
            "clients",
            "comptes",
            "produits_credit",
            "credits",
            "echeancier",
            "remboursements",
        ):
            for ligne in getattr(source, table):
                assert ligne.date_maj.year == annee
                assert ligne.date_maj.time() == cfg.HEURE_DATE_MAJ


def test_date_maj_metier(petite_generation: Generation) -> None:
    """date_maj = date de l'événement (crédit : décaissement, SOLDE compris, I10)."""
    v = petite_generation.verite
    decaissement = {c.id_credit: c.date_decaissement for c in v.credits}
    for r in v.remboursements:
        assert r.date_maj.date() == r.date_remboursement
    for c in v.credits:
        assert c.date_maj.date() == c.date_decaissement
    assert all(e.date_maj.date() == decaissement[e.id_credit] for e in v.echeancier)
    assert all(c.date_maj.date() == c.date_adhesion for c in v.clients)


def test_par30_recalcule(petite_generation: Generation) -> None:
    """Le PAR 30 du manifeste est recalculé à partir des tables."""
    v = petite_generation.verite
    par30, total = calculer_par30(
        v.credits, v.echeancier, v.remboursements, petite_generation.config.fin
    )
    assert (par30, total) == (v.indicateurs.encours_par30, v.indicateurs.encours_total)
    assert 0 < par30 < total


def test_pas_de_paiement_futur(petite_generation: Generation) -> None:
    """Aucun remboursement après le 31/12, aucune opération hors de l'exercice."""
    v = petite_generation.verite
    fin = petite_generation.config.fin
    debut = petite_generation.config.debut
    assert all(debut <= o.date_operation <= fin for o in v.operations)
    assert all(r.date_remboursement <= fin for r in v.remboursements)


@pytest.fixture(scope="module", params=[42, 7, 2025], ids=lambda seed: f"seed={seed}")
def generation_par_seed(
    request: pytest.FixtureRequest, tmp_path_factory: pytest.TempPathFactory
) -> Generation:
    """Petite configuration générée pour plusieurs seeds (règle indépendante de la seed)."""
    seed: int = request.param
    return generer(petite_config(tmp_path_factory.mktemp(f"seed{seed}") / "data", seed=seed))


def test_regle_date_maj_filigrane(generation_par_seed: Generation) -> None:
    """Règle 9.1 : date_maj métier déterministe, filigrane de l'ingestion incrémentale."""
    g = generation_par_seed
    config, v, b = g.config, g.verite, g.brut
    tables = ("clients", "comptes", "produits_credit", "credits", "echeancier", "remboursements")

    # Tous les date_maj (vérité et brut) sont dans l'exercice, à 20:00:00.
    for source in (v, b):
        for table in tables:
            for ligne in getattr(source, table):
                assert config.debut <= ligne.date_maj.date() <= config.fin, table
                assert ligne.date_maj.time() == cfg.HEURE_DATE_MAJ, table

    # Échéancier : date de décaissement du crédit (même pour les échéances après le 31/12).
    credits = {c.id_credit: c for c in v.credits}
    for e in v.echeancier:
        assert e.date_maj == datetime.combine(
            credits[e.id_credit].date_decaissement, cfg.HEURE_DATE_MAJ
        )

    # Crédits (I10) : date de décaissement à 20:00, SOLDE compris.
    soldes = [c for c in v.credits if c.statut == "SOLDE"]
    assert soldes, "la petite configuration doit contenir des crédits soldés"
    for c in v.credits:
        assert c.date_maj == datetime.combine(c.date_decaissement, cfg.HEURE_DATE_MAJ)

    # Remboursements de la vérité : date_maj = date du remboursement à 20:00.
    for r in v.remboursements:
        assert r.date_maj == datetime.combine(r.date_remboursement, cfg.HEURE_DATE_MAJ)

    # Remboursements ajoutés par les anomalies : date_maj du crédit visé (ligne de référence).
    ids_ajoutes = {c.id_ligne for c in b.catalogue if c.table == "remboursements"}
    ajoutes = [r for r in b.remboursements if r.id_remboursement in ids_ajoutes]
    assert ajoutes, "aucun remboursement ajouté par les anomalies"
    assert len(ajoutes) == len(ids_ajoutes)
    credits_bruts = {c.id_credit: c for c in b.credits}
    for r in ajoutes:
        assert r.date_maj == credits_bruts[r.id_credit].date_maj


def test_parents_visibles_avant_leurs_enfants(petite_generation: Generation) -> None:
    """Pour chaque jour J : toute ligne enfant de date_maj < J+1 a un parent de date_maj < J+1.

    Garantit qu'une ingestion incrémentale arrêtée à J ne contient jamais d'orphelin :
    echeancier et remboursements → credits, credits → clients et comptes, comptes → clients.
    Contrôlé sur les sorties brutes (ce qui est ingéré), anomalies comprises.
    """
    b = petite_generation.brut
    config = petite_generation.config
    liens = {
        "echeancier": [("credits", "id_credit", "id_credit")],
        "remboursements": [("credits", "id_credit", "id_credit")],
        "credits": [
            ("clients", "id_client", "id_client"),
            ("comptes", "id_compte_epargne", "id_compte"),
        ],
        "comptes": [("clients", "id_client", "id_client")],
    }
    cles = {"clients": "id_client", "comptes": "id_compte", "credits": "id_credit"}
    # Lignes de chaque table rangées par jour de date_maj.
    par_jour: dict[str, dict[date, list[object]]] = {}
    for table in set(liens) | set(cles):
        par_jour[table] = defaultdict(list)
        for ligne in getattr(b, table):
            par_jour[table][ligne.date_maj.date()].append(ligne)
    visibles: dict[str, set[str]] = {table: set() for table in cles}
    jour = config.debut
    while jour <= config.fin:
        # Parents dont date_maj < J+1 : ceux des jours ≤ J (les parents d'abord).
        for table, cle in cles.items():
            visibles[table].update(getattr(p, cle) for p in par_jour[table][jour])
        for enfant, parents in liens.items():
            for ligne in par_jour[enfant][jour]:
                for parent, colonne, _ in parents:
                    assert getattr(ligne, colonne) in visibles[parent], (enfant, jour, ligne)
        jour += timedelta(days=1)
    # Aucune ligne hors de l'exercice n'a échappé au contrôle.
    for table in liens:
        assert all(config.debut <= j <= config.fin for j in par_jour[table])


def test_quotas_mensuels() -> None:
    """Quotas : somme exacte, rien en janvier, produits saisonniers dans leur saison."""
    for nb in (150, 3000, 3001):
        quotas = quotas_mensuels(nb)
        assert sum(quotas.values()) == nb
        assert all(n == 0 for (mois, _), n in quotas.items() if mois == 1)
    quotas = quotas_mensuels(3000)
    assert {m for (m, p) in quotas if p == "AGRICOLE"} == {5, 6, 7}
    assert {m for (m, p) in quotas if p == "SCOLAIRE"} == {8, 9, 10}
    # Croissance régulière : le quota d'un produit annuel ne décroît jamais d'un mois à l'autre.
    agr = [quotas[m, "AGR"] for m in range(2, 13)]
    assert agr == sorted(agr)


def test_decaissements_jours_ouvres_et_mensuels(petite_generation: Generation) -> None:
    """Décaissements les jours ouvrés, dans le mois de leur quota (aucun report)."""
    v = petite_generation.verite
    assert all(est_ouvre(c.date_decaissement) for c in v.credits)
    produits = {p.code: p for p in cfg.PRODUITS}
    for c in v.credits:
        saison = produits[c.code_produit].mois_decaissement
        if saison is not None:
            assert saison[0] <= c.date_decaissement.month <= saison[1]
