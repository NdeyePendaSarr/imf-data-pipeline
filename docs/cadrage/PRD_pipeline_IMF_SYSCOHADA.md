# PRD – Pipeline de données d'une institution de microfinance (IMF) & états financiers (logique SYSCOHADA)

> **Document de cadrage (cahier des charges / PRD)** du projet.
> **Version 1.1 du 15/11/2026** : phase 0 (cadrage) terminée. Les décisions et le modèle détaillé sont dans `P1_phase0_cadrage.md`, qui complète ce PRD.
> **Version 1.2 du 20/11/2026** : cloud (Google Cloud Storage + BigQuery) intégré au plan, en phase 9 ; titre précisé (« logique SYSCOHADA »).
> **Version 1.3 du 21/11/2026** : cadrage de référence = `P1_phase0_cadrage.md` **v0.2** (D1 à D17) ; structure du repo complétée (§10) ; outils de l'environnement Python fixés (§8.2 : uv, ruff, mypy) ; PostgreSQL en une instance à deux bases, `imf_ops` et `imf_dwh` (§8.1) ; §8.3 replacé avant §8.4 ; chemins des documents de cadrage corrigés.
> **Version 1.4 du 21/11/2026** (cadrage de la phase 2) : cadrage de référence = `P1_phase0_cadrage.md` **v0.3** (D1 à D21) ; nouvelles sources `appro_caisse` (approvisionnement des caisses par la banque, D18) et `produits_credit` ; colonne `traitement_attendu` dans `catalogue_anomalies` (D21) ; répartition des sources entre `imf_ops` et CSV, CSV des opérations découpés par jour (§6.1) ; journal VIR (§6.3) ; tests banque ≥ 0 et TEG ≤ 24 % (§8.3) ; Faker retiré au profit de `random` seul (§8.2) ; décisions de la phase 2 dans `P1_phase2_cadrage.md`.
> **Version 1.5 du 21/11/2026** (phases 2 et 3 terminées) : `charges` et `appro_caisse` découpés par jour (§6.1, I11) ; `date_maj` des crédits = date de décaissement (I10, remplace la règle des crédits soldés de `P1_phase2_cadrage.md` 9.1) ; décaissements selon une courbe mensuelle, aucun en janvier (§5, I14) ; zone de landing des extractions `imf_ops` et modules d'ingestion (§10) ; limites complétées (§12). Décisions de la phase 3 dans `docs/cadrage/P1_phase3_cadrage.md`.

---

## 1. Contexte

En Afrique de l'Ouest, les institutions de microfinance (IMF / SFD) jouent un rôle central dans l'accès au crédit et à l'épargne pour les particuliers, les commerçants et les petites entreprises. Leur activité génère chaque jour un grand nombre d'opérations : ouvertures de comptes, dépôts, retraits, décaissements de crédits, remboursements, pénalités.

Ces données sont souvent dispersées (logiciel de gestion du portefeuille, fichiers Excel des agences, comptabilité tenue à part) et consolidées manuellement en fin de mois.

Le projet porte sur **« SenFinance Microcrédit »**, une **IMF fictive** opérant dans plusieurs régions du Sénégal (Dakar, Thiès, Kaolack, Saint-Louis, Ziguinchor…). Elle est supposée **en première année d'activité** : créée au 1er janvier, sans portefeuille historique.

## 2. Le problème

