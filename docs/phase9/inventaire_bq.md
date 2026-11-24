# Phase 9, étape 0 : inventaire de compatibilité BigQuery

Relevé du 24/11/2026 sur le dépôt au commit `34897c6` (fin de la phase 8) et la base `imf_dwh`
au 31/12/2025 (`dbt build` par défaut, 450 PASS). Aucun fichier du projet n'a été modifié.

**En bref.** Aucun modèle incrémental, aucun snapshot : les 46 modèles sont des tables ou des
vues reconstruites à chaque build. Le SQL propre à PostgreSQL est concentré dans 10 modèles, 1
macro et 3 tests : `date_trunc` et fin de mois par `interval` (10 lignes dans 6 modèles),
différences de dates (2), `distinct on` (1), `bool_and` (2), `isodow` (2), `age` (1), `to_char`
(1), expressions régulières `~` et casts `::` de la macro de typage, `filter (where …)` dans 2
tests. Une différence de comportement est à corriger dans un 11e modèle (`least` et NULL,
§ 2.2). Le reste est
du typage : 134 `cast(… as text)` dans le SQL, 164 `data_type: text` dans les contrats et 12
`text` dans les types de seeds, à passer en `STRING`. Volume total : environ 150 Mo côté
PostgreSQL, index compris.

## 1. Matérialisations

Aucune configuration dans les fichiers `.sql` (`config(materialized=…)` absent) : tout vient de
`dbt/dbt_project.yml`.

| Dossier | Matérialisation | Schéma | Modèles | Contrat |
|---|---|---|---:|---|
| `models/silver/staging/` | `view` | silver | 12 (`stg_*`) | non |
| `models/silver/` | `table` | silver | 12 (`slv_*`) | appliqué |
| `models/silver/intermediate/` | `table` | silver | 3 (`int_evenements_comptables`, `int_evenements_rejetes`, `int_mouvements_compte`) | appliqué |
| `models/gold/dims/` | `table` | gold | 8 | appliqué |
| `models/gold/facts/` | `table` | gold | 6 | appliqué |
| `models/gold/marts/` | `table` | gold | 5 | appliqué |
| **Total** | 34 `table`, 12 `view` | | **46** | 34 contrats |

- **`incremental` : aucun** (S14 : tables reconstruites à chaque build).
- **Snapshots : aucun** (pas de dossier `dbt/snapshots/`, `dbt ls --resource-type snapshot` vide).
- Seeds : 6 (`+full_refresh: true`, schéma `silver`).
- Schémas personnalisés par `generate_schema_name` (Jinja seul, sans SQL) : deviendront des
  datasets BigQuery `silver` et `gold`.

## 2. SQL propre à PostgreSQL

### 2.1 Modèles et macros

