# P1 – Phase 4 : silver dbt (cadrage v0.2 et bilan, 21/11/2026)

> Complète le PRD v1.5 et `docs/cadrage/P1_phase3_cadrage.md`. Critère de fin : `dbt build` vert sur silver **et** silver nettoyé = `data/_verite/` (pytest), `make check` vert. Partie Claude Code atteinte le 21/11/2026 ; reste : les deux tests relus par Ndeye Penda (§3), puis push.

## 1. Décisions

| # | Décision | Pourquoi (pour l'entretien) |
|---|---|---|
| S1 | dbt Core + dbt-postgres dans un groupe uv `dbt` de l'environnement principal ; version ≥ 1.8 (tests unitaires dbt), fixée par `uv.lock` | Airflow aura son image (phase 7) ; dbt seul ne crée pas de conflit |
| S2 | `dbt/profiles.yml` versionné, uniquement `env_var()` ; macro `generate_schema_name` → schémas exacts `silver` / `gold` ; seeds dans `silver` | Pas de `dev_silver` ; on garde les 3 schémas du PRD |
| S3 | Deux niveaux : `stg_<table>` (vues : typage sûr, standardisation, dernière version, `motif_ecart`) → `slv_<table>` (tables : lignes valides, contrat dbt imposé) ; `slv_lignes_ecartees` = toutes les lignes écartées, avec leur traçabilité bronze | La règle d'écart est écrite une fois ; rien n'est filtré en silence. **Écart au PRD §10** : sous-dossier `models/silver/staging/` |
| S4 | Typage sûr des colonnes `TEXT` (macros `vers_bigint`, `vers_date` : regex, sinon NULL) ; non convertible → motif `TYPE_INVALIDE` | Suite logique de I2 : une ligne mal formée ne fait pas échouer tout le build, elle est écartée et visible |
| S5 | Standardisation `upper(trim())` des codes (canal, type, catégorie), puis `accepted_values` | Corrige `FORMAT_CANAL` à l'identique (D21) |
| S6 | `motif_ecart` = nature du catalogue (même vocabulaire), un seul motif par ligne, priorité : TYPE_INVALIDE > ORPHELIN_COMPTE > MONTANT_NEGATIF > CANAL_NON_AUTORISE > DATE_INCOHERENTE > MONTANT_PAYE_INCOHERENT | La comparaison au catalogue devient une simple jointure |
| S7 | Dédoublonnage CSV : par id, on garde la 1re occurrence (`_source`, `_num_ligne`) ; les autres → `DOUBLON_EXACT` / DEDOUBLONNER. Test : même id avec un contenu différent = 0 ligne | Un « doublon » au contenu différent n'est pas un doublon : on veut une erreur, pas un choix arbitraire |
| S8 | `ops_*` : dernière version par clé (`date_maj` desc, `_charge_le` desc) | Bronze garde l'historique (I5) |
| S9 | `credits.statut` renommé `statut_au_31_12` (description explicite) | Conséquence de I10 : rend l'usage à date visiblement faux |
| S10 | `int_mouvements_compte` : un mouvement sur un compte client, `montant_signe` (+ augmente le solde). DEPOT +, RETRAIT −, FRAIS_TENUE −, DECAISSEMENT +, FRAIS_DOSSIER −, PRELEVEMENT − ; `id_mouvement` = `TYPE:source_id`, `source_table`, `source_id` | Une seule source par mouvement (PRD §6.1) ; base des soldes et du rapprochement D9 |
| S11 | `int_evenements_rejetes` reporté en phase 5 | Il dépend du mapping comptable (gold). **Écart au PRD §10** (rangé en silver/intermediate) |
| S12 | Vérité testée par pytest (`tests/test_silver_verite.py`, marqueur integration) : compare l'ensemble des lignes de chaque `slv_*` (colonnes métier, hors `_*`) à `data/_verite/` et aux comptes du manifeste. Vérité jamais chargée dans l'entrepôt. Prérequis : bronze complet au 31/12 | La vérité est un oracle de test, pas une donnée : Power BI ne doit jamais pouvoir la lire |
| S13 | Silver = noms de colonnes de la source (sauf S9) + `_id_run`, `_source` conservés | Comparaison directe à la vérité ; lignage jusqu'au fichier bronze |
| S14 | Matérialisation en tables reconstruites, pas d'incrémental | ~100 k lignes, quelques secondes ; l'incrémental ajoute du risque sans gain. À réévaluer pour `fct_portefeuille_quotidien` (phase 5) |
| S15 | `FRAIS_TENUE` reste dans `slv_operations` | Vrai mouvement et vraie écriture ; exclu des KPI d'activité en gold |
| S16 | **Correction du générateur** : une anomalie MONTANT_PAYE_INCOHERENT ne doit jamais produire un `montant_paye` négatif (RMB48979413 : −1 109) ; écart forcé positif, mêmes tirages ; nouveau test `test_chaque_anomalie_n_enfreint_que_sa_regle` | Silver avait raison : la ligne enfreignait aussi MONTANT_NEGATIF, prioritaire. Une anomalie ne doit tester qu'une règle |
| S17 | `make check` lance `dbt-build` avant `test-all` | Le test de vérité doit lire le silver qui vient d'être construit. Conséquence : `make check` suppose un bronze complet (à prévoir pour la CI, phase 9) |

