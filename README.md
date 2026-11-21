# SenFinance Microcrédit – pipeline de données & états financiers

> **EN —** End-to-end ELT pipeline for a fictional Senegalese microfinance institution: synthetic
> operations → PostgreSQL → dbt (bronze / silver / gold) → star schema, double-entry bookkeeping,
> monthly trial balances, financial statements and loan-portfolio KPIs (PAR 30). Work in progress.

> 🚧 **Projet en construction** — phase 4 terminée, prochaine étape : schéma en étoile et écritures comptables (gold).

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
| 3 | Ingestion incrémentale et idempotente (bronze) | ✅ |
| 4 | Nettoyage et standardisation avec dbt (silver) | ✅ |
| 5 | Schéma en étoile et écritures comptables (gold) | 🚧 |
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
| **En place** | Python 3.12 (uv, ruff, mypy, pytest) · PostgreSQL 17 · Docker Compose · dbt Core 1.12 (dbt-postgres, dbt_utils) |
| **Prévu** | Apache Airflow · Power BI · GitHub Actions |

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
make ingest-all        # ingère tout l'exercice dans bronze (imf_dwh)
make dbt-build         # silver : seeds, modèles et tests dbt
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

Les décaissements suivent une courbe mensuelle de croissance régulière (config.py), avec la
saisonnalité des produits (AGRICOLE de mai à juillet, SCOLAIRE d'août à octobre) et sans
rattrapage de fin d'année : un crédit qui ne trouve pas de client éligible dans son mois est
abandonné. Aucun crédit en janvier : les premières adhésions datent du 01/01 et un crédit exige
30 jours d'ancienneté du compte.

| Sortie | Contenu |
|---|---|
| `imf_ops` (PostgreSQL) | clients, comptes, produits_credit, credits, echeancier, remboursements |
| `data/<table>/date=AAAA-MM-JJ/` | operations (dépôts, retraits, frais de tenue), charges, appro_caisse : un fichier par jour avec des lignes |
| `data/*.csv` | instantanés : agences, ouverture (capital, fonds de caisse), catalogue_anomalies |
| `data/_verite/`, `data/_manifest.json` | vérité propre ; paramètres, volumes, indicateurs, SHA-256 |

**Volumes et indicateurs de l'exécution par défaut** (relevés dans `data/_manifest.json`) :

| Table | Vérité | Brut |
|---|---:|---:|
| clients | 2 000 | 2 000 |
| comptes | 2 317 | 2 317 |
| credits | 3 000 | 3 000 |
| echeancier | 34 037 | 34 037 |
| remboursements | 11 684 | 11 918 |
| operations (365 fichiers journaliers) | 66 514 | 68 848 |
| charges (83 fichiers journaliers) | 227 | 229 |
| appro_caisse (104 fichiers journaliers) | 141 | 141 |
| catalogue_anomalies | — | 2 916 |

| Indicateur au 31/12/2025 | Valeur |
|---|---:|
| PAR 30 (encours en retard > 30 j / encours) | 5,00 % |
| Encours total des crédits en cours | 1 850 520 623 XOF |
| Encours en retard de plus de 30 jours | 92 511 316 XOF |
| Capital d'ouverture | 1 797 000 000 XOF |
| Approvisionnements de caisse | 141 |
| Caisse minimale (agence, fin de journée) | 3 002 580 XOF |
| Banque minimale (fin de journée) | 163 883 235 XOF |

| Anomalie | Table | Lignes | Traitement attendu |
|---|---|---:|---|
| DOUBLON_EXACT | operations | 665 (1 004 copies) | DEDOUBLONNER |
| ORPHELIN_COMPTE | operations | 665 | REJETER |
| MONTANT_NEGATIF | operations | 665 | REJETER |
| FORMAT_CANAL | operations | 665 | STANDARDISER |
| CANAL_NON_AUTORISE | charges | 2 | REJETER |
| DATE_INCOHERENTE | remboursements | 117 | REJETER |
| MONTANT_PAYE_INCOHERENT | remboursements | 117 | REJETER |
| NULL_NON_CRITIQUE | clients | 20 | ACCEPTER_NULL |

## Ingestion bronze

```
imf_ops (PostgreSQL) ──COPY TO, fenêtre ]filigrane, J+1 00:00[──► data/landing/imf_ops/<table>/date=J/
data/<table>/date=J/ (CSV des agences) ─────────────────────────────┐            │
data/*.csv (instantanés) ───────────────────────────────────────────┤            │
                                                                    ▼            ▼
                                          même chargeur COPY ──► imf_dwh.bronze (+ _filigranes, _ingestions)
```

Chaque jour J est ingéré dans **une seule transaction** (données, filigranes et journal) : une
erreur annule tout le jour et la commande sort en erreur. Le rattrapage boucle jour par jour avec
le même code.

| Table bronze | Source | Mode |
|---|---|---|
| `csv_operations`, `csv_charges`, `csv_appro_caisse` | CSV des agences | partition du jour : ignorée si le même SHA-256 est déjà chargé, remplacée sinon ; aucun dédoublonnage |
| `csv_agences`, `csv_ouverture` | CSV des agences | instantané : rechargé en entier si son SHA-256 change |
| `meta_catalogue_anomalies` | métadonnée de test | instantané |
| `ops_produits_credit`, `ops_clients`, `ops_comptes`, `ops_credits`, `ops_echeancier`, `ops_remboursements` | imf_ops | filigrane sur `date_maj` ; une ligne par version, `UNIQUE (clé, date_maj)` |
| `_filigranes`, `_ingestions` | — | pilotage : filigrane par table, journal par run et par objet (CHARGE, IGNORE, VIDE) |

Chaque ligne porte `_id_run` (`AAAA-MM-JJ#n`), `_source`, `_num_ligne`, `_sha256` et
`_charge_le`. Le bronze est lié à une génération : une autre génération de `data/` est refusée
(`make reset-bronze`).

```bash
make ingest DATE=2025-03-15                # un jour
make ingest-range DU=2025-01-01 AU=2025-06-30
make ingest-all                            # tout l'exercice, jour par jour
make reset-bronze                          # vide le schéma bronze (imf_dwh uniquement)
```

**Rattrapage complet de l'exercice par défaut** (`make reset-bronze && make ingest-all`, mesuré
sur une vraie exécution) : 365 runs en **26,8 s**, 4 380 lignes de journal. Chaque table bronze
a exactement le volume brut du manifeste :