| Fichier | Ligne | PostgreSQL | Équivalent BigQuery |
|---|---:|---|---|
| `models/gold/facts/fct_solde_compte_mensuel.sql` | 10 | `date_trunc('month', date) <= date_trunc('month', arrete)` | `DATE_TRUNC(date, MONTH)` (ordre des arguments inversé ; renvoie une `DATE`, pas un horodatage) |
| `models/gold/facts/fct_solde_compte_mensuel.sql` | 20 | `(date_trunc('month', date) + interval '1 month - 1 day')::date` | `LAST_DAY(date, MONTH)` |
| `models/gold/marts/mart_rapprochements.sql` | 17 | `date_trunc('month', …)` | `DATE_TRUNC(…, MONTH)` |
| `models/gold/marts/mart_bilan.sql` | 17 | `date_trunc('month', …)` | `DATE_TRUNC(…, MONTH)` |
| `models/gold/marts/mart_bilan.sql` | 30 | `(date_trunc('month', e.date_ecriture) + interval '1 month - 1 day')::date` | `LAST_DAY(e.date_ecriture, MONTH)` |
| `models/gold/marts/mart_balance.sql` | 14 | `date_trunc('month', …)` | `DATE_TRUNC(…, MONTH)` |
| `models/gold/marts/mart_balance.sql` | 21 | `(date_trunc('month', date_ecriture) + interval '1 month - 1 day')::date` | `LAST_DAY(date_ecriture, MONTH)` |
| `models/gold/marts/mart_compte_resultat.sql` | 16 | `date_trunc('month', …)` | `DATE_TRUNC(…, MONTH)` |
| `models/gold/marts/mart_compte_resultat.sql` | 29, 30 | `bool_and(nature = 'PRODUIT')` | `LOGICAL_AND(nature = 'PRODUIT')` |
| `models/gold/marts/mart_compte_resultat.sql` | 40 | `(date_trunc('month', e.date_ecriture) + interval '1 month - 1 day')::date` | `LAST_DAY(e.date_ecriture, MONTH)` |
| `models/gold/dims/dim_date.sql` | 18 | `to_char(date_day, 'YYYY-MM')` | `FORMAT_DATE('%Y-%m', date_day)` |
| `models/gold/dims/dim_date.sql` | 20, 27 | `extract(isodow from date_day)` (1 = lundi … 7 = dimanche) | `EXTRACT(DAYOFWEEK …)` renvoie 1 = **dimanche** … 7 = samedi : utiliser `CAST(FORMAT_DATE('%u', date_day) AS INT64)` |
| `models/gold/dims/dim_date.sql` | 24 | `(date_trunc('month', date_day) + interval '1 month - 1 day')::date` | `LAST_DAY(date_day, MONTH)` |
| `models/gold/dims/dim_date.sql` | 16, 17, 19, 22, 23 | `extract(year / month / quarter from …)` | identique (`EXTRACT(YEAR FROM …)`, etc.) : compatible |
| `models/gold/dims/dim_client.sql` | 11 | `extract(year from age(arrete, date_naissance))` (années révolues) | `DATE_DIFF(arrete, date_naissance, YEAR) - IF(FORMAT_DATE('%m%d', arrete) < FORMAT_DATE('%m%d', date_naissance), 1, 0)` : `DATE_DIFF(…, YEAR)` seul compte les changements d'année, pas les années révolues |
| `models/gold/facts/fct_ecritures.sql` | 71–73 | `select distinct on (id_ecriture) … order by id_ecriture, priorite, code_journal` | `QUALIFY ROW_NUMBER() OVER (PARTITION BY id_ecriture ORDER BY priorite, code_journal) = 1` |
| `models/gold/facts/fct_echeances.sql` | 63 | `coalesce(cv.date_couverture, arrete) - e.date_prevue` (date − date = entier) | `DATE_DIFF(coalesce(cv.date_couverture, arrete), e.date_prevue, DAY)` |
| `models/gold/facts/fct_portefeuille_quotidien.sql` | 83 | `cj.jour - r.plus_ancienne_impayee` | `DATE_DIFF(cj.jour, r.plus_ancienne_impayee, DAY)` |
| `models/silver/slv_produits_credit.sql` | 6, 7 | `cast(… as numeric(6,4))` | `NUMERIC(6,4)` existe (type paramétré) : compatible |
| `models/silver/slv_credits.sql` | 12 | `cast(taux_annuel as numeric(6,4))` | idem, compatible |
| `macros/typage.sql` (`vers_bigint`) | 8 | `trim(x) ~ '^[-+]?[0-9]{1,18}$'` puis `trim(x)::bigint` | `REGEXP_CONTAINS(TRIM(x), r'^[-+]?[0-9]{1,18}$')` puis `CAST(TRIM(x) AS INT64)` (ou `SAFE_CAST(TRIM(x) AS INT64)`, qui renvoie NULL sur une valeur invalide) |
| `macros/typage.sql` (`vers_date`) | 17 | `trim(x) ~ '^[0-9]{4}-…$'` | `REGEXP_CONTAINS(TRIM(x), r'^[0-9]{4}-…$')` |
| `macros/typage.sql` (`vers_date`) | 19–21 | `substr(…)::int`, `make_date(a, m, 1) + interval '1 month' - interval '1 day'`, `extract(day from …)` | `CAST(SUBSTR(…) AS INT64)`, `LAST_DAY(DATE(a, m, 1), MONTH)` ; ou toute la macro en `SAFE.PARSE_DATE('%Y-%m-%d', TRIM(x))` après le contrôle de format (renvoie NULL pour un 30/02) |
| `macros/typage.sql` (`vers_date`) | 22 | `trim(x)::date` | `CAST(TRIM(x) AS DATE)` |