| Constat | Conséquence |
|---|---|
| Données réparties entre plusieurs sources (exports CSV d'agences, base opérationnelle) | Pas de vision unique et fiable de l'activité |
| Consolidation manuelle sous Excel | Lenteur, erreurs, aucune traçabilité |
| Suivi des retards de remboursement tardif | Le portefeuille à risque est découvert trop tard |
| Comptabilité produite séparément des données de gestion | Écarts entre gestion et comptabilité, clôtures longues |
| Pas de contrôle qualité automatisé | Doublons, montants négatifs, dates incohérentes non détectés |

## 3. Problématique

> **Comment centraliser, fiabiliser et automatiser le traitement des données opérationnelles d'une IMF afin de produire, de manière traçable et reproductible, à la fois des indicateurs de pilotage du portefeuille et des états financiers conformes à une logique SYSCOHADA ?**

## 4. Objectifs

### Objectif général
Construire un **pipeline de données ELT de bout en bout**, orchestré et testé, qui transforme les opérations brutes d'une IMF en **KPI de pilotage** et en **états financiers** exploitables dans un dashboard.

### Objectifs spécifiques
1. **Générer** un jeu de données fictif mais réaliste (clients, comptes, opérations, crédits, échéanciers, remboursements, charges, ouverture, approvisionnements de caisse), avec des **défauts volontaires** (doublons, nulls, dates incohérentes) consignés dans un catalogue, pour tester la qualité.
2. **Ingérer** ces données dans une zone brute (bronze), de façon **incrémentale** et **idempotente**.
3. **Nettoyer et standardiser** les données (silver) avec dbt.
4. **Modéliser** un **schéma en étoile** (gold) : faits et dimensions.
5. **Générer les écritures comptables** correspondant aux opérations, selon un plan de comptes simplifié (section 5, option hybride), **sans aucune affectation par défaut**.
6. **Produire** des balances mensuelles, le compte de résultat et le bilan simplifié (au 31/12 et à chaque fin de mois).
7. **Rapprocher** la gestion et la comptabilité (dépôts, encours de crédit).
8. **Calculer** les KPI de pilotage du portefeuille (section 7).
9. **Automatiser** l'exécution avec Airflow, avec contrôles qualité bloquants.
10. **Restituer** dans un dashboard Power BI.
11. **Documenter** l'ensemble (README, schéma d'architecture, lineage dbt, choix techniques, limites).

## 5. Périmètre

### Dans le périmètre (MVP)
- Données fictives générées en Python (`random` de la bibliothèque standard, listes de noms sénégalais maison) : 12 mois, ~2 000 clients, ~3 000 crédits, **paramétrables** ; exercice = année civile (paramètre `EXERCICE`). Les décaissements suivent une **courbe mensuelle de montée en charge** avec la saisonnalité des produits ; **aucun crédit en janvier** (I14).
- Pipeline batch quotidien.
- Modélisation medallion (bronze → silver → gold).
- Écriture d'ouverture (apport en capital), approvisionnements de caisse par la banque, charges de fonctionnement, écritures comptables simplifiées.
- Balances mensuelles, compte de résultat, bilan simplifié.
- Rapprochements gestion ↔ comptabilité.
- KPI portefeuille + dashboard.
- Tests de qualité, Docker, CI.

### Hors périmètre (BONUS ou améliorations éventuelles)
- Provisions et créances en souffrance (bonus).
- Épargne rémunérée (bonus).
- Intérêts courus non échus : le MVP reconnaît les intérêts à l'encaissement.
- Compensation des comptes de liaison (mobile money, agents).
- Versements des excédents de caisse vers la banque.
- Écriture de clôture (virement du résultat).
- SCD type 2 sur `dim_client` (bonus).
- Streaming temps réel.
- Spark : volume trop faible pour le justifier ici.
- Déploiement cloud **complet** (Airflow ou PostgreSQL managés). En revanche, l'entrepôt BigQuery et la zone brute Cloud Storage **font partie du plan** (phase 9, section 8.4).
- Machine learning (scoring de crédit).
- Conformité réglementaire réelle (reporting BCEAO).

### Référentiel comptable : option hybride (décidée en phase 0)
Dans l'UMOA, les SFD appliquent le **Référentiel comptable spécifique des SFD (RCSFD)**, institué par l'Instruction BCEAO n° 025-02-2009, et non le SYSCOHADA général. Le projet utilise donc :
- des **codes de comptes internes stables** (ex. `TRESO_CAISSE`), qui découplent le pipeline de toute numérotation ;
- une colonne **`compte_sfd`**, à remplir après relecture par un comptable d'IMF (checklist : `P1_checklist_relecture_SFD.md`) ;
- une colonne **`compte_syscohada_equiv`** avec un **`statut_correspondance`** (EQUIVALENT / APPROXIMATIF / A_VERIFIER), qui sert de correspondance indicative avec le SYSCOHADA général. Les numéros restent à vérifier.

Ce choix et ses limites sont **explicitement mentionnés dans le README** (section « Limites »).

