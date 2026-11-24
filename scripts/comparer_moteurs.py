"""Comparaison L3 des deux moteurs : gold et silver de PostgreSQL (dev) contre BigQuery (bq).

Les deux golds doivent être à la même date d'arrêté (sinon erreur, code 2). Mesures comparées :
- gold : date du gold, encours et encours PAR 30 au dernier jour (numérateur, dénominateur),
  actif et passif de chaque fin de mois (équilibre exigé des deux côtés), résultat cumulé,
  rapprochements (lignes, Σ |écart|), nombre de lignes des 19 tables ;
- silver : nombre de lignes et somme de chaque colonne de montant (entiers 64 bits et numériques)
  des 15 tables silver, colonnes relevées dans le catalogue PostgreSQL.

Les nombres sont comparés en Decimal : 443.2500 (PostgreSQL) = 443.25 (BigQuery).

    python -m scripts.comparer_moteurs     # make compare-moteurs : 0 égal, 1 écart, 2 erreur
"""

import datetime as dt
import os
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

Ligne = tuple[Any, ...]
# Exécute une requête où {gold} et {silver} préfixent les tables ; renvoie les lignes.
Executeur = Callable[[str], list[Ligne]]

TABLES_GOLD = (
    "dim_agence", "dim_client", "dim_compte_client", "dim_compte_comptable", "dim_credit",
    "dim_date", "dim_journal", "dim_produit_credit", "fct_echeances", "fct_ecritures",
    "fct_operations", "fct_portefeuille_quotidien", "fct_remboursements",
    "fct_solde_compte_mensuel", "mart_balance", "mart_bilan", "mart_compte_resultat",
    "mart_kpi_portefeuille", "mart_rapprochements",
)  # fmt: skip
TABLES_SILVER = (
    "slv_agences", "slv_appro_caisse", "slv_charges", "slv_clients", "slv_comptes",
    "slv_credits", "slv_echeancier", "slv_lignes_ecartees", "slv_operations", "slv_ouverture",
    "slv_produits_credit", "slv_remboursements",
    "int_evenements_comptables", "int_evenements_rejetes", "int_mouvements_compte",
)  # fmt: skip

DATE_GOLD = "select max(date_situation) from {gold}.mart_bilan"
REQUETES_GOLD: dict[str, str] = {
    "encours, encours PAR 30 (dernier jour)": (
        "select sum(encours), sum(encours_par30) from {gold}.mart_kpi_portefeuille "
        "where date = (select max(date) from {gold}.mart_kpi_portefeuille)"
    ),
    "résultat cumulé (dernier mois)": (
        "select sum(resultat_cumul) from {gold}.mart_compte_resultat "
        "where date_fin_mois = (select max(date_fin_mois) from {gold}.mart_compte_resultat)"
    ),
    "rapprochements (lignes, Σ |écart|)": (
        "select count(*), sum(abs(ecart)) from {gold}.mart_rapprochements"
    ),
}
BILAN_PAR_MOIS = (
    "select date_fin_mois, sum(case when cote = 'ACTIF' then montant end), "
    "sum(case when cote = 'PASSIF' then montant end) from {gold}.mart_bilan "
    "group by date_fin_mois order by date_fin_mois"
)


class ErreurComparaison(RuntimeError):
    """Comparaison impossible (dates d'arrêté différentes, table absente…)."""


@dataclass(frozen=True)
class Mesure:
    nom: str
    dev: Any
    bq: Any

    @property
    def egale(self) -> bool:
        return bool(normaliser(self.dev) == normaliser(self.bq))


def normaliser(valeur: Any) -> Any:
    """Nombres en Decimal (443.2500 = 443.25, int = Decimal), récursif sur les tuples/listes."""
    if isinstance(valeur, bool) or valeur is None:
        return valeur
    if isinstance(valeur, (int, float, Decimal)):
        return Decimal(str(valeur))
    if isinstance(valeur, (list, tuple)):
        return tuple(normaliser(v) for v in valeur)
    return valeur


def verifier_dates(date_dev: Any, date_bq: Any) -> dt.date:
    """Les deux golds doivent être arrêtés à la même date."""
    if date_dev is None or date_bq is None or date_dev != date_bq:
        raise ErreurComparaison(
            f"dates du gold différentes : dev {date_dev}, bq {date_bq} (reconstruire à la même "
            "date d'arrêté)"
        )
    if not isinstance(date_dev, dt.date):
        raise ErreurComparaison(f"date du gold illisible : {date_dev!r}")
    return date_dev


def mesures_bilan(dev: Sequence[Ligne], bq: Sequence[Ligne]) -> list[Mesure]:
    """Actif et passif de chaque mois, plus l'équilibre de chaque moteur."""
    mesures = [Mesure("bilan : mois (nombre)", len(dev), len(bq))]
    for moteur, lignes in (("dev", dev), ("bq", bq)):
        desequilibres = [str(r[0]) for r in lignes if normaliser(r[1]) != normaliser(r[2])]
        # Mesure d'équilibre : attendue vide des deux côtés.
        mesures.append(Mesure(f"bilan : mois déséquilibrés ({moteur})", desequilibres, []))
    par_mois_bq = {r[0]: r for r in bq}
    for ligne in dev:
        autre = par_mois_bq.get(ligne[0])
        mesures.append(Mesure(f"bilan {ligne[0]} (actif, passif)", ligne[1:],
                              None if autre is None else autre[1:]))  # fmt: skip
    return mesures


