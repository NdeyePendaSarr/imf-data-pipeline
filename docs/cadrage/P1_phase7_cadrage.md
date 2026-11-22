# P1 – Phase 7 : cadrage orchestration (v1.0, 22/11/2026) – PHASE TERMINÉE

> Version publique. Complète la PRD v1.6 et les cadrages des phases 0 à 6 ; les écarts sont reportés dans la **PRD v1.7**.
> Critère de fin (PRD §9) : exécution automatique sans intervention.
> Contraintes de départ : backfill de 3–4 h accepté ; poste de développement à 7,6 Go de RAM sous WSL2 (≈ 6,1 Go disponibles).

## 1. Décisions

| # | Décision | Justification |
|---|---|---|
| J1 | Le DAG orchestre le pipeline, pas la simulation (`make generate` hors DAG) | Le générateur joue le monde extérieur |
| J2 | Variable dbt `date_arrete` (défaut = fin d'exercice), macro `date_arrete()` ; Airflow passe `{{ ds }}` ; test `gold_aucune_date_apres_arrete` (hors `dim_date`, `fct_echeances.date_prevue`) | Le gold ne montre que ce qui est connu à J |
| J3 | Test bloquant `bronze_ingere_jusqu_a_l_arrete` | Pas de gold « au 15/03 » sur un bronze au 10/03 |
| J4 | 12 tests ramenés à l'arrêté ; aucun tag `fin_exercice` | Pas de test désactivé |
| J5 | Vérité (pytest) hors DAG, dans `make check` | Pas d'oracle en production |
| J6 | Airflow **3.3.2** épinglé (3.4.0 sortie le 06/11/2026, écartée : version .0 récente), LocalExecutor, parallelism 2, airflow-db séparée, sans triggerer, `mem_limit` par service, profil compose `airflow`, auth FAB | RAM 7,6 Go ; environnement de dev inchangé ; version de maintenance plutôt qu'une .0 |
| J7 | Image `airflow/Dockerfile` (4,28 Go) : env Airflow sans dbt + venv `/opt/pipeline-venv` (`uv sync --frozen`) sans Airflow ; dépôt monté **en lecture seule**, seul `data/` en écriture ; artefacts dbt dans le conteneur ; `PYTHONDONTWRITEBYTECODE=1` | Conflit de dépendances ; le conteneur ne peut pas modifier le code ni `.env` |
| J8 | `@daily`, exercice, `max_active_runs=1`, `depends_on_past=True`, backfill Airflow 3 ; run sans logical_date refusé | Filigrane cumulatif ; pas de J+1 sur un J en échec |
| J9 | `verifier_environnement` → `attendre_fichiers` (reschedule) → `ingerer` → `controler_completude` (bloquant) → `controler_volume` (avertissement) → `dbt_build` → `ecrire_audit` (teardown) | Le teardown ne rend pas le run vert |
| J10 | dbt : lecture de `run_results.json` ; error/fail/skipped → échec sans retry ; erreur technique → retry | Un test de données ne se relance pas |
| J11 | Retries 2, 2 min, backoff exponentiel | Pour l'infrastructure seulement |
| J12 | Complétude = manifeste / landing, rejeux idempotents (IGNORE) pris en compte (bloquant). Volume **corrigé de la tendance** (avertissement) : jour ordinaire = moyenne des 4 mêmes jours de semaine (fins de mois exclues) × facteur de tendance (moyenne par jour ordinaire des 7 derniers jours / mêmes fenêtres décalées de 1 à 4 semaines) ; dernier jour ouvré = fin de mois précédente × tendance sur 28 jours ordinaires ; plage [50 % ; 200 %] ; pas de contrôle sans 4 semaines d'historique ni fin de mois précédente | Une règle « vs veille » levait 10 fausses alertes au T1 (croissance ≈ 190 comptes/mois, fins de mois ×10). Détection prouvée : jour ÷3 → 34 %. Limite : rupture brutale seulement, pas de dérive lente |
| J13 | `audit.audit_runs`, en ajout seul : une ligne par **étape × tentative**, écrite par l'étape elle-même à la fin de chaque tentative, + une ligne `RUN` écrite par le teardown (étape sans ligne = NON_EXECUTE) ; source dbt pour la phase 8 | Toutes les tentatives tracées ; en Airflow 3 une tâche n'accède pas à la base de métadonnées : le teardown lit les XCom, pas l'état des tâches |
| J14 | Logique pure sans import Airflow, testée par pytest du projet ; DagBag testé dans le conteneur | DAG mince |
| J15 | Mois en cours = situation intermédiaire ; `date_situation = least(fin de mois, date_arrete)` | Un DAG quotidien tombe en milieu de mois |
| J16 | `catalogue_anomalies.date_ligne` ; filtre catalogue sur `date_ligne ≤ date_arrete` | Filtre porté par la source |
| J17 | `dim_credit.statut_a_l_arrete` (depuis silver) ; `statut_au_31_12` descriptif | La base opérationnelle ne garde que l'état au 31/12 (limite I10) : neutralisée dans le gold |
| J18 | Tests unitaires du gold : `overrides: vars: date_arrete: "2025-12-31"` | Logique indépendante de l'arrêté |
| J19 | Code d'orchestration dans un paquet **`orchestration/`** à la racine (comme `generator/`, `ingestion/`), exécuté dans le venv du projet (`python -m orchestration …`). Les tâches du DAG sont des `@task` Python qui lancent ce CLI par subprocess, avec un **contrat de codes de sortie** : 0 = succès, 3 = échec de contrôle (AirflowFailException, sans retry), autre = erreur technique (retry). Dernière ligne de sortie = résumé JSON (XCom) | Un BashOperator ne sait pas distinguer « ne pas relancer » ; tout accès à la base reste dans le venv du projet. Écart à la structure de la PRD v1.6 (`airflow/plugins/`) : ce n'est pas un plugin Airflow |
| J20 | Connexion à PostgreSQL par les variables `POSTGRES_*` (comme dbt et l'ingestion), pas de connexion Airflow `AIRFLOW_CONN_*` | Le code qui accède aux bases tourne hors Airflow |

BONUS : write-audit-publish ; Cosmos.

## 2. Lots

| Lot | Contenu | Critère | Statut |
|---|---|---|---|
| 0 | PRD v1.6 allégée dans `docs/cadrage/` | — | ✅ f7a4241 |
| A | J2–J4, J15–J18 | Défaut = phase 6 (PASS 442, pytest 153, MD5) ; arrêtés 15/01, 15/03, 31/03 verts ; **gold au 15/03 identique sur bronze partiel et complet (MD5, 19 tables, toutes colonnes)** | ✅ 3bbe4ba ; docs phase 6 publiques 8bac2b1 |
| B | Image, compose, `.env.example`, Makefile, DAG `verifier_environnement`, DagBag | Services healthy en 62 s, UI 200, DAG sans erreur, dbt build dans le conteneur PASS 442 (21,5 s), test-airflow 2 verts, check inchangé | ✅ 7b962fb |
| C | DAG complet, contrôles, audit (J8–J14, J19) | 90 runs verts ; gold au 31/03 = dbt build arrêté 31/03 (MD5) ; pannes a (fichier tronqué : complétude rouge, sans retry, J+1 bloqué, rechargement par SHA-256), b (seed : 346 PASS / 1 ERROR / 95 sautés, sans retry), c (PostgreSQL arrêté : ECHEC_TECHNIQUE puis SUCCES, audit mis en attente puis versé) | ✅ 5010424 |
| C' | Corrections : scheduler 1536m, volume corrigé de la tendance, vérification après clear, `make empreinte-gold` / `compare-empreintes` versionnés | make check 442 PASS, 197 pytest ; test-airflow 14 | ✅ 21a625c |
| D | Backfill complet + README | **365 RUN en SUCCES, chaque étape à la tentative 1 (2 555 lignes d'audit)** ; gold au 31/12 = référence (MD5, 19 tables) ; bilan 2 119 584 054, résultat −333 130 376, PAR 30 4,9992 %, 120 rapprochements à 0 ; volume : 331 jours contrôlés, 0 avertissement ; **3 h 27** ; run moyen 32 s ; pic scheduler 716 Mio (47 % de 1,5 Gio) | ✅ c0f220f ; clôture 0df7529 |

### Problèmes corrigés en route (lots C et C')

- `find_spec("airflow")` trouvait le dossier `airflow/` du dépôt ;
- `make generate` supprimait `data/` (montage Docker détaché) ;
- `airflow tasks clear -t '^…$'` ne sélectionnait rien, en silence → vérification après clear ;
- interblocage `depends_on_past` + 1 run actif → `make airflow-reprendre`.

## 3. Mesures

Mémoire (lot B) : 778 Mio au repos (4 services Airflow), 1 066 Mio avec le PostgreSQL du projet ; scheduler 545 Mio au pic d'un dbt build (memory.peak, 53 % de 1 Gio) ; api-server 292, dag-processor 308 / 768, airflow-db 101 / 256.

Arrêtés intermédiaires (seed 42) :

| Arrêté | Bilan | Rapprochements | Résultat cumulé | Encours |
|---|---|---|---|---|
| 15/01 | 1 846 911 500 | 10 lignes, 0 | −5 772 500 | aucun crédit |
| 15/03 | 1 876 010 446 | 30 lignes, 0 | −82 888 129 | 163 386 715 (PAR 30 = 0) |
| 31/03 | 1 866 378 469 | 30 lignes, 0 | −114 897 159 | 223 092 568 (PAR 30 = 0) |

Statut connu trop tôt (sans J17) : 57 crédits au 15/03, 75 au 31/03 EN_COURS à l'arrêté mais SOLDE au 31/12.

Backfill de l'année (lot D) : run moyen par mois 51,5 / 49,5 s puis 26,8 → 32,8 s (dbt 17,8 → 23,8 s, ≈ +0,6 s/mois). Janvier-février plus lents : coïncide avec la première heure du backfill, pendant laquelle l'économiseur d'énergie Windows était encore actif — explication probable, non prouvée par l'audit.

## 4. Reste à faire

- Volume : dimanches à petit effectif (198 % le 16/02, 16 opérations pour une référence de 8) ; option : pas de contrôle si la référence est < 20.
