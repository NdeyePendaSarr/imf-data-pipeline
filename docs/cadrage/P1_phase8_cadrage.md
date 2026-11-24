# P1 – Phase 8 : dashboard Power BI — cadrage (v0.3, 24/11/2026) – PHASE TERMINÉE

> Version publique. Complète la PRD v1.7 (§9, phase 8). Décisions K1 à K14.
> v0.2 : étape 1 terminée ; K3, K5, K2 corrigés ; K12 et K13 ajoutés.
> v0.3 : K10 tranché (.pbix) ; K14 (libellés des rubriques) ajouté ; étapes 1 bis à 5 terminées avec leurs chiffres ; nouveaux compteurs de tests.

## 1. Objectif et critère de fin (PRD §9)

Dashboard Power BI : pilotage du portefeuille, états financiers, qualité / fraîcheur depuis `audit.audit_runs`, mention « données arrêtées au ».
Critère : dashboard soigné, captures, chiffres de référence retrouvés au 31/12 et comportement « à date » démontré au 15/03.

## 2. Décisions

| # | Décision | Raison |
|---|---|---|
| K1 | **Deux dates.** *Date du gold* = `max(date_situation)` de `mart_bilan` ; *dernier run réussi* = ligne `RUN` + `SUCCES` de `audit.audit_runs`. Le bandeau « Données arrêtées au » affiche la date du gold ; **alerte** si les deux dates diffèrent ou si le dernier run est en échec | La ligne `RUN` est écrite après `dbt_build` ; un `dbt build --vars` manuel n'écrit rien dans l'audit ; un run en échec laisse des modèles à l'ancienne version (PRD §12) |
| K2 | **Mesures semi-additives** pour les stocks (encours, encours PAR 30, cumuls du taux de remboursement, crédits actifs, épargne, bilan, résultat cumulé) : évaluées au **dernier jour qui a des données** (`MAX` de la date du fait, équivalent de `LASTNONBLANK`), calculé **sans les filtres agence / produit** et plafonné à la date du gold (`KEEPFILTERS`). Pas de `LASTDATE` (`dim_date` couvre l'exercice + 2 ans). Flux (opérations, résultat de la période) en `SUM`. Densification partielle du mart : stocks **vides** (pas 0) en janvier et pour un couple agence × produit avant son premier crédit ; pas de `+ 0` | Un `SUM` de l'encours sur un mois multiplie l'encours par ~30 ; même jour de référence pour toutes les agences |
| K3 | **Rôle `powerbi_lecteur`** : `CONNECT`, `USAGE` + `SELECT` sur `gold` et `audit`, `ALTER DEFAULT PRIVILEGES` pour le rôle qui exécute dbt, `default_transaction_read_only = on` ; `dashboard/sql/role_lecture.sql`, `make powerbi-role` (mot de passe `POWERBI_PASSWORD` lu par `\getenv`). Connexion `localhost:5433` / `imf_dwh` (5432 = PostgreSQL local Windows) ; identité vérifiée par `current_database()`, adresse du réseau Docker et version (pas par `inet_server_port()`, qui renvoie le port interne 5432) ; « Chiffrer les connexions » décoché (serveur sans SSL, poste local, données fictives) | dbt reconstruit les tables : un `GRANT` sur table saute au build suivant. Jamais de connexion Power BI en superutilisateur |
| K4 | Mode **Import** | Plus gros fait `fct_portefeuille_quotidien` = 404 573 lignes (non importé : les marts suffisent) |
| K5 | Power BI lit `audit.audit_runs` **directement** (3 201 lignes : 2 555 du backfill + 646 des démonstrations de pannes), sans nouveau modèle dbt | Une table dbt serait en retard d'un run ; une vue dans `gold` tomberait sous `gold_aucune_date_apres_arrete` |
| K6 | `dim_date` marquée table de dates ; 14 relations 1:* à sens unique sur `date` / `date_situation`, `id_agence`, `code_produit`, `code_compte` ; `audit_runs` et `dim_credit` isolées ; table de mesures `_Mesures` ; colonnes numériques non additives en « Ne pas résumer » ; colonnes brutes des marts masquées | Étoile lisible, aucune somme accidentelle |
| K7 | Ratios uniquement en DAX (`DIVIDE`) | Les marts stockent numérateurs et dénominateurs (PRD §7) |
| K8 | Mois partiel : `date_situation` < fin de mois au mois en cours | Cohérent avec J15 |
| K9 | Thème `dashboard/theme_senfinance.json` (accent #0B5C8A, rouge #B42318 réservé aux alertes, vert #1B7F3B pour les contrôles à 0), fr-FR, canevas 1920 × 1080, montants en M sur les cartes et au franc dans les états | Design homogène, contrastes AA |
| K10 | Livrables : `dashboard/senfinance_dashboard.pbix`, captures PNG (`dashboard/captures/`, au 31/12 et au 15/03), `dashboard/mesures.md`, section README. **Format : `.pbix`** (l'enregistrement en projet PBIP n'est pas proposé par la version de Power BI Desktop utilisée) ; `mesures.md` rend le DAX lisible sur GitHub | Un `.pbix` est illisible dans un diff |
| K11 | Correctif du contrôle de volume du dimanche reporté en **phase 9** | Hors périmètre du dashboard |
| K12 | Ordre d'affichage : bilan trié par `ordre` ; compte de résultat trié par `rubrique` (préfixes R1…R6, vérifié jusqu'à R9) ; jamais de tri manuel dans Power BI. Si les rubriques bonus imposent la présentation bancaire (R6 après R1), ajouter une colonne `ordre` à `mart_compte_resultat` | La présentation d'un état vit avec l'état |
| K13 | `run_id` non unique d'un backfill à l'autre : *état final d'un jour* = plus grand `id_audit` pour (`date_logique`, `etape`), colonne calculée DAX `est_etat_final`. Indicateurs de runs sur les états finaux ; historique des incidents sur toutes les lignes. Statuts : `SUCCES`, `AVERTISSEMENT`, `ECHEC_CONTROLE`, `ECHEC_TECHNIQUE` | Un jour rejoué ne compte qu'une fois ; les pannes démontrées en phase 7 restent visibles |
| K14 | **Libellés des rubriques** : seed `rubriques_etats.csv` (rubrique, libelle ; 12 rubriques, dont R5 et R6 bonus), colonne `libelle_rubrique` ajoutée à `mart_bilan` et `mart_compte_resultat` (contrats, `not_null`, `relationships`) ; seed de présentation, sans incrément de `version_mapping`. Seules les empreintes de ces deux marts changent (mêmes lignes, mêmes montants) : la référence de la phase 7 reste `docs/phase7/empreinte_gold_reference_31_12.txt` (valable au commit `c0f220f`), la nouvelle est `docs/phase8/empreinte_gold_reference_31_12.txt` | Un état financier se lit en libellés, pas en codes techniques ; la preuve de la phase 7 n'est pas réécrite |

## 3. Pages

| Page | Contenu |
|---|---|
| Pilotage du portefeuille | Segments période (multisélection, sans « tout sélectionner »), agence (siège exclu), produit ; carte : encours brut, PAR 30, taux de remboursement, crédits actifs, épargne, clients actifs ; encours et PAR 30 par mois (non filtré par le segment période) ; encours par agence ; indicateurs par produit ; PAR 30 par produit |
| États financiers | Segment période synchronisé ; carte : total actif, résultat cumulé, contrôle d'équilibre, écart de rapprochement (vert si 0, rouge sinon) ; bilan actif / passif (niveau IMF) ; compte de résultat (période et cumul) |
| Qualité & fraîcheur | Carte : date du gold, dernier run réussi, runs réussis, runs en échec, incidents, nœuds dbt réussis au dernier run ; durée moyenne par étape ; historique étape × statut ; incidents (pannes démontrées en phase 7) ; écarts gestion ↔ comptabilité par mois |

Bandeau « Données arrêtées au » et alerte en haut de chaque page.

## 4. Étapes

| Étape | Critère | État |
|---|---|---|
| 1. Préparation | Rôle rejouable, lecture après `dbt build`, écriture refusée, connexion Windows au bon serveur, `modele_donnees.md`, thème, encours de référence | ✅ 22/11/2026 ; encours brut au 31/12 = **1 850 520 623 XOF** (vérité = mart = bilan A1 = rapprochement) |
| 1 bis. Ordre du compte de résultat | K12 tranché | ✅ tri par `rubrique`, aucun changement dbt |
| K14. Libellés | `make check` vert, chiffres inchangés | ✅ 23/11/2026 |
| 2. Modèle et mesures | Chiffres de référence au 31/12 ; cartes non vides sans filtre et sur l'année ; tests janvier / juin | ✅ bilan 2 119 584 054 ; résultat −333 130 376 ; PAR 30 4,9992 % ; encours 1 850 520 623 ; rapprochements 0 ; 365 runs réussis ; au 30/06 encours 766 464 543 ; janvier vide |
| 3. Pages | 3 pages, thème, guide | ✅ 23/11/2026 |
| 4. Test « à date » | Gold au 15/03 sans Airflow (`audit_runs` inchangé, 3 201 lignes) : bandeau 15/03, alerte rouge, cartes non vides ; retour au 31/12 : empreinte identique à la référence de la phase 8, alerte vide | ✅ 23/11/2026 : encours 163 386 715 ; bilan 1 876 010 446 équilibré ; PAR 30 0 % ; captures au 15/03 |
| 5. Livraison | Captures, `mesures.md`, README, cadrage public, un seul commit | ✅ 24/11/2026 |

**Compteurs après K14** : 398 tests dbt (388 de données + 10 unitaires), 203 pytest, soit 601 tests automatisés ; `make check` = 450 nœuds PASS (388 + 10 + 6 seeds + 46 modèles). Le dernier run Airflow (avant K14) compte 442 nœuds dbt réussis.

**Chiffres d'audit** : 32 lignes d'incident dans l'historique (21 avertissements, 6 échecs de contrôle, 5 échecs techniques), toutes issues des démonstrations de pannes de la phase 7 ; 16 lignes à plus d'une tentative ; durée moyenne d'une étape `dbt_build` ≈ 21 s.

## 5. Limites et hors périmètre

- Publication sur le service Power BI (compte professionnel requis) ; Power BI sur BigQuery (bonus, phase 9) ; correctif du contrôle de volume (phase 9).
- Page d'exploration de la balance non construite (mesures de balance conservées comme mesures de contrôle).
- Le dashboard lit la base locale : actualisation possible seulement avec le conteneur PostgreSQL démarré.