## 2. Tests (tous MVP)

- Génériques : `unique`, `not_null` (colonnes critiques seulement), `relationships`, `accepted_values`, montants ≥ 0, `unique_combination_of_columns` (agence, canal) sur `ouverture`.
- Test générique maison `canal_autorise` contre le seed (D16).
- Singuliers : `montant_paye = somme des parts` ; remboursement ≥ décaissement ; échéance ≥ décaissement ; doublons d'id non exacts = 0 ; solde de fin de journée ≥ 0 par compte.
- Catalogue : (1) écartées attendues ; (2) aucun faux positif ; (3) STANDARDISER corrigées ; (4) ACCEPTER_NULL conservées.
- Test unitaire dbt de `int_mouvements_compte` — **relu par Ndeye Penda**.

Limite à dire en entretien : le catalogue prouve les règles sur des défauts connus ; le test (2) est le garde-fou contre les faux positifs.

## 3. Ce que Ndeye Penda relit

1. Le test unitaire dbt de `int_mouvements_compte` (exemple §4 du cadrage phase 0 + un prélèvement + un remboursement non prélevé, qui ne doit pas apparaître).
2. Le test générique `dbt/tests/generic/canal_autorise.sql` (argument à ne pas nommer `source`, qui masquerait la fonction Jinja `source()`).

## 4. Résultats (seed 42, configuration par défaut)

- `dbt build` (dbt 1.12) : 5 seeds, 13 tables, 12 vues, 118 tests → PASS = 148, WARN = 0, ERROR = 0. `make check` : ruff, mypy (33 fichiers), dbt build, pytest 144 passed (dont 13 dans `test_silver_verite.py`). Rejeu complet `make ingest-all` : 17,6 s.
- Lignes : agences 6, ouverture 6, operations 66 514, charges 227, appro_caisse 141, produits_credit 4, clients 2 000, comptes 2 317, credits 3 000, echeancier 34 037, remboursements 11 684, lignes écartées 2 570, `int_mouvements_compte` 74 515. Silver = vérité ligne à ligne sur les 11 tables.
- Écartées = catalogue : DOUBLON_EXACT 1 004 copies (665 lignes au catalogue), ORPHELIN_COMPTE 665, MONTANT_NEGATIF 665, CANAL_NON_AUTORISE 2, DATE_INCOHERENTE 117, MONTANT_PAYE_INCOHERENT 117 ; FORMAT_CANAL 665 corrigées, NULL_NON_CRITIQUE 20 conservées. Cohérence : 66 514 + 1 004 + 665 + 665 = 68 848 opérations brutes (manifeste).
- Mutations : sans `trim`, 307 FORMAT_CANAL cassent (catalogue 3, catalogue 2, solde ≥ 0, vérité) ; sans ORPHELIN_COMPTE, 665 lignes (2 relationships, catalogue 1, solde ≥ 0, vérité).
- Commits : 500542b, 7ac203f, 1e9ad11, 82cb61d (non poussés au 21/11).

## 5. Points ouverts

- **Trou dans I12** : la correction S16 ne changeait que `imf_ops`, et l'empreinte de génération est restée identique ; l'ingestion n'aurait rien détecté (reset manuel). L'empreinte doit couvrir le contenu de `imf_ops` (hash par table) ou une version du générateur.
- Vérifier que 74 515 = 66 514 + 3 000 décaissements + 3 000 frais de dossier + nombre de remboursements PRELEVEMENT (attendu : 2 001).
- Les cadrages ne sont pas dans le dépôt (Claude Code les lit dans Downloads) ; à ranger dans `docs/` au plus tard en phase 9.
- `.env` : ajouter `POSTGRES_DB_DWH=imf_dwh`.