`~` dans `dim_date.sql` (3, 4, 9, 10) et `date_arrete.sql` (10) : concaténation **Jinja**, pas
du SQL, sans effet. `generate_series` : absent (`dim_date` utilise `dbt_utils.date_spine`,
portable). `string_agg`, `md5`, `ilike`, `distinct on` hors `fct_ecritures`, `filter (where …)`
dans les modèles : absents.

### 2.2 Différences de comportement, sans erreur de syntaxe

| Point | Où | PostgreSQL | BigQuery | Effet ici |
|---|---|---|---|---|
| `least` / `greatest` et NULL | 14 lignes : `mart_balance` (66, 67, 70, 71, 73), `mart_bilan` (116), `mart_compte_resultat` (79), `mart_rapprochements` (30, 69), `fct_solde_compte_mensuel` (34), `fct_echeances` (59, 63), `mart_kpi_portefeuille` (68), `stg_remboursements` (37) | ignore les NULL | renvoie NULL si un argument est NULL | Arguments non nuls (coalesce en amont, colonnes non nulles) sauf **`stg_remboursements.sql:37`** : `least(montant_paye, part_capital, part_interets, penalites) < 0` ; une part invalide (NULL après `vers_bigint`) masquerait un autre montant négatif en BigQuery. 0 ligne concernée aujourd'hui ; à rendre explicite (`coalesce`) |
| `date_trunc` sur une date | 7 modèles, 1 test | renvoie un `timestamp` (d'où les `::date`) | `DATE_TRUNC(date, MONTH)` renvoie une `DATE` | casts `::date` à retirer |
| `timestamp` sans fuseau | `slv_*.date_maj` (6 casts `as timestamp`), sources `ops_*.date_maj`, `_filigranes`, `_ingestions.filigrane_*` | horodatage local | `TIMESTAMP` = instant UTC ; l'équivalent est `DATETIME` | `date_maj` (date de l'événement à 20:00) → `DATETIME` |
| `is distinct from` | tests (5 fichiers) | supporté | supporté | compatible |
| Sous-requête corrélée `not exists` | `stg_remboursements.sql:38`, autres staging | supporté | supporté | compatible |

### 2.3 Tests singuliers (`dbt/tests`), exécutés aussi par `dbt build`

| Fichier | Ligne | PostgreSQL | Équivalent BigQuery |
|---|---:|---|---|
| `tests/marts/bilan_equilibre.sql` | 4, 5, 8, 9 | `sum(montant) filter (where cote = 'ACTIF')` | `SUM(IF(cote = 'ACTIF', montant, NULL))` |
| `tests/marts/kpi_a_l_arrete_egal_portefeuille.sql` | 15 | `sum(encours) filter (where jours_retard > 30)` | `SUM(IF(jours_retard > 30, encours, NULL))` |
| `tests/marts/rapprochements_grille_complete.sql` | 6 | `date_trunc('month', …)` | `DATE_TRUNC(…, MONTH)` |
| `tests/gold/ecritures_dans_exercice.sql` | 4 | `extract(year from date_ecriture)` | identique : compatible |

### 2.4 Types