| Table bronze | Lignes |
|---|---:|
| `csv_operations` | 68 848 |
| `csv_charges` | 229 |
| `csv_appro_caisse` | 141 |
| `csv_agences` | 6 |
| `csv_ouverture` | 6 |
| `meta_catalogue_anomalies` | 2 916 |
| `ops_produits_credit` | 4 |
| `ops_clients` | 2 000 |
| `ops_comptes` | 2 317 |
| `ops_credits` | 3 000 |
| `ops_echeancier` | 34 037 |
| `ops_remboursements` | 11 918 |

## Silver (dbt)

```
bronze ──► stg_<table> (vues) ──► slv_<table> (tables, contrat dbt) ──► int_mouvements_compte
                │
                └──────────────► slv_lignes_ecartees (motif + traitement + _source, _num_ligne)
```

- **stg_** : typage sûr des colonnes TEXT (`vers_bigint`, `vers_date` : sinon NULL et motif
  TYPE_INVALIDE), codes standardisés `upper(trim())`, dernière version par clé pour imf_ops,
  rang de doublon par identifiant pour les CSV, et **un seul** `motif_ecart` par ligne
  (TYPE_INVALIDE > ORPHELIN_COMPTE > MONTANT_NEGATIF > CANAL_NON_AUTORISE > DATE_INCOHERENTE >
  MONTANT_PAYE_INCOHERENT ; copie d'un doublon → DOUBLON_EXACT).
- **slv_** : les lignes sans motif, avec les noms de colonnes de la source, `_id_run` et `_source`
  (`credits.statut` devient `statut_au_31_12`). Aucun modèle incrémental.
- **slv_lignes_ecartees** : tout ce qui n'est pas en silver, avec sa traçabilité bronze. Rien
  n'est filtré en silence.
- **int_mouvements_compte** : un mouvement par ligne sur un compte client (DEPOT, RETRAIT,
  FRAIS_TENUE, DECAISSEMENT, FRAIS_DOSSIER, PRELEVEMENT), `montant_signe` > 0 s'il augmente le solde.

```bash
make dbt-deps      # installe dbt_utils
make dbt-build     # seeds + modèles + tests (prérequis : make ingest-all)
make test-verite   # chaque slv_* = data/_verite/<table>.csv (la vérité n'entre jamais en base)
```

`dbt build` sur l'exercice par défaut : **148 PASS, 0 WARN, 0 ERROR** (5 seeds, 25 modèles,
118 tests). Les tests de catalogue comparent les lignes écartées aux anomalies injectées :

| Nature (catalogue) | Table | Lignes du catalogue | Lignes attendues | Lignes écartées |
|---|---|---:|---:|---:|
| DOUBLON_EXACT | operations | 665 | 1 004 (copies) | 1 004 |
| ORPHELIN_COMPTE | operations | 665 | 665 | 665 |
| MONTANT_NEGATIF | operations | 665 | 665 | 665 |
| CANAL_NON_AUTORISE | charges | 2 | 2 | 2 |
| DATE_INCOHERENTE | remboursements | 117 | 117 | 117 |
| MONTANT_PAYE_INCOHERENT | remboursements | 117 | 117 | 117 |
| FORMAT_CANAL (STANDARDISER) | operations | 665 | 0 (corrigées, gardées) | 0 |
| NULL_NON_CRITIQUE (ACCEPTER_NULL) | clients | 20 | 0 (gardées) | 0 |
| **Total** | | | **2 570** | **2 570** |

Silver obtenu (= vérité, ligne pour ligne) : 66 514 opérations, 227 charges, 141
approvisionnements, 6 agences, 6 ouvertures, 4 produits, 2 000 clients, 2 317 comptes, 3 000
crédits, 34 037 échéances, 11 684 remboursements ; 74 515 mouvements de comptes.

## Structure actuelle

```
├── docker/postgres/init/   # création des bases et des schémas
├── dbt/                    # projet dbt : sources bronze, modèles et tests silver, seeds du cadrage
├── generator/              # générateur de données (vérité, anomalies, imf_ops) et ses tests
├── ingestion/              # ingestion bronze (fenêtres, extraction, chargement, journal) et ses tests
├── data/                   # sorties du générateur (non versionnées)
├── tests/                  # tests du socle et test silver = vérité
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
- Runs imf_ops cumulatifs (filigrane) : rejouer un jour passé ne recharge rien ; pour tout rejouer,
  make reset-bronze.
- La base opérationnelle simulée ne conserve que l'état au 31/12 : le statut des crédits n'est pas
  historisé.

## Licence

MIT — voir [LICENSE](LICENSE).

## Autrice

**Ndeye Penda SARR** — Master 2 Business Intelligence (UCAD) · Data Engineering (Orange Digital Center)
