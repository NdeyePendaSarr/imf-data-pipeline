# P1 – Phase 5 : cadrage gold (v0.2, 21/11/2026) – phase terminée

> Complète le PRD v1.5 et les cadrages des phases 0 à 4. Décisions G1 à G15, appliquées aux lots A (c03361a), B (18b046c) et C (2905bce). **Validation de Ndeye Penda à confirmer** (aucune objection à ce jour). À reporter dans le PRD v1.6 avec les écarts de la phase 4.

## 1. Lots

| Lot | Contenu | Critère | Statut |
|---|---|---|---|
| A | Reports de phase 4 (empreinte imf_ops, test unitaire des mouvements) + 8 dimensions | dbt build et make check verts | ✅ c03361a |
| B | int_evenements_comptables, int_evenements_rejetes, fct_ecritures, tests comptables, seeds v0.4, PAR 30 de la vérité | Balance équilibrée, rejets vides (critère du PRD) | ✅ 18b046c |
| C | fct_operations, fct_echeances, fct_remboursements, fct_portefeuille_quotidien, fct_solde_compte_mensuel | Tests verts, vérité retrouvée (encours, PAR 30) | ✅ 2905bce |

## 2. Décisions

| # | Décision | Justification |
|---|---|---|
| G1 | Écritures construites depuis les 6 sources d'événements (slv_*), jamais depuis int_mouvements_compte, qui ne sert qu'à fct_solde_compte_mensuel | Une écriture = une source ; sinon les prélèvements seraient comptés deux fois |
| G2 | Moteur générique : int_evenements_comptables (un événement par ligne : type, source_table, source_id, date, agence, canal), montants au format long (champ_montant, montant), jointure sur mapping_comptable (type, source, champ), @TRESORERIE résolu par le canal, lignes à 0 omises. Aucun CASE sur les types | Ajouter une règle = ajouter une ligne de seed |
| G3 | int_evenements_rejetes, motif ∈ {TYPE_SANS_REGLE, CANAL_SANS_TRESORERIE, COMPTE_HORS_PLAN}, un motif par événement (priorité dans cet ordre), test en erreur si non vide ; test de complétude : événements = pièces + rejets | Une jointure interne perd des lignes en silence |
| G4 | id_ecriture = source_table:source_id:type_evenement (un crédit = 2 pièces) | Lisible, remontée à la source sans table de correspondance |
| G5 | Colonne type_evenement dans journaux.csv (OUV → OUVERTURE, VIR → APPRO_CAISSE) : seeds v0.4 | D15 exécutable en SQL ; la règle n'était qu'en texte libre |
| G6 | Agence de l'écriture = agence du client (opérations, crédits, remboursements), agence de la source sinon | Condition du rapprochement D9 par agence |
| G7 | Ouverture datée du 01/01 de la var `exercice` ; toutes les dates dans l'exercice (test) | La source ouverture n'a pas de date |
| G8 | version_mapping = var dbt (`v0.4`), incrémentée à chaque changement d'un seed de mapping | Traçabilité de la règle appliquée |
| G9 | Clés naturelles (id sources) ; la date est la clé de date. Clé de substitution seulement avec le SCD 2 (bonus) | Une source par entité, pas d'historisation au MVP |
| G10 | Tranche d'âge au 31/12 de l'exercice, jamais current_date ; nulls → NON_RENSEIGNE | Reproductibilité |
| G11 | Retard en FIFO cumulé : au jour d, retard = d − date prévue de la plus ancienne échéance échue dont le cumul dû (capital + intérêts) dépasse le cumul payé (capital + intérêts, pénalités exclues). Encours = montant accordé − Σ part capital ≤ d. PAR 30 : retard > 30 jours (30 exclu, 31 inclus). **Même définition que le générateur** (`en_retard_30`, `calculer_par30`, vérifié au lot A) | Sinon le PAR 30 recalculé ne veut rien dire |
| G12 | fct_operations.est_activite_client = false pour FRAIS_TENUE (22 % des opérations), avec un test | Les KPI d'activité de la phase 6 excluent les frais |
| G13 | Caisse cumulée ≥ 0 par agence et par jour, banque cumulée ≥ 0 par jour au niveau de l'IMF, testées sur fct_ecritures | Les écritures suffisent |
| G14 | Contrats appliqués sur toutes les tables gold ; tables, pas d'incrémental | Même règle qu'en silver |
| G15 | Rubrique R5_COUT_DU_RISQUE mixte (dotation et reprise, coût du risque net) : seule exception nommée du test D17 | Ligne nette usuelle en banque ; bonus seulement |

