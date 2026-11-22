"""Anomalies : catalogue exhaustif et traitements qui redonnent la vérité."""

from collections import Counter
from dataclasses import replace
from pathlib import Path

from generator.__main__ import Generation
from generator.anomalies import ACCEPTER_NULL, DEDOUBLONNER, REJETER, STANDARDISER
from generator.tests.conftest import lire_csv


def _partitions(sortie: Path, table: str) -> list[dict[str, str]]:
    """Concatène les partitions journalières d'une table brute (I11)."""
    lignes: list[dict[str, str]] = []
    for fichier in sorted((sortie / table).glob(f"date=*/{table}.csv")):
        jour = fichier.parent.name.removeprefix("date=")
        partition = lire_csv(fichier)
        # Chaque partition ne contient que les lignes de son jour.
        colonne = {"operations": "date_operation", "charges": "date_charge"}.get(
            table, "date_appro"
        )
        assert partition and all(ligne[colonne] == jour for ligne in partition)
        lignes.extend(partition)
    return lignes


def _operations_brutes(sortie: Path) -> list[dict[str, str]]:
    return _partitions(sortie, "operations")


def _catalogue(sortie: Path) -> list[dict[str, str]]:
    return lire_csv(sortie / "catalogue_anomalies.csv")


def test_toutes_les_natures_sont_presentes(petite_generation: Generation) -> None:
    natures = {(c["table"], c["nature"]) for c in _catalogue(petite_generation.config.sortie)}
    assert natures == {
        ("operations", "DOUBLON_EXACT"),
        ("operations", "ORPHELIN_COMPTE"),
        ("operations", "MONTANT_NEGATIF"),
        ("operations", "FORMAT_CANAL"),
        ("charges", "CANAL_NON_AUTORISE"),
        ("remboursements", "DATE_INCOHERENTE"),
        ("remboursements", "MONTANT_PAYE_INCOHERENT"),
        ("clients", "NULL_NON_CRITIQUE"),
    }


def test_chaque_ligne_du_catalogue_existe(petite_generation: Generation) -> None:
    sortie = petite_generation.config.sortie
    brut = petite_generation.brut
    ops = Counter(o["id_operation"] for o in _operations_brutes(sortie))
    charges = {c["id_charge"]: c for c in _partitions(sortie, "charges")}
    remboursements = {r.id_remboursement: r for r in brut.remboursements}
    credits = {c.id_credit: c for c in brut.credits}
    comptes = {c.id_compte for c in brut.comptes}
    clients = {c.id_client: c for c in brut.clients}
    for ligne in _catalogue(sortie):
        id_ligne, nature, nombre = ligne["id_ligne"], ligne["nature"], int(ligne["nombre"])
        if ligne["table"] == "operations":
            assert ops[id_ligne] == (1 + nombre if nature == "DOUBLON_EXACT" else 1)
        elif ligne["table"] == "charges":
            assert charges[id_ligne]["canal"] == "PRELEVEMENT"
        elif ligne["table"] == "remboursements":
            r = remboursements[id_ligne]
            credit = credits[r.id_credit]  # clé étrangère respectée
            if nature == "DATE_INCOHERENTE":
                assert r.date_remboursement < credit.date_decaissement
            else:
                assert r.montant_paye != r.part_capital + r.part_interets + r.penalites
            assert r.date_maj == credit.date_maj
        else:
            client = clients[id_ligne]
            assert client.secteur_activite is None or client.date_naissance is None
    orphelins = [o for o in _operations_brutes(sortie) if o["id_compte"] not in comptes]
    assert {o["id_operation"] for o in orphelins} == {
        c["id_ligne"] for c in _catalogue(sortie) if c["nature"] == "ORPHELIN_COMPTE"
    }


def test_traitements_redonnent_la_verite_csv(petite_generation: Generation) -> None:
    """Dédoublonner, retirer les REJETER et standardiser redonne exactement _verite/."""
    sortie = petite_generation.config.sortie
    catalogue = _catalogue(sortie)

    def ids(table: str, traitement: str) -> set[str]:
        return {
            c["id_ligne"]
            for c in catalogue
            if c["table"] == table and c["traitement_attendu"] == traitement
        }

    # Opérations
    vues: set[tuple[str, ...]] = set()
    traitees: list[dict[str, str]] = []
    doublons = ids("operations", DEDOUBLONNER)
    for op in _operations_brutes(sortie):
        if op["id_operation"] in ids("operations", REJETER):
            continue
        if op["id_operation"] in doublons:
            cle = tuple(op.values())
            if cle in vues:
                continue
            vues.add(cle)
        if op["id_operation"] in ids("operations", STANDARDISER):
            op["canal"] = op["canal"].strip().upper()
        traitees.append(op)
    cle_tri = lambda o: (o["date_operation"], o["id_operation"])  # noqa: E731
    assert sorted(traitees, key=cle_tri) == lire_csv(sortie / "_verite" / "operations.csv")

    # Charges
    charges = [
        c for c in _partitions(sortie, "charges") if c["id_charge"] not in ids("charges", REJETER)
    ]
    cle_charges = lambda c: (c["date_charge"], c["id_charge"])  # noqa: E731
    assert sorted(charges, key=cle_charges) == lire_csv(sortie / "_verite" / "charges.csv")

    # Approvisionnements : aucune anomalie, les partitions redonnent la vérité.
    assert _partitions(sortie, "appro_caisse") == lire_csv(sortie / "_verite" / "appro_caisse.csv")

    # Instantanés sans anomalie : identiques octet pour octet.
    for table in ("agences", "ouverture"):
        brut = (sortie / f"{table}.csv").read_bytes()
        assert brut == (sortie / "_verite" / f"{table}.csv").read_bytes()


