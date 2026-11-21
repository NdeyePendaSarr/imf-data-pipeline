# SenFinance Microcrédit – pipeline de données & états financiers

> **EN —** End-to-end ELT pipeline for a fictional Senegalese microfinance institution: synthetic
> operations → PostgreSQL → dbt (bronze / silver / gold) → star schema, double-entry bookkeeping,
> monthly trial balances, financial statements and loan-portfolio KPIs (PAR 30). Work in progress.

> 🚧 **Projet en construction** — phase 2 terminée, prochaine étape : ingestion bronze.

## Objectif

SenFinance Microcrédit est une institution de microfinance (IMF) **fictive**, présente dans plusieurs
régions du Sénégal. Ce projet transforme ses opérations brutes (dépôts, retraits, crédits,
remboursements, charges) en :

- **indicateurs de pilotage du portefeuille** : encours, PAR 30, taux de remboursement ;
- **comptabilité** : écritures, balances mensuelles, compte de résultat et bilan simplifié
  (logique SYSCOHADA, plan de comptes simplifié) ;
- **contrôles** : rapprochements gestion ↔ comptabilité et tests de qualité automatisés.

## Avancement

| Phase | Contenu | État |
|---|---|:---:|
| 0 | Cadrage : plan de comptes, schéma en étoile, règles de mapping | ✅ |
| 1 | Socle : Docker, PostgreSQL, environnement Python | ✅ |
| 2 | Générateur de données fictives et anomalies injectées | ✅ |
| 3 | Ingestion incrémentale et idempotente (bronze) | 🚧 |
| 4 | Nettoyage et standardisation avec dbt (silver) | ⬜ |
| 5 | Schéma en étoile et écritures comptables (gold) | ⬜ |
| 6 | Balances, états financiers, KPI, rapprochements | ⬜ |
| 7 | Orchestration Airflow | ⬜ |
| 8 | Dashboard Power BI | ⬜ |
| 9 | CI, documentation, entrepôt cloud | ⬜ |

## Architecture (cible)

```
Générateur Python ──► CSV d'agences + base opérationnelle (imf_ops)
                              │
                              ▼
               Ingestion ──► BRONZE ─► SILVER ─► GOLD   (entrepôt imf_dwh, dbt)
                                                   │
                                                   ▼
                                     Power BI : portefeuille, états financiers, qualité
```

## Stack

| | Outils |
|---|---|
| **En place** | Python 3.12 (uv, ruff, mypy, pytest) · PostgreSQL 17 · Docker Compose |
| **Prévu** | dbt Core · Apache Airflow · Power BI · GitHub Actions |

## Lancer le projet

