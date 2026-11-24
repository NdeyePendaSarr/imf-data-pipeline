# P1 – Phase 9 : industrialisation et cloud — cadrage (v0.14, 24/11/2026) – PHASE TERMINÉE

> Version publique. Complète le PRD (§8.4, §9) ; les écarts au PRD sont reportés en **v1.8**.
> Critère de fin (PRD §9) : CI verte, `dbt build` vert sur PostgreSQL **et** sur BigQuery, README
> complet, schéma d'architecture, docs dbt.

## 1. Décisions

| # | Décision | Pourquoi | Statut |
|---|---|---|---|
| L1 | **Zone brute sans Google Cloud Storage.** Le bronze est chargé depuis PostgreSQL dans un dataset BigQuery `bronze` par des *load jobs* (pas de DML, compatible avec le bac à sable). `ingestion/upload_gcs.py` abandonné | Pas de compte de facturation possible, donc pas de Cloud Storage ; l'essai gratuit ferme au bout de 90 jours (même motif que l'écart de Snowflake). Écart au PRD §8.4, documenté dans le README | ✅ |
| L2 | Source du chargement = **tables bronze PostgreSQL** (+ `audit.audit_runs` dans un dataset `audit`) exportées en Parquet, schéma BigQuery explicite tiré d'**une seule** table de correspondance des types (`CORRESPONDANCE`, type inconnu = échec), `WRITE_TRUNCATE`, contrôle lignes BigQuery = PostgreSQL | Même entrée pour les deux cibles dbt : seul le moteur change | ✅ |
| L3 | Comparaison PostgreSQL ↔ BigQuery sur les chiffres de contrôle, pas sur le MD5 ; silver (lignes, sommes) et gold. **Versionnée** : `scripts/comparer_moteurs.py`, `make compare-moteurs`, tests pytest ; tableau dans `$GITHUB_STEP_SUMMARY` en CI | Une preuve rejouable vaut plus qu'un tableau dans un compte rendu | ✅ 71 mesures, 0 écart (local et CI) |
| L4 | BigQuery **jamais à chaque push** : job CI manuel (`workflow_dispatch`) ; identifiants par défaut (ADC) en local, Workload Identity Federation en CI, aucune clé JSON. Garde-fou `maximum_bytes_billed` 1 Go. Quota de stockage : raisonnement au pire cas | Pire cas (limite de 10 Gio, stockage supprimé jamais rendu) : entrepôt ≈ 119 Mio logiques → ≈ 85 reconstructions, ≈ 14 ans à une reconstruction par expiration de 60 jours | ✅ |
| L5 | Tous les datasets en **`EU`**, lue depuis `BQ_LOCATION` ; `BQ_PROJECT` jamais dans le dépôt | BigQuery ne joint pas des datasets de régions différentes ; région non modifiable après création | ✅ |
| L6 | Ordre de portage : SQL standard commun > macros dbt > **8 macros `adapter.dispatch` maison**, `default__` qui échoue ; **7 tests singuliers à valeurs littérales**, alignés sur PostgreSQL | Moins de code maison ; rien de copié dans les modèles ; cas limites prouvés | ✅ |
| L7 | Contrats sur les deux moteurs ; types génériques ; Jinja seulement pour les `column_types` des seeds ; macros pour `date_maj` et taux | Moins de bruit ; contre-essai en échec sur les deux moteurs | ✅ |
| L8 (K11) | Pas de contrôle de volume si la référence est < 20 | Ratios proches de 200 % sans anomalie réelle ; troncature détectée par la complétude | ✅ |
| L9 | CI PostgreSQL : un job, `pytest` après `dbt build`, cibles make (`--env-file` seulement si `.env` existe), mot de passe jetable commenté, tests Airflow exclus | Reconstruction complète, déterministe | ✅ |
| L10 | Commits espacés : lot A `aee9820`, lot B `af40f42`, correctif L15 `b705301`, lot C (documentation) | Un échec, son diagnostic et sa correction visibles dans l'historique ; pas de rafale | ✅ |
| L11 | Groupe uv `bq`, groupes par défaut ; image Airflow `--no-default-groups --group dbt` | L'orchestrateur n'a que ses dépendances | ✅ |
| L12 | Taux : `numeric(6,4)` sur PostgreSQL, `NUMERIC` sur BigQuery | BigQuery refuse les types paramétrés dans `CAST` | ✅ |
| L13 | `post-hook: analyze {{ this }}` sur seeds et tables, PostgreSQL seulement ; preuve dans le conteneur Airflow ; pas de run du DAG | `fct_ecritures` > 9 min sans statistiques, 2,3 s avec ; l'audit (3 201 lignes) reste figé | ✅ |
| L14 | Job BigQuery validé après push sur `main` (condition de la fédération d'identité : ce dépôt, `refs/heads/main`) ; documentation avec le lien du run réel | Ne pas affaiblir la condition | ✅ |
| L15 | **La CI ne recharge pas l'audit** : option explicite `SANS_AUDIT=1` / `--sans-audit`, utilisée seulement dans `bigquery.yml` ; sans l'option, table absente = erreur | Explicite plutôt qu'implicite ; une table vide en CI viderait l'audit BigQuery. Conséquence : le bronze BigQuery reflète le dernier chargement (poste ou CI, mêmes données métier, colonnes techniques différentes), l'audit reste la copie du poste (3 201 lignes) | ✅ |
| L16 | Schéma d'architecture en **Mermaid** dans le README (rendu par GitHub, versionné comme du code) ; **docs dbt publiées sur GitHub Pages** depuis la CI PostgreSQL, sur `main` seulement (job de déploiement séparé, seul à avoir `pages: write` et `id-token: write`) | Un schéma texte se relit et se corrige comme le code ; le graphe de lignage dbt consultable sans rien installer | ✅ |

Contraintes du bac à sable : pas de DML ni de streaming ; tables, vues et partitions expirent au bout de 60 jours (`make rebuild-bq`).

Hors périmètre : Airflow sur BigQuery ; DagBag dans la CI ; run du DAG en phase 9 (L13) ; K12 ; Terraform et Power BI sur BigQuery (bonus).

## 2. Étapes

| Étape | Contenu | Critère de fin | État |
|---|---|---|---|
| 0. Inventaire | Matérialisations, SQL propre à PostgreSQL, taille, types | Tableau des écarts | ✅ `docs/phase9/inventaire_bq.md` (`aee9820`, complété dans `af40f42`) |
| 1. K11 | Seuil de référence 20 | `make check` vert ; gold inchangé | ✅ (`aee9820`) : 323 jours contrôlés, 0 avertissement, ratios 71 % à 148 % |
| 2. CI PostgreSQL | GitHub Actions | Badge vert sur `main` | ✅ (`aee9820`) ; dernier run sur `main` : 45395881197, 75 s |
| 3a–3d. Portage BigQuery | Chargeur, profil, silver, gold | Build bq complet vert ; L3 sans écart au 31/12 et au 15/03 | ✅ (`af40f42`) : 457 PASS sur bq et dev |
| 4a. Rebuild et preuve versionnée | `make rebuild-bq`, `make compare-moteurs` | Entrepôt recréé en une commande, 0 écart | ✅ (`af40f42`) : 4 min 28 s à 5 min 07 s en local |
| 4b. Job CI BigQuery | `bigquery.yml`, fédération d'identité | Run manuel vert sur `main` sans clé JSON, 0 écart | ✅ : premier run 45393283643 en échec (audit absent de la CI) → correctif L15 `b705301` → **run 45396166776 vert, 351 s** (authentification 0 s ; generate 5 s ; ingest 6 s ; dbt dev 19 s ; `rebuild-bq SANS_AUDIT=1` 290 s : 14 tables en 64,5 s, 457 PASS, **71 mesures, 0 écart**) ; audit BigQuery toujours à 3 201 lignes ; `make check` 457 PASS, **227 pytest** |
| 5. Livraison (lot C) | README, Mermaid, docs dbt (Pages), PRD v1.8 et cadrage public | CI verte, docs en ligne, badges verts | ✅ |