def test_traitements_redonnent_la_verite_imf_ops(petite_generation: Generation) -> None:
    """imf_ops : retirer les REJETER redonne la vérité ; les NULL acceptés sont catalogués."""
    v, b = petite_generation.verite, petite_generation.brut
    rejetes = {c.id_ligne for c in b.catalogue if c.table == "remboursements"}
    assert all(c.traitement_attendu == REJETER for c in b.catalogue if c.table == "remboursements")
    assert (
        tuple(r for r in b.remboursements if r.id_remboursement not in rejetes) == v.remboursements
    )

    nulls = {c.id_ligne for c in b.catalogue if c.traitement_attendu == ACCEPTER_NULL}
    verite = {c.id_client: c for c in v.clients}
    assert len(b.clients) == len(v.clients)
    for client in b.clients:
        attendu = verite[client.id_client]
        if client.id_client in nulls:
            assert client != attendu
            complete = replace(
                client,
                secteur_activite=client.secteur_activite or attendu.secteur_activite,
                date_naissance=client.date_naissance or attendu.date_naissance,
            )
            assert complete == attendu
        else:
            assert client == attendu
    # Pas de doublon ni d'orphelin dans imf_ops.
    for table in ("credits", "comptes", "echeancier"):
        assert getattr(b, table) == getattr(v, table)


def test_taux_d_anomalies_environ_un_pour_cent(petite_generation: Generation) -> None:
    v, b = petite_generation.verite, petite_generation.brut
    par_nature = Counter(c.nature for c in b.catalogue)
    attendu = max(1, round(0.01 * len(v.operations)))
    assert par_nature["MONTANT_NEGATIF"] == attendu
    assert par_nature["NULL_NON_CRITIQUE"] == max(1, round(0.01 * len(v.clients)))


def test_chaque_anomalie_n_enfreint_que_sa_regle(petite_generation: Generation) -> None:
    """Les remboursements ajoutés ne violent que la règle de leur nature (un seul motif)."""
    b = petite_generation.brut
    natures = {c.id_ligne: c.nature for c in b.catalogue if c.table == "remboursements"}
    credits = {c.id_credit: c for c in b.credits}
    canaux = {"GUICHET", "AGENT", "MOBILE", "PRELEVEMENT"}
    for r in b.remboursements:
        if r.id_remboursement not in natures:
            continue
        nature = natures[r.id_remboursement]
        # Jamais de montant négatif ni de canal interdit sur ces lignes.
        assert min(r.montant_paye, r.part_capital, r.part_interets, r.penalites) >= 0
        assert r.canal in canaux
        avant = r.date_remboursement < credits[r.id_credit].date_decaissement
        incoherent = r.montant_paye != r.part_capital + r.part_interets + r.penalites
        assert (avant, incoherent) == (
            (True, False) if nature == "DATE_INCOHERENTE" else (False, True)
        ), (nature, r)


def test_date_ligne_du_catalogue(petite_generation: Generation) -> None:
    """date_ligne = date de l'événement visé (opération, charge) ; date_maj pour les
    remboursements ajoutés (imf_ops), date d'adhésion pour les clients."""
    b = petite_generation.brut
    dates: dict[tuple[str, str], set[object]] = {}
    for o in b.operations:
        dates.setdefault(("operations", o.id_operation), set()).add(o.date_operation)
    for c in b.charges:
        dates.setdefault(("charges", c.id_charge), set()).add(c.date_charge)
    for r in b.remboursements:
        dates.setdefault(("remboursements", r.id_remboursement), set()).add(r.date_maj.date())
    for cl in b.clients:
        dates.setdefault(("clients", cl.id_client), set()).add(cl.date_adhesion)
    for ligne in b.catalogue:
        assert dates[ligne.table, ligne.id_ligne] == {ligne.date_ligne}, ligne
    # Le CSV porte la colonne, au format ISO.
    lignes = lire_csv(petite_generation.config.sortie / "catalogue_anomalies.csv")
    assert all(len(ligne["date_ligne"]) == 10 for ligne in lignes)