## 6. Données

### 6.1 Sources simulées (zone brute)

| Fichier / table source | Contenu principal | Emplacement | Périmètre |
|---|---|---|---|
| `agences` | id, nom, région ; inclut une agence `SIEGE` (capital, charges centrales, sans clients) | CSV (instantané) | MVP |
| `produits_credit` | code, libellé, taux nominal annuel, taux de frais de dossier, durée min et max (mois), périodicité (MENSUELLE) | `imf_ops` | MVP |
| `clients` | id, nom fictif, sexe, date de naissance, secteur d'activité, agence, date d'adhésion | `imf_ops` | MVP |
| `comptes` | id, client, type (épargne / courant), date d'ouverture, statut | `imf_ops` | MVP |
| `operations` | id, compte, date, type (DEPOT, RETRAIT, FRAIS_TENUE), montant (XOF), canal (GUICHET, AGENT, MOBILE) | CSV, **un fichier par jour** | MVP |
| `credits` | id, client, produit, montant accordé, **frais de dossier**, taux, durée, date de décaissement, **compte d'épargne crédité**, statut | `imf_ops` | MVP |
| `echeancier` | id crédit, n° échéance, date prévue, capital dû, intérêts dus | `imf_ops` | MVP |
| `remboursements` | id, crédit, date, montant payé, part capital, part intérêts, pénalités, **canal** (GUICHET, AGENT, MOBILE, PRELEVEMENT) | `imf_ops` | MVP |
| **`charges`** | id, date, agence, catégorie (PERSONNEL, LOYERS, TELECOM_SI, FOURNITURES, COMMISSIONS_MM), montant, canal | CSV, **un fichier par jour** (I11) | MVP |
| **`ouverture`** | agence, canal (VIREMENT = banque, GUICHET = caisse), montant | CSV (instantané) | MVP |
| **`appro_caisse`** | id, date, agence approvisionnée, montant (banque → caisse, D18) | CSV, **un fichier par jour** (I11) | MVP |
| **`catalogue_anomalies`** (sortie du générateur) | nature, table, id de ligne, nombre, **traitement attendu** (DEDOUBLONNER / REJETER / STANDARDISER / ACCEPTER_NULL) | CSV (instantané) | MVP |
| `provisions` | crédit, date, montant de dotation ou de reprise | — | BONUS |

Formats : CSV « exports d'agences et de la comptabilité » (`data/`) + PostgreSQL `imf_ops` « logiciel de gestion du portefeuille », pour simuler **plusieurs sources**. Les CSV d'événements sont découpés par jour (`data/<table>/date=AAAA-MM-JJ/<table>.csv` pour `operations`, `charges`, `appro_caisse`) ; les autres CSV sont des instantanés. Chaque table de `imf_ops` porte une colonne `date_maj`, filigrane de l'ingestion incrémentale : horodatage métier déterministe (date de l'événement à 20:00) ; pour un crédit et son échéancier, c'est **toujours la date de décaissement** (I10). Ainsi, à chaque jour J, tout enfant visible en bronze a son parent.

Les défauts injectés n'altèrent jamais la vérité propre (D21) : doublons, orphelins et lignes invalides sont des **lignes ajoutées** ; seules la casse ou les espaces (STANDARDISER) et les nulls sur des colonnes non critiques (ACCEPTER_NULL) touchent de vraies lignes. Les doublons et les orphelins ne sont injectés que dans les CSV ; `imf_ops` garde ses clés primaires et étrangères.

Les mouvements induits sur les comptes d'épargne (virement du crédit, frais de dossier, prélèvements de remboursement) ne figurent pas dans `operations` : ils sont dérivés en silver. Chaque écriture n'a ainsi qu'**une seule source**.

### 6.2 Modèle cible (gold) – schéma en étoile

Le détail (attributs, clés, volumes) est dans `P1_phase0_cadrage.md` §3.

**Dimensions (toutes MVP) :** `dim_date`, `dim_agence`, `dim_client` (SCD 1 ; SCD 2 en bonus), `dim_compte_client`, `dim_produit_credit`, `dim_credit`, `dim_compte_comptable`, `dim_journal`