## 3. Écarts et points techniques

- `dim_date` couvre l'exercice + 2 ans (var `annees_apres_exercice: 2`), car des échéances tombent jusqu'au 31/12/2027. fct_solde_compte_mensuel ne prend que les 12 fins de mois de l'exercice.
- Le PAR 30 de la vérité est la valeur obtenue par la calibration, pas 5 % : `data/_verite/par30.csv` (2025-12-31 ; 92 511 316 / 1 850 520 623 = 0,049992). Le pipeline la retrouve exactement (lot C).
- Seeds en `full_refresh: true` (lot C) : plus d'étape manuelle quand les colonnes d'un seed changent.
- Si un test amont échoue, dbt build saute les modèles en aval et **l'ancienne table reste en base** : en phase 7, Airflow doit bloquer sur ce code d'erreur.

## 4. Résultats

**Lot B.** 84 572 pièces, 181 193 lignes, Σ débit = Σ crédit = 13 140 567 531 XOF ; 0 rejet ; complétude 84 572 = 84 572. Journaux : CAI 31 119, OD 22 761, MOB 19 518, AGT 10 860, BQ 167, VIR 141, OUV 6. Caisse minimale 3 002 580 XOF (AG841, 01/07/2025) et banque minimale 163 883 235 XOF (31/12/2025) = manifeste du générateur au franc près. Mutations : règle supprimée → équilibre ; canal supprimé → rejets ; sens inversé → équilibre, caisse, montants par type.

Lignes de REMBOURSEMENT : 11 684 lignes de trésorerie (caisse 3 674, mobile 3 989, agent 2 020, prélèvement 2 001), 11 684 de capital, 11 441 d'intérêts (243 remboursements sans intérêts), 608 de pénalités.

**Lot C.** fct_operations 66 514 (dont 14 760 FRAIS_TENUE hors activité), fct_remboursements 11 684, fct_echeances 34 037, fct_portefeuille_quotidien 347 012 (5,3 s), fct_solde_compte_mensuel 14 946. dbt build PASS=352 (~26 s), pytest 150. PAR 30 au 31/12 = vérité au franc près ; 2 317 soldes au 31/12 = vérité recalculée hors dbt. Aperçu D9 au 31/12 : DEPOTS_EPARGNE 605 714 430 = Σ soldes clients ; CREDITS_SAINS 1 850 520 623 = Σ encours.

## 5. Points ouverts pour la phase 6

1. **Fins de mois un dimanche.** fct_portefeuille_quotidien n'a que des jours ouvrés (lundi–samedi) ; le 31/08/2025 et le 30/11/2025 sont des dimanches, donc sans ligne. Les rapprochements D9 et le PAR « à chaque fin de mois » exigent une décision : ajouter les fins de mois calendaires au grain, ou passer à tous les jours calendaires. Le retard se compte en jours calendaires : prendre le samedi fausserait le PAR à la frontière des 30 jours.
2. **Commissions mobile money de décembre** : facturées en m+1 par le générateur, donc absentes de l'exercice (11 pièces, février à décembre). Limite à écrire dans le README (pas de charges à payer).
3. **243 remboursements sans intérêts** : vérifier l'ordre d'imputation du générateur (pénalités → intérêts → capital est l'usage) et documenter.
4. **Second cas chiffré** (cadrage phase 0 §4, avec l'approvisionnement de 200 000) : **calculé à la main**. Il couvre écritures, balance, rapprochements et bilan : il devient le test unitaire des marts.
5. Ranger les cadrages dans le dépôt (docs/) pour que Claude Code les trouve.
