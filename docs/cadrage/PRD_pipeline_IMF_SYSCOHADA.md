# PRD – Pipeline de données d'une institution de microfinance (IMF) & états financiers (logique SYSCOHADA)

> **Document de cadrage (cahier des charges / PRD)** du projet portfolio n°1.
> **Version publique allégée** : sans les éléments propres à l'organisation personnelle du projet.
> **Version 1.1 du 15/11/2026** : phase 0 (cadrage) terminée. Les décisions et le modèle détaillé sont dans `P1_phase0_cadrage.md`, qui complète ce PRD.
> **Version 1.2 du 20/11/2026** : cloud (Google Cloud Storage + BigQuery) intégré au plan, en phase 9 ; titre précisé (« logique SYSCOHADA »).
> **Version 1.3 du 21/11/2026** : cadrage de référence = `P1_phase0_cadrage.md` **v0.2** (D1 à D17) ; structure du repo complétée (§10) ; outils de l'environnement Python fixés (§8.2 : uv, ruff, mypy) ; PostgreSQL en une instance à deux bases, `imf_ops` et `imf_dwh` (§8.1) ; §8.3 replacé avant §8.4 ; chemins des documents de cadrage corrigés.
> **Version 1.4 du 21/11/2026** (cadrage de la phase 2) : cadrage de référence = `P1_phase0_cadrage.md` **v0.3** (D1 à D21) ; nouvelles sources `appro_caisse` (approvisionnement des caisses par la banque, D18) et `produits_credit` ; colonne `traitement_attendu` dans `catalogue_anomalies` (D21) ; répartition des sources entre `imf_ops` et CSV, CSV des opérations découpés par jour (§6.1) ; journal VIR (§6.3) ; tests banque ≥ 0 et TEG ≤ 24 % (§8.3) ; Faker retiré au profit de `random` seul (§8.2) ; décisions de la phase 2 dans `P1_phase2_cadrage.md`.
> **Version 1.5 du 21/11/2026** (phases 2 et 3 terminées) : `charges` et `appro_caisse` découpés par jour (§6.1, I11) ; `date_maj` des crédits = date de décaissement (I10, remplace la règle des crédits soldés de `P1_phase2_cadrage.md` 9.1) ; décaissements selon une courbe mensuelle, aucun en janvier (§5, I14) ; zone de landing des extractions `imf_ops` et modules d'ingestion (§10) ; limites complétées (§12). Décisions de la phase 3 dans `P1_phase3_cadrage.md`.
> **Version 1.6 du 22/11/2026** (phases 4, 5 et 6 terminées) : écarts reportés depuis `P1_phase4_cadrage.md` (S1–S17), `P1_phase5_cadrage.md` (G1–G15) et `P1_phase6_cadrage.md` (H1–H12). Grain de `fct_portefeuille_quotidien` en jours calendaires (H1) ; `mart_rapprochements` ajouté, `audit_runs` déplacé en phase 7 (§6.2) ; seeds v0.5 (`journaux.type_evenement`, `plan_comptes.rubrique_solde_inverse`) (§6.3) ; définitions du PAR 30 et du taux de remboursement précisées (§7) ; tests complétés (§8.3) ; sous-dossier `silver/staging/`, `docs/cadrage/` et cas chiffrés (§10) ; phases 4 à 6 terminées (§9) ; limites complétées (§12).
> **Version 1.7 du 22/11/2026** (phase 7 terminée) : écarts reportés depuis `P1_phase7_cadrage.md` (J1–J20). `catalogue_anomalies.date_ligne` (§6.1, J16) ; gold « à date » : variable `date_arrete`, `date_situation`, `dim_credit.statut_a_l_arrete` ; `audit.audit_runs` (§6.2, J2, J13, J15, J17) ; schéma `audit` et orchestration (§8.1) ; Airflow 3.3.2, image à deux environnements, dépôt monté en lecture seule (§8.2, J6, J7) ; tests ramenés à l'arrêté, contrôles de complétude et de volume (§8.3, J3, J4, J12, J18) ; phase 7 terminée (§9) ; paquet `orchestration/`, `airflow/plugins/` abandonné (§10, J19) ; mois partiel et limite I10 neutralisée (§12, J15, J17).

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
- Charges à payer (ex. commissions mobile money de décembre, facturées en janvier suivant).
- Compensation des comptes de liaison (mobile money, agents) ; comptes de tiers individuels par agent.
- Versements des excédents de caisse vers la banque.
- Écriture de clôture (virement du résultat).
- Bilan par agence.
- SCD type 2 sur `dim_client` (bonus).
- Write-audit-publish (publication du gold seulement après tests verts) ; astronomer-cosmos (bonus, J1).
- Streaming temps réel.
- Spark : volume trop faible pour le justifier ici.
- Déploiement cloud **complet** (Airflow ou PostgreSQL managés). En revanche, l'entrepôt BigQuery et la zone brute Cloud Storage **font partie du plan** (phase 9, section 8.4).
- Machine learning (scoring de crédit).
- Conformité réglementaire réelle (reporting BCEAO).