| Où | `text` | `bigint` | `integer` | `smallint` | `numeric(6,4)` | `date` | `boolean` | `timestamp` |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Casts `as …` dans les modèles et macros | 134 | 38 | 13 | 4 | 3 | 30 | 7 | 6 |
| Casts `::…` (macro `typage.sql`, marts) | — | 1 | 3 (`::int`) | — | — | 6 | — | — |
| `data_type` des contrats (`_*.yml`) | 164 | 48 | 13 | 8 | 6 | 34 | 7 | 6 |
| `column_types` des seeds | 12 | — | 1 | — | — | — | — | — |
| **Type BigQuery** | `STRING` | `INT64` | `INT64` | `INT64` | `NUMERIC(6,4)` | `DATE` | `BOOL` | `DATETIME` |

`text` n'existe pas en BigQuery (`STRING`) ; `bigint`, `integer` et `smallint` y sont acceptés
comme alias d'`INT64` dans un `CAST`, mais les contrats comparent le type déclaré au type réel
(`INT64`) : les `data_type` des contrats et les `column_types` des seeds devront être exprimés
dans les deux dialectes (macros `dbt.type_string()`, `dbt.type_bigint()`… ou valeurs par cible).

## 3. Taille des schémas de `imf_dwh`

`pg_total_relation_size` (table + index + TOAST), au 31/12/2025 après `dbt build` par défaut.

| Schéma | Tables | Vues | Taille | Octets |
|---|---:|---:|---:|---:|
| bronze | 14 | 0 | 34 Mo | 35 545 088 |
| silver | 21 | 12 | 39 Mo | 41 361 408 |
| gold | 19 | 0 | 78 Mo | 81 395 712 |
| audit | 1 | 0 | 1,2 Mo | 1 228 800 |
| **Total** | 55 | 12 | **≈ 152 Mo** | 159 531 008 |