**Prérequis :** Docker, [uv](https://docs.astral.sh/uv/), make.
Sous Windows : WSL2 + Docker Desktop, dépôt cloné dans WSL2.

```bash
git clone https://github.com/NdeyePendaSarr/imf-data-pipeline.git
cd imf-data-pipeline
cp .env.example .env   # puis choisis un mot de passe dans .env
make install           # environnement Python
make up                # démarre PostgreSQL
make test              # tests rapides
make generate          # génère data/ et remplit imf_ops
```

**Se connecter :**

| Base | Rôle |
|---|---|
| `imf_ops` | base opérationnelle simulée (source) |
| `imf_dwh` | entrepôt : schémas `bronze`, `silver`, `gold` |

- Terminal : `make psql-dwh` ou `make psql-ops`
- Client graphique (DBeaver, pgAdmin) : hôte `localhost`, port `5433`, identifiants du `.env`

`make help` liste toutes les commandes.

## Générer les données

```bash
make generate          # configuration par défaut : 2 000 clients, 3 000 crédits, seed 42
make generate-small    # petit jeu : 100 clients, 150 crédits
uv run python -m generator --exercice 2025 --clients 2000 --credits 3000 --seed 42 \
    --taux-anomalies 0.01 --sortie data [--sans-db]
```

Le générateur réécrit `data/` entièrement et recharge `imf_ops` dans une seule transaction
(`--sans-db` : fichiers seulement). Même seed → mêmes fichiers, octet pour octet.

**Principe : vérité propre + anomalies.** Le générateur simule d'abord une **vérité propre**
cohérente (soldes jamais négatifs, échéanciers exacts, TEG ≤ 24 %, PAR 30 calibré, caisses et
banque toujours positives), écrite dans `data/_verite/` pour les tests, jamais ingérée. Il
injecte ensuite, avec un flux aléatoire séparé, des **anomalies** dans les sorties brutes, chacune
listée dans `data/catalogue_anomalies.csv` avec son traitement attendu. Appliquer ces traitements
aux sorties brutes redonne exactement la vérité : c'est le contrat du futur nettoyage (silver).

| Sortie | Contenu |
|---|---|
| `imf_ops` (PostgreSQL) | clients, comptes, produits_credit, credits, echeancier, remboursements |
| `data/operations/date=AAAA-MM-JJ/` | dépôts, retraits et frais de tenue des agences, un fichier par jour |
| `data/*.csv` | agences, charges, ouverture (capital, fonds de caisse), appro_caisse |
| `data/_verite/`, `data/_manifest.json` | vérité propre ; paramètres, volumes, indicateurs, SHA-256 |

**Volumes et indicateurs de l'exécution par défaut** (relevés dans `data/_manifest.json`) :

| Table | Vérité | Brut |
|---|---:|---:|
| clients | 2 000 | 2 000 |
| comptes | 2 317 | 2 317 |
| credits | 3 000 | 3 000 |
| echeancier | 34 352 | 34 352 |
| remboursements | 7 365 | 7 513 |
| operations (364 fichiers journaliers) | 66 282 | 68 609 |
| charges | 227 | 229 |
| appro_caisse | 152 | 152 |
| catalogue_anomalies | — | 2 822 |

| Indicateur au 31/12/2025 | Valeur |
|---|---:|
| PAR 30 (encours en retard > 30 j / encours) | 5,00 % |
| Encours total des crédits en cours | 2 284 329 328 XOF |
| Encours en retard de plus de 30 jours | 114 207 065 XOF |
| Capital d'ouverture | 1 999 000 000 XOF |
| Approvisionnements de caisse | 152 |
| Caisse minimale (agence, fin de journée) | 3 000 831 XOF |
| Banque minimale (fin de journée) | 182 616 221 XOF |

| Anomalie | Table | Lignes | Traitement attendu |
|---|---|---:|---|
| DOUBLON_EXACT | operations | 663 (1 001 copies) | DEDOUBLONNER |
| ORPHELIN_COMPTE | operations | 663 | REJETER |
| MONTANT_NEGATIF | operations | 663 | REJETER |
| FORMAT_CANAL | operations | 663 | STANDARDISER |
| CANAL_NON_AUTORISE | charges | 2 | REJETER |
| DATE_INCOHERENTE | remboursements | 74 | REJETER |
| MONTANT_PAYE_INCOHERENT | remboursements | 74 | REJETER |
| NULL_NON_CRITIQUE | clients | 20 | ACCEPTER_NULL |

## Structure actuelle

```
├── docker/postgres/init/   # création des bases et des schémas
├── dbt/seeds/              # plan de comptes et règles de mapping comptable
├── generator/              # générateur de données (vérité, anomalies, imf_ops) et ses tests
├── data/                   # sorties du générateur (non versionnées)
├── tests/                  # tests du socle
├── docker-compose.yml
├── Makefile
└── pyproject.toml
```

## Limites

- Données **100 % fictives**.
- Plan de comptes **simplifié**, à codes internes : ce n'est pas le référentiel comptable officiel
  des SFD (RCSFD) ; les correspondances avec le SYSCOHADA sont **indicatives**.
- La liste complète sera publiée avec les états financiers (phase 6).
- Approvisionnements des caisses en une seule pièce (journal VIR), sans compte de fonds en transit.
- Banque contrôlée au niveau de l'IMF (un seul compte bancaire), pas par agence.
- TEG calculé sur l'échéancier théorique, pas sur les paiements réels.
- Jours ouvrés du lundi au samedi, sans jours fériés.
- Pas de refinancement : le capital d'ouverture couvre seul le besoin de financement, d'où un
  capital élevé.

## Licence

MIT — voir [LICENSE](LICENSE).

## Autrice

**Ndeye Penda SARR** — Master 2 Business Intelligence (UCAD) · Data Engineering (Orange Digital Center)