### Référentiel comptable : option hybride (décidée en phase 0)
Dans l'UMOA, les SFD appliquent le **Référentiel comptable spécifique des SFD (RCSFD)**, institué par l'Instruction BCEAO n° 025-02-2009, et non le SYSCOHADA général. Le projet utilise donc :
- des **codes de comptes internes stables** (ex. `TRESO_CAISSE`), qui découplent le pipeline de toute numérotation ;
- une colonne **`compte_sfd`**, à remplir après relecture par un comptable d'IMF (checklist : `P1_checklist_relecture_SFD.md`) ;
- une colonne **`compte_syscohada_equiv`** avec un **`statut_correspondance`** (EQUIVALENT / APPROXIMATIF / A_VERIFIER), qui sert de pont vers le SYSCOHADA général. Les numéros sont indicatifs.

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
| `credits` | id, client, produit, montant accordé, **frais de dossier**, taux, durée, date de décaissement, **compte d'épargne crédité**, statut (renommé `statut_au_31_12` en silver, S9) | `imf_ops` | MVP |
| `echeancier` | id crédit, n° échéance, date prévue, capital dû, intérêts dus | `imf_ops` | MVP |
| `remboursements` | id, crédit, date, montant payé, part capital, part intérêts, pénalités, **canal** (GUICHET, AGENT, MOBILE, PRELEVEMENT). Imputation pénalités → intérêts → capital, échéance par échéance | `imf_ops` | MVP |
| **`charges`** | id, date, agence, catégorie (PERSONNEL, LOYERS, TELECOM_SI, FOURNITURES, COMMISSIONS_MM), montant, canal | CSV, **un fichier par jour** (I11) | MVP |
| **`ouverture`** | agence, canal (VIREMENT = banque, GUICHET = caisse), montant ; datée du 01/01 de l'exercice en gold (G7) | CSV (instantané) | MVP |
| **`appro_caisse`** | id, date, agence approvisionnée, montant (banque → caisse, D18) | CSV, **un fichier par jour** (I11) | MVP |
| **`catalogue_anomalies`** (sortie du générateur) | nature, table, id de ligne, nombre, **traitement attendu** (DEDOUBLONNER / REJETER / STANDARDISER / ACCEPTER_NULL), **`date_ligne`** (date de la ligne fautive ; les tests du catalogue ne retiennent que `date_ligne ≤ date_arrete`, J16) | CSV (instantané) | MVP |
| `provisions` | crédit, date, montant de dotation ou de reprise | — | BONUS |

Formats : CSV « exports d'agences et de la comptabilité » (`data/`) + PostgreSQL `imf_ops` « logiciel de gestion du portefeuille », pour simuler **plusieurs sources**. Les CSV d'événements sont découpés par jour (`data/<table>/date=AAAA-MM-JJ/<table>.csv` pour `operations`, `charges`, `appro_caisse`) ; les autres CSV sont des instantanés. Chaque table de `imf_ops` porte une colonne `date_maj`, filigrane de l'ingestion incrémentale : horodatage métier déterministe (date de l'événement à 20:00) ; pour un crédit et son échéancier, c'est **toujours la date de décaissement** (I10). Ainsi, à chaque jour J, tout enfant visible en bronze a son parent.

Les défauts injectés n'altèrent jamais la vérité propre (D21) : doublons, orphelins et lignes invalides sont des **lignes ajoutées** ; seules la casse ou les espaces (STANDARDISER) et les nulls sur des colonnes non critiques (ACCEPTER_NULL) touchent de vraies lignes. Les doublons et les orphelins ne sont injectés que dans les CSV ; `imf_ops` garde ses clés primaires et étrangères. Une anomalie n'enfreint qu'une seule règle (S16).

Les mouvements induits sur les comptes d'épargne (virement du crédit, frais de dossier, prélèvements de remboursement) ne figurent pas dans `operations` : ils sont dérivés en silver (`int_mouvements_compte`, S10), qui ne sert qu'aux soldes clients. Les écritures sont construites depuis les sources d'événements (G1). Chaque écriture n'a ainsi qu'**une seule source**.

La **vérité propre** du générateur (`data/_verite/`) est un oracle de test : elle n'entre jamais dans l'entrepôt et n'est lue que par pytest (S12), **hors DAG**, dans `make check` (J5).

La génération (`make generate`) reste **hors du DAG** : le générateur joue le monde extérieur, le DAG orchestre le pipeline (J1).

### 6.2 Modèle cible (gold) – schéma en étoile

Le détail (attributs, clés, volumes) est dans `P1_phase0_cadrage.md` §3 ; décisions gold dans `P1_phase5_cadrage.md`, gold « à date » dans `P1_phase7_cadrage.md`. Clés naturelles (G9) ; toutes les tables gold sous contrat dbt, reconstruites, sans incrémental (G14).

