# SenFinance Microcrédit – pipeline de données & états financiers

> **EN —** End-to-end ELT pipeline for a fictional Senegalese microfinance institution: synthetic
> operations → PostgreSQL → dbt (bronze / silver / gold) → star schema, double-entry bookkeeping,
> monthly trial balances, financial statements and loan-portfolio KPIs (PAR 30). Work in progress.

> 🚧 **Projet en construction** — phase 1 terminée, prochaine étape : générateur de données.

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
| 2 | Générateur de données fictives et anomalies injectées | 🚧 |
| 3 | Ingestion incrémentale et idempotente (bronze) | ⬜ |
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
make test              # vérifie le socle
```

**Se connecter :**

| Base | Rôle |
|---|---|
| `imf_ops` | base opérationnelle simulée (source) |
| `imf_dwh` | entrepôt : schémas `bronze`, `silver`, `gold` |

- Terminal : `make psql-dwh` ou `make psql-ops`
- Client graphique (DBeaver, pgAdmin) : hôte `localhost`, port `5433`, identifiants du `.env`

`make help` liste toutes les commandes.

## Structure actuelle

```
├── docker/postgres/init/   # création des bases et des schémas
├── dbt/seeds/              # plan de comptes et règles de mapping comptable
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

## Licence

MIT — voir [LICENSE](LICENSE).

## Autrice

**Ndeye Penda SARR** — Master 2 Business Intelligence (UCAD) · Data Engineering (Orange Digital Center)