Plus grosses tables gold : `fct_portefeuille_quotidien` (404 573 lignes, 35 Mo),
`fct_ecritures` (181 193 lignes, 28 Mo), `fct_operations` (66 514 lignes, 7 Mo). La taille
logique BigQuery sera différente (pas d'index, stockage en colonnes), et très en dessous de la
limite de stockage du bac à sable (10 Go).

## 4. Sources dbt : tables bronze

14 tables du schéma `bronze` déclarées en source (`dbt/models/bronze/sources.yml`), plus la
source `audit.audit_runs` (phase 7), reprise en fin de section. Types proposés : `text`,
`varchar(n)`, `char(n)` → `STRING` ; `bigint`, `integer`, `smallint` → `INT64` ;
`numeric(p,s)` → `NUMERIC(p,s)` ; `date` → `DATE` ; `timestamp with time zone` → `TIMESTAMP` ;
`timestamp without time zone` → `DATETIME` ; `text[]` → `ARRAY<STRING>`. Les CSV (`csv_*`,
`meta_catalogue_anomalies`) restent tout en `STRING` : le typage est fait en silver par
`vers_bigint` / `vers_date` (S4). `meta_catalogue_anomalies` a une colonne nommée `table`, mot
clé SQL : à citer (`` `table` ``) en BigQuery comme en PostgreSQL.

| Table | Lignes | Colonnes |
|---|---:|---:|
| `bronze._filigranes` | 6 | 2 |
| `bronze._ingestions` | 4 380 | 13 |
| `bronze.csv_agences` | 6 | 10 |
| `bronze.csv_appro_caisse` | 141 | 9 |
| `bronze.csv_charges` | 229 | 11 |
| `bronze.csv_operations` | 68 848 | 12 |
| `bronze.csv_ouverture` | 6 | 9 |
| `bronze.meta_catalogue_anomalies` | 2 916 | 11 |
| `bronze.ops_clients` | 2 000 | 14 |
| `bronze.ops_comptes` | 2 317 | 11 |
| `bronze.ops_credits` | 3 000 | 16 |
| `bronze.ops_echeancier` | 34 037 | 12 |
| `bronze.ops_produits_credit` | 4 | 12 |
| `bronze.ops_remboursements` | 11 918 | 14 |
| `audit.audit_runs` | 3 201 | 20 |

#### `bronze._filigranes` — 6 lignes, 2 colonnes

| Colonne | Type PostgreSQL | Null | Type BigQuery |
|---|---|:---:|---|
| `table_source` | text | non | STRING |
| `filigrane` | timestamp without time zone | non | DATETIME |

#### `bronze._ingestions` — 4 380 lignes, 13 colonnes

| Colonne | Type PostgreSQL | Null | Type BigQuery |
|---|---|:---:|---|
| `id_run` | text | non | STRING |
| `empreinte_generation` | char(64) | non | STRING |
| `jour` | date | non | DATE |
| `source` | text | non | STRING |
| `objet` | text | non | STRING |
| `chemin` | text | oui | STRING |
| `sha256` | char(64) | oui | STRING |
| `nb_lignes` | integer | non | INT64 |
| `filigrane_avant` | timestamp without time zone | oui | DATETIME |
| `filigrane_apres` | timestamp without time zone | oui | DATETIME |
| `statut` | text | non | STRING |
| `debut` | timestamp with time zone | non | TIMESTAMP |
| `fin` | timestamp with time zone | non | TIMESTAMP |

#### `bronze.csv_agences` — 6 lignes, 10 colonnes

| Colonne | Type PostgreSQL | Null | Type BigQuery |
|---|---|:---:|---|
| `id_agence` | text | oui | STRING |
| `nom` | text | oui | STRING |
| `ville` | text | oui | STRING |
| `region` | text | oui | STRING |
| `type_agence` | text | oui | STRING |
| `_id_run` | text | non | STRING |
| `_source` | text | non | STRING |
| `_num_ligne` | integer | non | INT64 |
| `_sha256` | char(64) | non | STRING |
| `_charge_le` | timestamp with time zone | non | TIMESTAMP |

#### `bronze.csv_appro_caisse` — 141 lignes, 9 colonnes

| Colonne | Type PostgreSQL | Null | Type BigQuery |
|---|---|:---:|---|
| `id_appro` | text | oui | STRING |
| `id_agence` | text | oui | STRING |
| `date_appro` | text | oui | STRING |
| `montant` | text | oui | STRING |
| `_id_run` | text | non | STRING |
| `_source` | text | non | STRING |
| `_num_ligne` | integer | non | INT64 |
| `_sha256` | char(64) | non | STRING |
| `_charge_le` | timestamp with time zone | non | TIMESTAMP |

#### `bronze.csv_charges` — 229 lignes, 11 colonnes

| Colonne | Type PostgreSQL | Null | Type BigQuery |
|---|---|:---:|---|
| `id_charge` | text | oui | STRING |
| `id_agence` | text | oui | STRING |
| `date_charge` | text | oui | STRING |
| `categorie` | text | oui | STRING |
| `canal` | text | oui | STRING |
| `montant` | text | oui | STRING |
| `_id_run` | text | non | STRING |
| `_source` | text | non | STRING |
| `_num_ligne` | integer | non | INT64 |
| `_sha256` | char(64) | non | STRING |
| `_charge_le` | timestamp with time zone | non | TIMESTAMP |

#### `bronze.csv_operations` — 68 848 lignes, 12 colonnes

| Colonne | Type PostgreSQL | Null | Type BigQuery |
|---|---|:---:|---|
| `id_operation` | text | oui | STRING |
| `id_compte` | text | oui | STRING |
| `id_agence` | text | oui | STRING |
| `date_operation` | text | oui | STRING |
| `type_operation` | text | oui | STRING |
| `canal` | text | oui | STRING |
| `montant` | text | oui | STRING |
| `_id_run` | text | non | STRING |
| `_source` | text | non | STRING |
| `_num_ligne` | integer | non | INT64 |
| `_sha256` | char(64) | non | STRING |
| `_charge_le` | timestamp with time zone | non | TIMESTAMP |

#### `bronze.csv_ouverture` — 6 lignes, 9 colonnes

| Colonne | Type PostgreSQL | Null | Type BigQuery |
|---|---|:---:|---|
| `id_agence` | text | oui | STRING |
| `date_ouverture` | text | oui | STRING |
| `canal` | text | oui | STRING |
| `montant` | text | oui | STRING |
| `_id_run` | text | non | STRING |
| `_source` | text | non | STRING |
| `_num_ligne` | integer | non | INT64 |
| `_sha256` | char(64) | non | STRING |
| `_charge_le` | timestamp with time zone | non | TIMESTAMP |

#### `bronze.meta_catalogue_anomalies` — 2 916 lignes, 11 colonnes

| Colonne | Type PostgreSQL | Null | Type BigQuery |
|---|---|:---:|---|
| `nature` | text | oui | STRING |
| `table` | text | oui | STRING |
| `id_ligne` | text | oui | STRING |
| `nombre` | text | oui | STRING |
| `traitement_attendu` | text | oui | STRING |
| `date_ligne` | text | oui | STRING |
| `_id_run` | text | non | STRING |
| `_source` | text | non | STRING |
| `_num_ligne` | integer | non | INT64 |
| `_sha256` | char(64) | non | STRING |
| `_charge_le` | timestamp with time zone | non | TIMESTAMP |

#### `bronze.ops_clients` — 2 000 lignes, 14 colonnes

| Colonne | Type PostgreSQL | Null | Type BigQuery |
|---|---|:---:|---|
| `id_client` | varchar(12) | oui | STRING |
| `id_agence` | varchar(8) | oui | STRING |
| `prenom` | text | oui | STRING |
| `nom` | text | oui | STRING |
| `sexe` | char(1) | oui | STRING |
| `date_naissance` | date | oui | DATE |
| `secteur_activite` | varchar(20) | oui | STRING |
| `date_adhesion` | date | oui | DATE |
| `date_maj` | timestamp without time zone | oui | DATETIME |
| `_id_run` | text | non | STRING |
| `_source` | text | non | STRING |
| `_num_ligne` | integer | non | INT64 |
| `_sha256` | char(64) | non | STRING |
| `_charge_le` | timestamp with time zone | non | TIMESTAMP |

#### `bronze.ops_comptes` — 2 317 lignes, 11 colonnes

| Colonne | Type PostgreSQL | Null | Type BigQuery |
|---|---|:---:|---|
| `id_compte` | varchar(12) | oui | STRING |
| `id_client` | varchar(12) | oui | STRING |
| `type_compte` | varchar(10) | oui | STRING |
| `date_ouverture` | date | oui | DATE |
| `statut` | varchar(10) | oui | STRING |
| `date_maj` | timestamp without time zone | oui | DATETIME |
| `_id_run` | text | non | STRING |
| `_source` | text | non | STRING |
| `_num_ligne` | integer | non | INT64 |
| `_sha256` | char(64) | non | STRING |
| `_charge_le` | timestamp with time zone | non | TIMESTAMP |

#### `bronze.ops_credits` — 3 000 lignes, 16 colonnes

| Colonne | Type PostgreSQL | Null | Type BigQuery |
|---|---|:---:|---|
| `id_credit` | varchar(12) | oui | STRING |
| `id_client` | varchar(12) | oui | STRING |
| `id_compte_epargne` | varchar(12) | oui | STRING |
| `code_produit` | varchar(20) | oui | STRING |
| `date_decaissement` | date | oui | DATE |
| `montant_accorde` | bigint | oui | INT64 |
| `frais_dossier` | bigint | oui | INT64 |
| `duree_mois` | smallint | oui | INT64 |
| `taux_annuel` | numeric(6,4) | oui | NUMERIC(6,4) |
| `statut` | varchar(10) | oui | STRING |
| `date_maj` | timestamp without time zone | oui | DATETIME |
| `_id_run` | text | non | STRING |
| `_source` | text | non | STRING |
| `_num_ligne` | integer | non | INT64 |
| `_sha256` | char(64) | non | STRING |
| `_charge_le` | timestamp with time zone | non | TIMESTAMP |

#### `bronze.ops_echeancier` — 34 037 lignes, 12 colonnes

| Colonne | Type PostgreSQL | Null | Type BigQuery |
|---|---|:---:|---|
| `id_credit` | varchar(12) | oui | STRING |
| `num_echeance` | smallint | oui | INT64 |
| `date_echeance` | date | oui | DATE |
| `capital` | bigint | oui | INT64 |
| `interets` | bigint | oui | INT64 |
| `montant` | bigint | oui | INT64 |
| `date_maj` | timestamp without time zone | oui | DATETIME |
| `_id_run` | text | non | STRING |
| `_source` | text | non | STRING |
| `_num_ligne` | integer | non | INT64 |
| `_sha256` | char(64) | non | STRING |
| `_charge_le` | timestamp with time zone | non | TIMESTAMP |

#### `bronze.ops_produits_credit` — 4 lignes, 12 colonnes

| Colonne | Type PostgreSQL | Null | Type BigQuery |
|---|---|:---:|---|
| `code_produit` | varchar(20) | oui | STRING |
| `libelle` | text | oui | STRING |
| `taux_annuel` | numeric(6,4) | oui | NUMERIC(6,4) |
| `taux_frais_dossier` | numeric(6,4) | oui | NUMERIC(6,4) |
| `duree_min_mois` | smallint | oui | INT64 |
| `duree_max_mois` | smallint | oui | INT64 |
| `date_maj` | timestamp without time zone | oui | DATETIME |
| `_id_run` | text | non | STRING |
| `_source` | text | non | STRING |
| `_num_ligne` | integer | non | INT64 |
| `_sha256` | char(64) | non | STRING |
| `_charge_le` | timestamp with time zone | non | TIMESTAMP |

#### `bronze.ops_remboursements` — 11 918 lignes, 14 colonnes

| Colonne | Type PostgreSQL | Null | Type BigQuery |
|---|---|:---:|---|
| `id_remboursement` | varchar(12) | oui | STRING |
| `id_credit` | varchar(12) | oui | STRING |
| `date_remboursement` | date | oui | DATE |
| `montant_paye` | bigint | oui | INT64 |
| `part_capital` | bigint | oui | INT64 |
| `part_interets` | bigint | oui | INT64 |
| `penalites` | bigint | oui | INT64 |
| `canal` | varchar(20) | oui | STRING |
| `date_maj` | timestamp without time zone | oui | DATETIME |
| `_id_run` | text | non | STRING |
| `_source` | text | non | STRING |
| `_num_ligne` | integer | non | INT64 |
| `_sha256` | char(64) | non | STRING |
| `_charge_le` | timestamp with time zone | non | TIMESTAMP |

#### `audit.audit_runs` (source dbt hors bronze) — 3 201 lignes, 20 colonnes

| Colonne | Type PostgreSQL | Null | Type BigQuery |
|---|---|:---:|---|
| `id_audit` | bigint | non | INT64 |
| `dag_id` | text | non | STRING |
| `run_id` | text | non | STRING |
| `date_logique` | date | non | DATE |
| `etape` | text | non | STRING |
| `tentative` | integer | non | INT64 |
| `statut` | text | non | STRING |
| `debut` | timestamp with time zone | non | TIMESTAMP |
| `fin` | timestamp with time zone | non | TIMESTAMP |
| `duree_s` | numeric(10,3) | non | NUMERIC(10,3) |
| `lignes_chargees` | bigint | oui | INT64 |
| `nb_pass` | integer | oui | INT64 |
| `nb_warn` | integer | oui | INT64 |
| `nb_error` | integer | oui | INT64 |
| `nb_skip` | integer | oui | INT64 |
| `noeuds_en_echec` | text[] | oui | ARRAY<STRING> (BigQuery n'admet pas de NULL dans un tableau) |
| `noeuds_sautes` | text[] | oui | ARRAY<STRING> |
| `version_mapping` | text | oui | STRING |
| `commit_git` | text | oui | STRING |
| `message` | text | oui | STRING |