def comparer(dev: Executeur, bq: Executeur, colonnes_silver: dict[str, list[str]]) -> list[Mesure]:
    """Toutes les mesures, gold puis silver. Lève ErreurComparaison si les dates diffèrent."""
    date = verifier_dates(dev(DATE_GOLD)[0][0], bq(DATE_GOLD)[0][0])
    mesures = [Mesure("date du gold", date, date)]
    for nom, requete in REQUETES_GOLD.items():
        mesures.append(Mesure(nom, dev(requete)[0], bq(requete)[0]))
    mesures += mesures_bilan(dev(BILAN_PAR_MOIS), bq(BILAN_PAR_MOIS))
    for table in TABLES_GOLD:
        requete = f"select count(*) from {{gold}}.{table}"
        mesures.append(Mesure(f"gold.{table} : lignes", dev(requete)[0][0], bq(requete)[0][0]))
    for table in TABLES_SILVER:
        colonnes = colonnes_silver.get(table, [])
        expressions = ", ".join(["count(*)"] + [f"sum({c})" for c in colonnes])
        requete = f"select {expressions} from {{silver}}.{table}"
        valeurs_dev, valeurs_bq = dev(requete)[0], bq(requete)[0]
        for i, nom in enumerate(["lignes"] + colonnes):
            mesures.append(Mesure(f"silver.{table} : {nom}", valeurs_dev[i], valeurs_bq[i]))
    return mesures


def ratio_par30(mesures: list[Mesure]) -> str:
    """PAR 30 de chaque moteur, à partir du numérateur et du dénominateur comparés."""
    ligne = next(m for m in mesures if m.nom.startswith("encours"))
    textes = []
    for moteur, (encours, par30) in (("dev", ligne.dev), ("bq", ligne.bq)):
        taux = Decimal(par30) / Decimal(encours) * 100 if encours else Decimal(0)
        textes.append(f"{moteur} {par30} / {encours} = {taux:.4f} %")
    return " ; ".join(textes)


def tableau(mesures: list[Mesure]) -> str:
    largeur = max(len(m.nom) for m in mesures)
    lignes = [f"{'mesure':{largeur}}  {'dev':>28}  {'bq':>28}  état"]
    for m in mesures:
        etat = "=" if m.egale else "ÉCART"
        lignes.append(f"{m.nom:{largeur}}  {_texte(m.dev):>28}  {_texte(m.bq):>28}  {etat}")
    return "\n".join(lignes)


def _texte(valeur: Any) -> str:
    return ", ".join(map(str, valeur)) if isinstance(valeur, (tuple, list)) else str(valeur)


def tableau_markdown(mesures: list[Mesure]) -> str:
    """Résumé pour la page du run GitHub Actions ($GITHUB_STEP_SUMMARY)."""
    ecarts = sum(not m.egale for m in mesures)
    lignes = [
        "## Comparaison PostgreSQL (dev) / BigQuery (bq)",
        "",
        f"**{len(mesures)} mesures, {ecarts} écart(s)** — PAR 30 : {ratio_par30(mesures)}",
        "",
        "| Mesure | dev | bq | État |",
        "|---|---:|---:|:---:|",
    ]
    for m in mesures:
        etat = "=" if m.egale else "**ÉCART**"
        lignes.append(f"| {m.nom} | {_texte(m.dev)} | {_texte(m.bq)} | {etat} |")
    return "\n".join(lignes) + "\n"


def _executeurs() -> tuple[Executeur, Executeur, dict[str, list[str]]]:
    """Connexions réelles : PostgreSQL (POSTGRES_*) et BigQuery (BQ_PROJECT, BQ_LOCATION, ADC)."""
    import psycopg
    from google.cloud import bigquery

    from ingestion.config import parametres_connexion

    projet, region = os.environ["BQ_PROJECT"], os.environ["BQ_LOCATION"]
    conn = psycopg.connect(**parametres_connexion(os.getenv("POSTGRES_DB_DWH", "imf_dwh")))
    client = bigquery.Client(project=projet, location=region)

    def dev(requete: str) -> list[Ligne]:
        texte = requete.format(gold="gold", silver="silver")
        return [tuple(r) for r in conn.execute(texte.encode()).fetchall()]

    def bq(requete: str) -> list[Ligne]:
        texte = requete.format(gold=f"`{projet}`.gold", silver=f"`{projet}`.silver")
        return [tuple(r.values()) for r in client.query(texte).result()]

    colonnes: dict[str, list[str]] = {}
    for table, colonne in conn.execute(
        "select table_name, column_name from information_schema.columns "
        "where table_schema = 'silver' and data_type in ('bigint', 'numeric') "
        "order by table_name, ordinal_position"
    ).fetchall():
        colonnes.setdefault(table, []).append(colonne)
    return dev, bq, colonnes


def main() -> int:
    try:
        dev, bq, colonnes = _executeurs()
        mesures = comparer(dev, bq, colonnes)
    except (ErreurComparaison, KeyError) as erreur:
        print(f"Erreur : {erreur}", file=sys.stderr)
        return 2
    print(tableau(mesures))
    print(f"PAR 30 : {ratio_par30(mesures)}")
    # GitHub Actions : tableau Markdown sur la page du run (variable absente en local).
    resume = os.getenv("GITHUB_STEP_SUMMARY")
    if resume:
        with open(resume, "a", encoding="utf-8") as fichier:
            fichier.write(tableau_markdown(mesures))
    ecarts = [m for m in mesures if not m.egale]
    print(f"{len(mesures)} mesures, {len(ecarts)} écart(s)")
    return 1 if ecarts else 0


if __name__ == "__main__":
    sys.exit(main())