**Faits (tous MVP) :**
- `fct_operations` (grain : une opération de compte client)
- `fct_echeances` (grain : une échéance, crédit × n°)
- `fct_remboursements` (grain : un remboursement)
- `fct_portefeuille_quotidien` (grain : un crédit × un jour d'activité : encours, jours de retard)
- `fct_solde_compte_mensuel` (grain : un compte client × une fin de mois)
- `fct_ecritures` (grain : une ligne d'écriture comptable, débit/crédit ; avec `id_ecriture` (pièce), `num_ligne`, journal, agence, `type_evenement`, `source_table`, `source_id`, `version_mapping`)

**Marts finance (tous MVP) :**
- `mart_balance` (compte × agence × mois, balance à 6 colonnes)
- `mart_compte_resultat` (rubrique × mois + cumul)
- `mart_bilan` (rubrique × fin de mois)
- `mart_kpi_portefeuille` (jour × agence × produit)
- `audit_runs`

### 6.3 Mapping opérations → écritures

Le mapping est porté par cinq **seeds dbt** (`dbt/seeds/`), modifiables sans toucher au code :

| Seed | Rôle |
|---|---|
| `plan_comptes.csv` | Comptes : code interne, libellé, nature, sens normal, état, rubrique, `compte_sfd`, `compte_syscohada_equiv`, statut de correspondance, MVP |
| `mapping_comptable.csv` | Pour chaque type d'événement : lignes de l'écriture (sens, compte, champ du montant) |
| `mapping_canal_tresorerie.csv` | Résout le compte de trésorerie `@TRESORERIE` selon le canal : guichet → caisse, agent → liaison agents, mobile → liaison mobile money, virement → banque, prélèvement → compte d'épargne |
| `journaux.csv` | Journaux : OUV, VIR, CAI, AGT, MOB, BQ, OD, avec une priorité (le journal du type d'événement prime sur celui du canal) |
| `canaux_autorises.csv` | Canaux acceptés pour chaque source (ex. PRELEVEMENT réservé aux remboursements) |

| Événement | Débit | Crédit | Journal |
|---|---|---|---|
| Ouverture | Trésorerie (banque ou caisse) | Capital | OUV |
| Approvisionnement de caisse | Caisse (agence approvisionnée) | Banque | VIR |
| Dépôt | Trésorerie (selon canal) | Dépôts de la clientèle | selon canal |
| Retrait | Dépôts de la clientèle | Trésorerie (selon canal) | selon canal |
| Frais de tenue de compte | Dépôts de la clientèle | Produits – frais de tenue | OD |
| Décaissement de crédit (par virement) | Crédits à la clientèle | Dépôts de la clientèle | OD |
| Frais de dossier | Dépôts de la clientèle | Produits – frais de dossier | OD |
| Remboursement | Trésorerie (selon canal ; prélèvement = dépôts) | Crédits (capital) + Intérêts + Pénalités | selon canal |
| Charge de fonctionnement | Charge (par catégorie) | Trésorerie (selon canal) | selon canal |

> **Règle : aucune affectation par défaut.** Un événement sans règle de mapping va dans `int_evenements_rejetes`, qui doit rester vide (test bloquant).

## 7. Indicateurs (KPI)

| KPI | Définition | Source |
|---|---|---|
| Encours brut de crédit | Somme du capital restant dû | `fct_portefeuille_quotidien` |
| PAR 30 (portefeuille à risque) | Encours des crédits avec plus de 30 jours de retard / encours total | `fct_portefeuille_quotidien` |
| Taux de remboursement | Montants remboursés / montants échus | `fct_echeances` |
| Volume des dépôts et retraits | Par jour, mois, agence, canal | `fct_operations` |
| Encours d'épargne | Solde total des comptes clients | `fct_solde_compte_mensuel` |
| Produits d'intérêts | Intérêts encaissés sur la période | `fct_ecritures` |
| Clients actifs | Clients ayant eu au moins une opération sur la période | `fct_operations` |
| Équilibre comptable | Total débit = total crédit (contrôle) | `fct_ecritures`, `mart_balance` |
| Rapprochements | Écart gestion ↔ comptabilité sur les dépôts et les crédits (attendu : 0) | marts |

## 8. Solution technique

### 8.1 Architecture

```
[Générateur Python (random)]
        │  CSV agences (data/) + base opérationnelle PostgreSQL (imf_ops) + catalogue des anomalies
        ▼
[Ingestion Python] ──► BRONZE (entrepôt imf_dwh : données brutes, horodatées, incrémentales)
        ▼
[dbt] ──► SILVER (nettoyage, typage, dédoublonnage, standardisation, mouvements induits)
        ▼
[dbt] ──► GOLD (schéma en étoile + écritures + marts finance)
        ▼
[Power BI] Dashboards : pilotage portefeuille + états financiers + qualité

Orchestration : Airflow (DAG quotidien) · Conteneurs : Docker Compose · CI : GitHub Actions

Phase 9 (cloud) : fichiers bronze copiés dans Google Cloud Storage ;
même projet dbt exécuté aussi sur BigQuery (cible `bq`).
```

PostgreSQL (MVP) : **une instance, deux bases**. `imf_ops` joue la base opérationnelle (source) ; `imf_dwh` est l'entrepôt, avec les schémas `bronze`, `silver` et `gold`. Les deux bases et les trois schémas sont créés au premier démarrage par `docker/postgres/init/`. Les tables de `imf_ops` sont créées et rechargées par le générateur (`generator/sql/imf_ops.sql`). Les tables bronze sont créées par l'ingestion (`ingestion/sql/bronze.sql`) ; les extractions de `imf_ops` passent par une zone de landing (`data/landing/imf_ops/`) avant le chargement (I8).

### 8.2 Outils

| Outil | Rôle | Pourquoi |
|---|---|---|
| Python 3.12 (`random`) | Génération | Simple, typable, testable ; une seule source d'aléa (`random.Random`), donc une reproductibilité qui ne dépend d'aucune bibliothèque tierce ; Faker écarté en v1.4 (aucune colonne n'en a besoin) ; version fixée dans `.python-version` |
| psycopg 3 | Chargement de `imf_ops` et ingestion bronze (COPY) | Pilote PostgreSQL moderne, typé |
| pandas/polars | Non utilisés en phase 3 (I13) ; à réévaluer si besoin | Bronze ne transforme rien |
| uv | Dépendances, environnement virtuel, version de Python, fichier lock | Un seul outil, standard `pyproject.toml`, `uv.lock` reproductible, très rapide |
| ruff | Lint et formatage | Remplace flake8, isort et black en un outil |
| mypy | Vérification des types | Les type hints sont contrôlés, pas décoratifs |
| PostgreSQL 17 | Base opérationnelle + entrepôt (MVP) | Robuste, gratuit, connu |
| dbt Core | Transformations, tests, documentation, lineage | Standard du marché |
| Apache Airflow | Orchestration quotidienne, retries ; **image Docker séparée** (phase 7) | Très demandé en DE ; ses dépendances entrent en conflit avec celles de dbt |
| Docker / docker-compose | Environnement reproductible | Lancement en une commande |
| pytest | Tests Python (générateur, ingestion, socle) | Fiabilité du code |
| GitHub Actions | CI : lint (ruff), types (mypy), tests, `dbt build` | Pratiques professionnelles |
| Power BI | Dashboard | Restitution standard du pilotage et des états financiers |
| Google Cloud Storage + BigQuery | Zone brute et entrepôt cloud (phase 9) | Entrepôt cloud gratuit et durable (bac à sable BigQuery, sans carte bancaire) |
| *(Bonus)* Terraform | Création du bucket et des datasets | Infrastructure recréable à l'identique |

Poste de développement : Windows 11 + **WSL2** (Ubuntu) + Docker Desktop (intégration WSL activée). Le dépôt est cloné dans le système de fichiers Linux (`~/…`), pas dans `/mnt/c`.

### 8.3 Qualité des données

La liste numérotée (T1 à T17) est dans `P1_phase0_cadrage.md` §3.

| Test | Périmètre |
|---|---|
| Tests dbt génériques : `unique`, `not_null`, `relationships`, `accepted_values` (types, canaux) | MVP |
| Montants **entiers** (XOF, `BIGINT`) et ≥ 0 ; dates cohérentes (remboursement ≥ décaissement) | MVP |
| `montant_paye = part_capital + part_interets + penalites` | MVP |
| Débit = crédit **par `id_ecriture`** ; un seul des deux montants > 0 par ligne ; débit = crédit sur la balance | MVP |
| Tout compte d'écriture existe dans le plan ; `int_evenements_rejetes` vide | MVP |
| Rapprochements gestion ↔ comptabilité (dépôts, crédits) à chaque fin de mois | MVP |
| Bilan : actif = passif + résultat à chaque fin de mois | MVP |
| Caisse ≥ 0 par agence et par jour ; **banque ≥ 0 par jour, au niveau de l'IMF** (D19) | MVP |
| **TEG actuariel (frais de dossier inclus) ≤ 24 % pour chaque crédit** (D20, pytest du générateur) | MVP |
| Exemples chiffrés calculés à la main, en tests unitaires dbt | MVP |
| Chaque défaut du `catalogue_anomalies` attrapé par au moins un test, selon son `traitement_attendu` | MVP |
| Contrôles de volume (lignes chargées vs veille) et table `audit_runs`, visible dans le dashboard | MVP (phase 7) |
| SCD 2, provisions | BONUS |

### 8.4 Cloud (phase 9)

- **Deux cibles dbt, un seul projet** : `dbt build --target dev` (PostgreSQL local) et `dbt build --target bq` (BigQuery) doivent passer tous les deux.
- Les différences de SQL entre PostgreSQL et BigQuery sont isolées dans des **macros** (`dbt/macros/`), jamais copiées dans les modèles.
- **Zone brute cloud** : les fichiers bronze (CSV sources et extractions de landing) sont copiés dans un bucket Google Cloud Storage (`ingestion/upload_gcs.py`).
- **Contrainte du bac à sable** : tables, vues et partitions expirent au bout de **60 jours**. Une commande `make rebuild-bq` recrée tout l'entrepôt.
- **Snowflake écarté** : l'essai gratuit dure 30 jours, la démo disparaîtrait.
- **Bonus** : Terraform pour le bucket et les datasets ; Power BI connecté à BigQuery.
- Aucun identifiant ni clé de service dans le dépôt : variables d'environnement et `.env` dans `.gitignore`.

## 9. Comment s'y prendre (phases)

> Règle : **ne passer à la phase suivante que lorsque la précédente marche de bout en bout.**

| Phase | Contenu | Livrable / critère de fin |
|---|---|---|
| **0 – Cadrage** | Relire ce PRD, valider le plan de comptes, dessiner le schéma en étoile | ✅ **Terminée** : cadrage v0.2 validé le 21/11/2026 (D1 à D17), schéma en étoile, 5 seeds ; **v0.3** (D18 à D21) ajoutée pendant le cadrage de la phase 2 |
| **1 – Socle** | Repo Git public, fichiers du socle (§10), docker-compose (PostgreSQL : `imf_ops` + `imf_dwh` et ses schémas), environnement Python (uv, ruff, mypy, pytest), 5 seeds copiés dans `dbt/seeds/`, premier README | ✅ **Terminée** le 21/11/2026 |
| **2 – Données** | Générateur Python (toutes les sources de 6.1, approvisionnements de caisse compris ; paramètres : 12 mois, ~2 000 clients, ~3 000 crédits, exercice) + défauts injectés + `catalogue_anomalies` + tests pytest (invariants, TEG, reproductibilité). Détail : `P1_phase2_cadrage.md` | ✅ **Terminée** le 21/11/2026 (corrigée en phase 3 : I10, I11, I14) |
| **3 – Ingestion** | Chargement en bronze, incrémental et idempotent. Détail : `docs/cadrage/P1_phase3_cadrage.md` | ✅ **Terminée** le 21/11/2026 : relance sans doublon, bronze = manifeste |
| **4 – Silver** | Modèles dbt de nettoyage, mouvements induits + tests | `dbt build` vert sur silver |
| **5 – Gold** | Dimensions, faits, écritures comptables (seeds de mapping) | Balance équilibrée, rejets vides |
| **6 – Marts** | Balances mensuelles, compte de résultat, bilan simplifié, KPI, rapprochements | Chiffres cohérents et vérifiés à la main sur un échantillon ; tous les tests MVP au vert. **Jalon** : dépôt public, README à jour |
| **7 – Orchestration** | DAG Airflow quotidien, retries, contrôles bloquants, `audit_runs` | Exécution automatique sans intervention |
| **8 – Restitution** | Dashboard Power BI (pilotage + états financiers + qualité) | Dashboard soigné, captures |
| **9 – Industrialisation et cloud** | CI GitHub Actions, README complet, schéma d'architecture, docs dbt ; **cible dbt BigQuery + zone brute Cloud Storage** (section 8.4) | Repo présentable à un recruteur ; `dbt build` vert sur PostgreSQL **et** sur BigQuery |
| **Bonus** | Provisions, SCD 2 sur `dim_client`, Terraform, Power BI sur BigQuery | — |

> **Publication au fil de l'eau** : le dépôt est public dès la phase 1 et le README suit l'avancement. Un recruteur doit voir un projet vivant. Pas de rafales de commits ni de push forcé.

## 10. Structure du repo

Structure cible. **Chaque dossier est créé à la phase qui l'utilise** (indiquée en commentaire) : pas de dossiers vides ni de fichiers factices dans le dépôt.

```
imf-data-pipeline/
├── README.md
├── LICENSE                    # MIT (phase 1)
├── .gitignore                 # .env, data/, .venv/, dbt/target/, dbt/logs/… (phase 1)
├── .gitattributes             # fins de ligne LF, indispensable sous Windows/WSL2 (phase 1)
├── .env.example               # noms des variables, sans valeur secrète (phase 1)
├── .python-version            # 3.12 (phase 1)
├── pyproject.toml             # dépendances (uv) + config ruff, mypy, pytest (phase 1)
├── uv.lock                    # versionné (phase 1)
├── Makefile                   # up, down, psql, lint, test… (phase 1) ; generate (phase 2) ;
│                              # ingest, ingest-range, ingest-all, reset-bronze (phase 3) ; rebuild-bq (phase 9)
├── docker-compose.yml         # PostgreSQL (phase 1) ; Airflow (phase 7)
├── docker/
│   └── postgres/init/         # création de imf_ops, imf_dwh et des schémas (phase 1)
├── tests/                     # tests d'intégration : socle, bout en bout (phase 1)
├── data/                      # gitignoré : CSV générés, catalogue des anomalies, manifeste (phase 2) ;
│                              # landing/imf_ops/ : extractions de l'ingestion (phase 3)
├── generator/                 # phase 2
│   ├── __init__.py
│   ├── __main__.py            # CLI : python -m generator
│   ├── config.py              # EXERCICE, nb clients, nb crédits, seed aléatoire, seuils, courbe des décaissements
│   ├── referentiels.py        # agences, produits, prénoms et noms sénégalais, secteurs
│   ├── echeancier.py          # annuités constantes, arrondi XOF, TEG
│   ├── simulation.py          # simulation jour par jour (soldes, caisses, banque)
│   ├── anomalies.py           # injection + catalogue
│   ├── ecriture.py            # CSV + manifeste
│   ├── imf_ops.py             # chargement PostgreSQL
│   ├── sql/imf_ops.sql        # DDL de la base opérationnelle
│   └── tests/
├── ingestion/                 # phase 3
│   ├── __init__.py
│   ├── __main__.py            # CLI : python -m ingestion --date | --du --au | --exercice
│   ├── config.py
│   ├── fenetre.py             # fenêtres d'extraction (fonctions pures)
│   ├── extraction.py          # imf_ops → data/landing
│   ├── chargement.py          # fichier → bronze (COPY)
│   ├── journal.py             # bronze._ingestions, bronze._filigranes
│   ├── sql/bronze.sql         # DDL idempotent du bronze
│   ├── upload_gcs.py          # phase 9
│   └── tests/
├── dbt/
│   ├── dbt_project.yml        # phase 4
│   ├── profiles.yml           # cibles dev (phase 4) et bq (phase 9), uniquement via env_var()
│   ├── packages.yml           # dbt_utils (phase 4)
│   ├── macros/                # generate_schema_name (phase 4) ; différences PostgreSQL / BigQuery (phase 9)
│   ├── models/
│   │   ├── bronze/            # sources.yml (phase 4)
│   │   ├── silver/            # phase 4
│   │   │   └── intermediate/  # int_mouvements_compte, int_evenements_rejetes
│   │   └── gold/              # phases 5–6
│   │       ├── dims/
│   │       ├── facts/
│   │       └── marts/
│   ├── seeds/                 # 5 seeds (v0.3 depuis la phase 2) :
│   │                          # plan_comptes.csv, mapping_comptable.csv,
│   │                          # mapping_canal_tresorerie.csv, journaux.csv,
│   │                          # canaux_autorises.csv
│   └── tests/                 # tests singuliers (phases 4–6)
├── airflow/                   # phase 7, image Docker séparée
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── dags/
│   └── plugins/
├── .github/workflows/ci.yml   # phase 9
├── infra/terraform/           # bonus
├── dashboard/                 # .pbix + captures (phase 8)
└── docs/                      # architecture, choix techniques (phase 9)
    └── img/
```

## 11. Critères de réussite

- [ ] Le pipeline complet se lance avec Docker et s'exécute automatiquement via Airflow.
- [ ] Une relance ne crée ni doublon ni incohérence (idempotence).
- [ ] Tous les tests dbt et pytest passent en CI.
- [ ] Les défauts injectés sont détectés par les tests.
- [ ] La balance est équilibrée (débit = crédit) et aucun événement n'est rejeté.
- [ ] Les rapprochements gestion ↔ comptabilité sont à zéro.
- [ ] Les KPI et états financiers sont vérifiés à la main sur un échantillon.
- [ ] Le pipeline produit **la même balance, au franc près**, sur PostgreSQL et sur BigQuery.
- [ ] Le README permet à un inconnu de comprendre et relancer le projet.

## 12. Limites (à afficher dans le README)

- Données **100 % fictives** ; IMF supposée en **première année d'activité**.
- **Aucun crédit en janvier** : l'IMF démarre le 01/01 sans clients, et un crédit exige un compte ouvert depuis 30 jours.
- PAR 30 au 31/12 **paramétré à 5 %** dans la simulation ; le pipeline le recalcule, il ne le mesure pas sur une activité réelle.
- Plan de comptes **simplifié** à codes internes ; **ce n'est pas le RCSFD officiel**. Les numéros RCSFD sont à confirmer par un comptable d'IMF.
- Correspondances avec le SYSCOHADA général **indicatives**, certaines **approximatives** : le SYSCOHADA général n'a pas de comptes propres à l'activité de crédit et de dépôt.
- Intérêts reconnus **à l'encaissement**, alors que le RCSFD repose sur une comptabilité d'engagement.
- **Pas de provisions** sur créances en souffrance : le bilan surévalue l'encours si le PAR 30 est non nul.
- Épargne **non rémunérée** ; frais de dossier constatés en une fois.
- Comptes de liaison (mobile money, agents) **non compensés** ; pas d'écriture de clôture.
- Pas de refinancement : le capital d'ouverture couvre seul le besoin de financement, d'où un capital élevé.
- Approvisionnements de caisse en **une seule pièce** (journal VIR), sans compte de virements internes ; pas de versement des excédents de caisse vers la banque ; banque contrôlée ≥ 0 au niveau de l'IMF, pas par agence ; caisse contrôlée en fin de journée.
- TEG calculé sur l'échéancier théorique (frais de dossier inclus, pénalités exclues) ; taux d'usure de 24 % appliqué comme plafond unique.
- Jours d'ouverture du lundi au samedi, sans jours fériés.
- La base opérationnelle simulée ne conserve que l'**état au 31/12** : le statut des crédits n'est pas historisé.
- Runs `imf_ops` **cumulatifs** (filigrane) : rejouer un jour passé ne recharge rien ; pour tout rejouer, `make reset-bronze`.
- Pipeline **batch** uniquement.
- Orchestration **locale** (Airflow dans Docker) ; seuls l'entrepôt (BigQuery, bac à sable) et la zone brute (Cloud Storage) sont dans le cloud.
- Bac à sable BigQuery : données supprimées au bout de 60 jours, recréées par `make rebuild-bq`.