**Gold « à date » (phase 7).** Variable dbt **`date_arrete`** (défaut = 31/12 de l'exercice, lue par la macro `date_arrete()`) ; Airflow passe `{{ ds }}`. Le gold ne montre que ce qui est connu à la date d'arrêté : aucune date postérieure, sauf `dim_date` et `fct_echeances.date_prevue` (J2). Sans variable, le build est identique à celui de la phase 6.

**Dimensions (toutes MVP) :** `dim_date` (exercice + 2 ans), `dim_agence`, `dim_client` (SCD 1 ; SCD 2 en bonus), `dim_compte_client`, `dim_produit_credit`, `dim_credit` (avec **`statut_a_l_arrete`**, calculé depuis le silver ; `statut_au_31_12` reste descriptif, J17), `dim_compte_comptable`, `dim_journal`

**Faits (tous MVP) :**
- `fct_operations` (grain : une opération de compte client ; `est_activite_client` = false pour FRAIS_TENUE, G12)
- `fct_echeances` (grain : une échéance, crédit × n°)
- `fct_remboursements` (grain : un remboursement)
- `fct_portefeuille_quotidien` (grain : un crédit × **un jour calendaire**, du décaissement au solde ou à la date d'arrêté ; `est_jour_ouvre` ; encours, jours de retard) (H1, J2)
- `fct_solde_compte_mensuel` (grain : un compte client × une fin de mois de l'exercice, jusqu'à l'arrêté)
- `fct_ecritures` (grain : une ligne d'écriture comptable, débit/crédit ; avec `id_ecriture` = `source_table:source_id:type_evenement` (G4), `num_ligne`, journal, agence (agence du client, sinon de la source, G6), `type_evenement`, `source_table`, `source_id`, `version_mapping`)

**Marts finance (tous MVP)** — les marts mensuels portent **`date_situation = least(fin de mois, date_arrete)`** : le mois en cours est une situation intermédiaire (J15) :
- `mart_balance` (compte × agence × mois, balance à 6 colonnes, ouverture de janvier = 0, densifiée) (H5, H6)
- `mart_compte_resultat` (rubrique × mois + cumul) (H9)
- `mart_bilan` (rubrique × fin de mois, **niveau IMF**, soldes calculés sur les mouvements agrégés ; reclassement des soldes inversés ; ligne `RESULTAT_CUMULE`) (H7, H8)
- `mart_rapprochements` (fin de mois × agence × contrôle DEPOTS / CREDITS, grille complète ; gestion, compta, écart) (H10)
- `mart_kpi_portefeuille` (jour × agence × produit ; numérateurs et dénominateurs seulement) (H11)

**Journal d'exécution (MVP, phase 7) :** `audit.audit_runs`, en **ajout seul**, dans le schéma `audit` de `imf_dwh`. Une ligne par **étape × tentative**, écrite par l'étape elle-même à la fin de chaque tentative, plus une ligne `RUN` écrite par la tâche de teardown (une étape sans ligne = NON_EXECUTE). Déclarée en **source dbt**, pour la page qualité / fraîcheur du dashboard (phase 8) (J13).

### 6.3 Mapping opérations → écritures

Le mapping est porté par cinq **seeds dbt** (`dbt/seeds/`, **v0.5**, `full_refresh: true`), modifiables sans toucher au code. Moteur générique (G2) : événements au format long × `mapping_comptable`, `@TRESORERIE` résolu par le canal, aucun `CASE` sur les types. `version_mapping` = variable dbt, incrémentée à chaque changement d'un seed (G8).

| Seed | Rôle |
|---|---|
| `plan_comptes.csv` | Comptes : code interne, libellé, nature, sens normal, état, rubrique, **`rubrique_solde_inverse`** (v0.5, H8), `compte_sfd`, `compte_syscohada_equiv`, statut de correspondance, MVP |
| `mapping_comptable.csv` | Pour chaque type d'événement : lignes de l'écriture (sens, compte, champ du montant) |
| `mapping_canal_tresorerie.csv` | Résout le compte de trésorerie `@TRESORERIE` selon le canal : guichet → caisse, agent → liaison agents, mobile → liaison mobile money, virement → banque, prélèvement → compte d'épargne |
| `journaux.csv` | Journaux : OUV, VIR, CAI, AGT, MOB, BQ, OD, avec une priorité et **`type_evenement`** (v0.4, G5) : le journal du type d'événement prime sur celui du canal |
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

> **Règle : aucune affectation par défaut.** Un événement sans règle de mapping va dans `int_evenements_rejetes` (motif TYPE_SANS_REGLE, CANAL_SANS_TRESORERIE ou COMPTE_HORS_PLAN, G3), qui doit rester vide (test bloquant) ; complétude : événements = pièces + rejets.

## 7. Indicateurs (KPI)

| KPI | Définition | Source |
|---|---|---|
| Encours brut de crédit | Montant accordé − Σ part capital remboursée à la date | `mart_kpi_portefeuille` |
| PAR 30 (portefeuille à risque) | Encours des crédits avec **plus de 30 jours** de retard (31 inclus) / encours total ; retard en FIFO cumulé (G11), même définition que le générateur | `mart_kpi_portefeuille` |
| Taux de remboursement | Σ min(cumul payé capital + intérêts, cumul dû échu) **par crédit** / Σ cumul dû échu ; échue = date prévue ≤ jour ; crédits soldés inclus (H11) | `mart_kpi_portefeuille` |
| Volume des dépôts et retraits | Par jour, mois, agence, canal | `fct_operations` (Power BI) |
| Encours d'épargne | Solde total des comptes clients | `fct_solde_compte_mensuel` (Power BI) |
| Produits d'intérêts | Intérêts encaissés sur la période | `mart_compte_resultat` / `fct_ecritures` |
| Clients actifs | Clients ayant eu au moins une opération sur la période, hors FRAIS_TENUE | `fct_operations` (Power BI, comptage distinct) |
| Équilibre comptable | Total débit = total crédit (contrôle) | `fct_ecritures`, `mart_balance` |
| Rapprochements | Écart gestion ↔ comptabilité sur les dépôts et les crédits (attendu : 0) | `mart_rapprochements` |
| Fraîcheur et qualité des runs | Date d'arrêté du dernier run réussi (« données arrêtées au »), statut et durée par étape, tentatives | `audit.audit_runs` (Power BI, phase 8) |

Les marts stockent les numérateurs et les dénominateurs, jamais les ratios : Power BI les recalcule à chaque niveau d'agrégation.

## 8. Solution technique

### 8.1 Architecture

```
[Générateur Python (random)]   ← hors DAG (make generate)
        │  CSV agences (data/) + base opérationnelle PostgreSQL (imf_ops) + catalogue des anomalies
        ▼
[Ingestion Python] ──► BRONZE (entrepôt imf_dwh : données brutes, horodatées, incrémentales)
        ▼
[dbt] ──► SILVER (nettoyage, typage, dédoublonnage, standardisation, mouvements induits)
        ▼
[dbt --vars date_arrete] ──► GOLD « à date » (schéma en étoile + écritures + marts finance)
        ▼
[Power BI] Dashboards : pilotage portefeuille + états financiers + qualité

Orchestration : Airflow 3 (DAG imf_quotidien, @daily) → audit.audit_runs
Conteneurs : Docker Compose · CI : GitHub Actions (phase 9)

Phase 9 (cloud) : fichiers bronze copiés dans Google Cloud Storage ;
même projet dbt exécuté aussi sur BigQuery (cible `bq`).
```

PostgreSQL (MVP) : **une instance, deux bases**. `imf_ops` joue la base opérationnelle (source) ; `imf_dwh` est l'entrepôt, avec les schémas `bronze`, `silver`, `gold` et **`audit`** (journal d'exécution, phase 7) (schémas exacts via `generate_schema_name`, seeds dans `silver`, S2). Les deux bases et les schémas sont créés au premier démarrage par `docker/postgres/init/`. Les tables de `imf_ops` sont créées et rechargées par le générateur (`generator/sql/imf_ops.sql`). Les tables bronze sont créées par l'ingestion (`ingestion/sql/bronze.sql`) ; les extractions de `imf_ops` passent par une zone de landing (`data/landing/imf_ops/`) avant le chargement (I8). Les métadonnées d'Airflow ont leur propre base (`airflow-db`), séparée de l'entrepôt (J6).

**DAG `imf_quotidien` (phase 7, J8–J11, J19).** `@daily` sur l'exercice, `max_active_runs=1`, `depends_on_past=True` (pas de J+1 sur un J en échec), backfill Airflow 3 ; un run sans `logical_date` est refusé. Sept tâches :

`verifier_environnement` → `attendre_fichiers` (capteur, mode reschedule) → `ingerer` → `controler_completude` (**bloquant**) → `controler_volume` (**avertissement**) → `dbt_build --vars date_arrete={{ ds }}` → `ecrire_audit` (**teardown** : s'exécute toujours, ne rend pas le run vert).

Les tâches sont des `@task` Python qui lancent le CLI `python -m orchestration …` dans le venv du projet, avec un **contrat de codes de sortie** : 0 = succès ; 3 = échec de contrôle (`AirflowFailException`, **sans retry**) ; autre = erreur technique (retry). La dernière ligne de sortie est un résumé JSON (XCom). Pour dbt, `run_results.json` est lu : `error` / `fail` / `skipped` → échec sans retry ; erreur technique → retry. Retries : 2, 2 min, backoff exponentiel — pour l'infrastructure seulement. Le code qui accède aux bases se connecte par les variables `POSTGRES_*` (comme dbt et l'ingestion), sans connexion Airflow (J20).

### 8.2 Outils

| Outil | Rôle | Pourquoi |
|---|---|---|
| Python 3.12 (`random`) | Génération | Simple, typable, testable ; une seule source d'aléa (`random.Random`), donc une reproductibilité qui ne dépend d'aucune bibliothèque tierce ; Faker écarté en v1.4 (aucune colonne n'en a besoin) ; version fixée dans `.python-version` |
| psycopg 3 | Chargement de `imf_ops` et ingestion bronze (COPY) | Pilote PostgreSQL moderne, typé |
| pandas/polars | Non utilisés (I13) ; à réévaluer si besoin | Bronze ne transforme rien |
| uv | Dépendances, environnement virtuel, version de Python, fichier lock ; dbt dans un groupe `dbt` (S1) | Un seul outil, standard `pyproject.toml`, `uv.lock` reproductible, très rapide |
| ruff | Lint et formatage | Remplace flake8, isort et black en un outil |
| mypy | Vérification des types | Les type hints sont contrôlés, pas décoratifs |
| PostgreSQL 17 | Base opérationnelle + entrepôt (MVP) | Robuste, gratuit, connu |
| dbt Core (≥ 1.8, tests unitaires) | Transformations, tests, documentation, lineage | Standard du marché |
| Apache Airflow **3.3.2** (épinglé) | Orchestration quotidienne, retries. LocalExecutor, `parallelism` 2, sans triggerer, `mem_limit` par service, profil compose `airflow`, auth FAB (J6). **Image `airflow/Dockerfile` à deux environnements** : celui d'Airflow (sans dbt) et le venv du projet `/opt/pipeline-venv` (`uv sync --frozen`, sans Airflow) ; **dépôt monté en lecture seule**, seul `data/` en écriture ; artefacts dbt dans le conteneur ; `PYTHONDONTWRITEBYTECODE=1` (J7) | Standard de l'orchestration. 3.4.0 (sortie le 06/11/2026) écartée : version .0 trop récente. Deux environnements : conflit de dépendances avec dbt. Lecture seule : le conteneur ne peut modifier ni le code ni `.env`. Réglages mémoire : poste de dev à 7,6 Go de RAM sous WSL2 |
| Docker / docker-compose | Environnement reproductible | Lancement en une commande |
| pytest | Tests Python (générateur, ingestion, socle, orchestration, comparaison à la vérité) | Fiabilité du code |
| GitHub Actions | CI : lint (ruff), types (mypy), tests, `dbt build` | Pratiques professionnelles |
| Power BI | Dashboard | Outil BI de référence, modèle sémantique et mesures DAX |
| Google Cloud Storage + BigQuery | Zone brute et entrepôt cloud (phase 9) | Un cloud gratuit et durable (bac à sable BigQuery, sans carte bancaire) |
| *(Bonus)* Terraform | Création du bucket et des datasets | Infrastructure recréable à l'identique |

Poste de développement : Windows 11 + **WSL2** (Ubuntu) + Docker Desktop (intégration WSL activée). Le dépôt est cloné dans le système de fichiers Linux (`~/…`), pas dans `/mnt/c`.

### 8.3 Qualité des données

La liste numérotée (T1 à T17) est dans `P1_phase0_cadrage.md` §3.

| Test | Périmètre |
|---|---|
| Tests dbt génériques : `unique`, `not_null`, `relationships`, `accepted_values` (types, canaux) ; test générique `canal_autorise` | MVP |
| Montants **entiers** (XOF, `BIGINT`) et ≥ 0 ; dates cohérentes (remboursement ≥ décaissement) | MVP |
| `montant_paye = part_capital + part_interets + penalites` | MVP |
| Débit = crédit **par `id_ecriture`** ; un seul des deux montants > 0 par ligne ; débit = crédit sur la balance, par agence × mois | MVP |
| Tout compte d'écriture existe dans le plan ; `int_evenements_rejetes` vide ; complétude événements = pièces + rejets | MVP |
| Balance : clôture m = ouverture m+1 ; clôture de décembre = Σ `fct_ecritures` | MVP |
| Rapprochements gestion ↔ comptabilité (dépôts, crédits) à chaque fin de mois, grille complète, écart = 0 | MVP |
| Bilan : actif = passif + résultat à chaque fin de mois ; aucun solde inversé sans `rubrique_solde_inverse` | MVP |
| Caisse ≥ 0 par agence et par jour ; **banque ≥ 0 par jour, au niveau de l'IMF** (D19) | MVP |
| KPI : payé imputé ≤ dû échu ; encours PAR 30 ≤ encours | MVP |
| **TEG actuariel (frais de dossier inclus) ≤ 24 % pour chaque crédit** (D20, pytest du générateur) | MVP |
| Exemples chiffrés calculés à la main, en tests unitaires dbt (`P1_cas_chiffres_tests.md`, test à deux agences, cas FIFO du taux de remboursement) ; attendus jamais modifiés pour faire passer un test ; arrêté fixé par `overrides: vars: date_arrete: "2025-12-31"` (J18) | MVP |
| Silver et gold = vérité du générateur (pytest, hors DAG, dans `make check`) : lignes silver, PAR 30, encours, soldes, résultat | MVP |
| Chaque défaut du `catalogue_anomalies` attrapé par au moins un test, selon son `traitement_attendu` (défauts datés au plus tard à l'arrêté) ; aucun faux positif | MVP |
| **Tests à l'arrêté (phase 7)** : `gold_aucune_date_apres_arrete` (hors `dim_date` et `fct_echeances.date_prevue`) ; `bronze_ingere_jusqu_a_l_arrete` (**bloquant** : pas de gold « au 15/03 » sur un bronze au 10/03) ; 12 tests ramenés à l'arrêté, aucun test désactivé ni tag `fin_exercice` (J2–J4) | MVP |
| **Contrôle de complétude** (bloquant) : fichiers du manifeste / landing, rejeux idempotents pris en compte (J12) | MVP (phase 7) |
| **Contrôle de volume corrigé de la tendance** (avertissement) : jour ordinaire = moyenne des 4 mêmes jours de semaine (fins de mois exclues) × facteur de tendance ; dernier jour ouvré = fin de mois précédente × tendance sur 28 jours ordinaires ; plage [50 % ; 200 %] ; pas de contrôle sans 4 semaines d'historique ni fin de mois précédente (J12) | MVP (phase 7) |
| Table `audit.audit_runs`, visible dans le dashboard | MVP (phases 7–8) |
| Code d'orchestration testé par pytest sans Airflow ; chargement du DAG (DagBag) testé dans le conteneur (J14) | MVP (phase 7) |
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
| **2 – Données** | Générateur Python (toutes les sources de 6.1, approvisionnements de caisse compris ; paramètres : 12 mois, ~2 000 clients, ~3 000 crédits, exercice) + défauts injectés + `catalogue_anomalies` + tests pytest (invariants, TEG, reproductibilité). Détail : `P1_phase2_cadrage.md` | ✅ **Terminée** le 21/11/2026 (corrigée en phase 3 : I10, I11, I14 ; en phase 4 : S16 ; en phase 7 : `date_ligne`) |
| **3 – Ingestion** | Chargement en bronze, incrémental et idempotent. Détail : `P1_phase3_cadrage.md` | ✅ **Terminée** le 21/11/2026 : relance sans doublon, bronze = manifeste |
| **4 – Silver** | Modèles dbt de nettoyage, mouvements induits + tests. Détail : `P1_phase4_cadrage.md` | ✅ **Terminée** le 21/11/2026 : `dbt build` vert, silver = vérité ligne à ligne, écartées = catalogue |
| **5 – Gold** | Dimensions, faits, écritures comptables (seeds de mapping). Détail : `P1_phase5_cadrage.md` | ✅ **Terminée** le 21/11/2026 : 84 572 pièces équilibrées, 0 rejet, PAR 30 = vérité |
| **6 – Marts** | Balances mensuelles, compte de résultat, bilan simplifié, KPI, rapprochements. Détail : `P1_phase6_cadrage.md` | ✅ **Terminée** le 22/11/2026 : bilan équilibré chaque mois, rapprochements à 0, résultat et PAR 30 = vérité, cas chiffrés verts. |
| **7 – Orchestration** | DAG Airflow quotidien, retries, contrôles bloquants (y compris modèles sautés par dbt après un test en échec), `audit_runs`, gold « à date ». Détail : `P1_phase7_cadrage.md` | ✅ **Terminée** le 22/11/2026 : backfill de l'exercice 2025 = **365 runs en SUCCES, chaque étape à la tentative 1** (2 555 lignes d'audit), 3 h 27 ; gold au 31/12 identique à la référence (MD5, 19 tables) ; gold au 15/03 identique sur bronze partiel et complet ; 3 pannes démontrées (fichier tronqué, seed cassé, PostgreSQL arrêté) |
| **8 – Restitution** | Dashboard Power BI (pilotage portefeuille + états financiers + qualité / fraîcheur depuis `audit.audit_runs`, mention « données arrêtées au ») | Dashboard soigné, captures |
| **9 – Industrialisation et cloud** | CI GitHub Actions, README complet, schéma d'architecture, docs dbt ; **cible dbt BigQuery + zone brute Cloud Storage** (section 8.4) | Repo présentable à un recruteur ; `dbt build` vert sur PostgreSQL **et** sur BigQuery |
| **Bonus** | Provisions, SCD 2 sur `dim_client`, write-audit-publish, Cosmos, Terraform, Power BI sur BigQuery | — |

> **Publication au fil de l'eau** : le dépôt est public dès la phase 1 et le README suit l'avancement. Un recruteur doit voir un projet vivant. Pas de rafales de commits ni de push forcé.

**Reste ouvert après la phase 7** (petit correctif, sans bloquer la phase 8) :
- contrôle de volume trop sensible les **dimanches à petit effectif** (198 % le 16/02 : 16 opérations pour une référence de 8) ; option : pas de contrôle si la référence est < 20 ;

## 10. Structure du repo

Structure cible. **Chaque dossier est créé à la phase qui l'utilise** (indiquée en commentaire) : pas de dossiers vides ni de fichiers factices dans le dépôt.

```
imf-data-pipeline/
├── README.md
├── LICENSE                    # MIT (phase 1)
├── .gitignore                 # .env, data/, .venv/, dbt/target/, dbt/logs/… (phase 1)
├── .gitattributes             # fins de ligne LF, indispensable sous Windows/WSL2 (phase 1)
├── .env.example               # noms des variables, sans valeur secrète (phase 1) ; variables Airflow (phase 7)
├── .python-version            # 3.12 (phase 1)
├── pyproject.toml             # dépendances (uv) + config ruff, mypy, pytest (phase 1)
├── uv.lock                    # versionné (phase 1)
├── Makefile                   # up, down, psql, lint, test… (phase 1) ; generate (phase 2) ;
│                              # ingest, ingest-range, ingest-all, reset-bronze (phase 3) ;
│                              # check = lint + types + dbt build + tests (phase 4) ;
│                              # airflow-up, airflow-down, airflow-logs, airflow-reprendre, test-airflow,
│                              # empreinte-gold, compare-empreintes (phase 7) ; rebuild-bq (phase 9)
├── docker-compose.yml         # PostgreSQL (phase 1) ; Airflow, profil `airflow` (phase 7)
├── docker/
│   └── postgres/init/         # création de imf_ops, imf_dwh et des schémas (phase 1 ; audit en phase 7)
├── tests/                     # tests d'intégration : socle, bout en bout, vérité silver et gold (phases 1–6)
├── data/                      # gitignoré : CSV générés, catalogue des anomalies, manifeste, _verite/ (phase 2) ;
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
├── orchestration/             # phase 7 (J19) : logique des tâches, sans import Airflow, testée par le pytest du projet
│   ├── __init__.py            # contrat des codes de sortie
│   ├── __main__.py            # CLI : python -m orchestration … (codes de sortie 0 / 3 / autre, résumé JSON)
│   ├── commandes.py           # verifier, attendre, ingerer, completude, volume, dbt
│   ├── resultats.py           # règles d'évaluation (fonctions pures) : run_results, volume, complétude
│   ├── audit.py               # lignes de audit.audit_runs (mise en attente si la base est injoignable)
│   ├── empreinte.py           # empreinte MD5 du gold (make empreinte-gold, compare-empreintes)
│   ├── sql/audit.sql          # DDL du schéma audit et de audit.audit_runs
│   └── tests/
├── dbt/
│   ├── dbt_project.yml        # phase 4 ; variable date_arrete (phase 7)
│   ├── profiles.yml           # cibles dev (phase 4) et bq (phase 9), uniquement via env_var()
│   ├── packages.yml           # dbt_utils (phase 4)
│   ├── macros/                # generate_schema_name, vers_bigint, vers_date (phase 4) ; date_arrete (phase 7) ;
│   │                          # différences PostgreSQL / BigQuery (phase 9)
│   ├── models/
│   │   ├── bronze/            # sources.yml (phase 4) ; source audit.audit_runs (phase 7)
│   │   ├── silver/            # phase 4
│   │   │   ├── staging/       # stg_* (vues) (S3)
│   │   │   └── intermediate/  # int_mouvements_compte (phase 4) ; int_evenements_comptables, int_evenements_rejetes (phase 5)
│   │   └── gold/              # phases 5–6
│   │       ├── dims/
│   │       ├── facts/
│   │       └── marts/         # balance, compte de résultat, bilan, rapprochements, KPI (phase 6)
│   ├── seeds/                 # 5 seeds (v0.5 depuis la phase 6) :
│   │                          # plan_comptes.csv, mapping_comptable.csv,
│   │                          # mapping_canal_tresorerie.csv, journaux.csv,
│   │                          # canaux_autorises.csv
│   └── tests/                 # tests singuliers et génériques (phases 4–7)
├── airflow/                   # phase 7, image Docker séparée (J7)
│   ├── Dockerfile             # environnement Airflow + venv du projet (/opt/pipeline-venv)
│   ├── dags/                  # imf_quotidien.py : DAG mince, @task qui appellent python -m orchestration
│   │                          # (pas de plugins/ : le code d'orchestration n'est pas un plugin Airflow, J19)
│   ├── reprendre.py           # reprise d'un jour en échec (make airflow-reprendre)
│   └── tests/                 # DagBag et reprise, lancés dans le conteneur (make test-airflow)
├── .github/workflows/ci.yml   # phase 9
├── infra/terraform/           # bonus
├── dashboard/                 # .pbix + captures (phase 8)
└── docs/
    ├── cadrage/               # versions publiques des cadrages, PRD, cas chiffrés (phases 6–7)
    └── img/                   # architecture, choix techniques (phase 9)
```

> Le détail exact de `orchestration/` et `airflow/` (noms de fichiers, emplacement des tests DagBag) est celui du dépôt au commit `0df7529`.

## 11. Critères de réussite

- [x] Le pipeline complet se lance avec Docker et s'exécute automatiquement via Airflow — phase 7.
- [x] Une relance ne crée ni doublon ni incohérence (idempotence) — phase 3 ; rejeux idempotents vérifiés par le contrôle de complétude — phase 7.
- [ ] Tous les tests dbt et pytest passent en CI. *(verts en local : 391 tests dbt dont 10 unitaires, 203 pytest ; CI en phase 9)*
- [x] Les défauts injectés sont détectés par les tests — phase 4.
- [x] La balance est équilibrée (débit = crédit) et aucun événement n'est rejeté — phases 5–6.
- [x] Les rapprochements gestion ↔ comptabilité sont à zéro — phase 6.
- [x] Les KPI et états financiers sont vérifiés à la main sur un échantillon — phase 6.
- [ ] Le pipeline produit **la même balance, au franc près**, sur PostgreSQL et sur BigQuery.
- [ ] Le README permet à un inconnu de comprendre et relancer le projet.

## 12. Limites (à afficher dans le README)

- Données **100 % fictives** ; IMF supposée en **première année d'activité**.
- **Aucun crédit en janvier** : l'IMF démarre le 01/01 sans clients, et un crédit exige un compte ouvert depuis 30 jours.
- PAR 30 au 31/12 **calibré autour de 5 %** dans la simulation (4,9992 % obtenu) ; le pipeline le recalcule, il ne le mesure pas sur une activité réelle.
- Plan de comptes **simplifié** à codes internes ; **ce n'est pas le RCSFD officiel**. Les numéros RCSFD sont à confirmer par un comptable d'IMF.
- Correspondances avec le SYSCOHADA général **indicatives**, certaines **approximatives** : le SYSCOHADA général n'a pas de comptes propres à l'activité de crédit et de dépôt.
- Intérêts reconnus **à l'encaissement**, alors que le RCSFD repose sur une comptabilité d'engagement.
- **Pas de provisions** sur créances en souffrance : le bilan surévalue l'encours si le PAR 30 est non nul.
- Épargne **non rémunérée** ; frais de dossier constatés en une fois.
- Comptes de liaison (mobile money, agents) **non compensés** ; pas d'écriture de clôture.
- **Pas de comptes de tiers par agent** : les liaisons sont classées sur leur solde au niveau de l'IMF (écart chiffré dans le README) ; pas de bilan par agence (la banque par agence n'a pas de sens, G6).
- **Pas de charges à payer** : les commissions mobile money de décembre, facturées en janvier suivant, sont hors exercice.
- Remboursements partiels : imputation pénalités → intérêts → capital, échéance par échéance (243 soldes d'échéance sans intérêts).
- Pas de refinancement : le capital d'ouverture couvre seul le besoin de financement, d'où un capital élevé.
- Approvisionnements de caisse en **une seule pièce** (journal VIR), sans compte de virements internes ; pas de versement des excédents de caisse vers la banque ; banque contrôlée ≥ 0 au niveau de l'IMF, pas par agence ; caisse contrôlée en fin de journée.
- TEG calculé sur l'échéancier théorique (frais de dossier inclus, pénalités exclues) ; taux d'usure de 24 % appliqué comme plafond unique.
- Jours d'ouverture du lundi au samedi, sans jours fériés.
- La base opérationnelle simulée ne conserve que l'**état au 31/12** : le statut des crédits n'y est pas historisé. **Neutralisé dans le gold** depuis la phase 7 : `dim_credit.statut_a_l_arrete` est recalculé depuis le silver ; `statut_au_31_12` reste descriptif (sans cela, 57 crédits au 15/03 et 75 au 31/03 seraient vus SOLDE alors qu'ils étaient EN_COURS).
- **Mois en cours = situation intermédiaire** : un run quotidien tombe en milieu de mois ; les marts mensuels portent `date_situation = least(fin de mois, date_arrete)`.
- Runs `imf_ops` **cumulatifs** (filigrane) : rejouer un jour passé ne recharge rien ; pour tout rejouer, `make reset-bronze`.
- Si un test dbt échoue, le run Airflow échoue (sans retry) et le jour suivant est bloqué (`depends_on_past`), mais les modèles déjà construits restent en base et les modèles sautés gardent leur **ancienne version** : pas de write-audit-publish (bonus). Le dashboard affiche la date d'arrêté du dernier run réussi.
- Contrôle de volume : détecte une **rupture brutale** (jour divisé par 3 → 34 %), **pas une dérive lente** ; sensible aux jours à petit effectif (dimanches).
- Orchestration **locale** (Airflow dans Docker, LocalExecutor) ; seuls l'entrepôt (BigQuery, bac à sable) et la zone brute (Cloud Storage) sont dans le cloud.
- Pipeline **batch** uniquement.
- Bac à sable BigQuery : données supprimées au bout de 60 jours, recréées par `make rebuild-bq`.
