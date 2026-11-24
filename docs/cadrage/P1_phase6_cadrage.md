# P1 – Phase 6 : cadrage marts (v0.2, 22/11/2026) – phase terminée et poussée

> Complète le PRD v1.6 et les cadrages des phases 0 à 5. Décisions H1 à H12 **validées par Ndeye Penda le 21/11/2026** (avec G1–G15 de la phase 5). Écarts reportés dans la PRD v1.6.

## 1. Lots

| Lot | Contenu | Critère | Statut |
|---|---|---|---|
| A | H1 (grain calendaire), H4 (docs/cadrage/, versions publiques allégées), seeds v0.5 (H8), vérification des 243 remboursements sans intérêts | dbt build vert ; PAR 30 au 31/12 = vérité ; 31/08 et 30/11 présents | ✅ 39b948b |
| B | mart_balance, mart_compte_resultat + tests | Σ D = Σ C par agence × mois ; cumul décembre = fct_ecritures | ✅ a15a6ae |
| C | mart_bilan, mart_rapprochements, unit tests du cas chiffré (P1_cas_chiffres_tests.md, calculé à la main) + test à deux agences | Actif = passif + résultat chaque fin de mois ; 0 écart ; cas chiffré vert ; résultat = vérité | ✅ 0f9e592 (après amend de 73a3de2, à confirmer par git log) |
| D | mart_kpi_portefeuille + README phase 6 | Jalon : dépôt public, README à jour ; vrais chiffres du run | ✅ 5659880 (+ 1850c56, docs), poussés le 22/11 |

## 2. Décisions

| # | Décision | Justification |
|---|---|---|
| H1 | fct_portefeuille_quotidien en **jours calendaires** (colonne est_jour_ouvre) ; convention « échue » = date prévue ≤ jour, partout | Un encours est un stock ; retard en jours calendaires ; pas de cas particulier pour les fins de mois du dimanche. Empreinte MD5 inchangée après alignement |
| H2 | Cas chiffré → dbt unit tests, un par mart, attendus calculés à la main, jamais modifiés pour faire passer un test | Un unit test dbt teste un modèle ; l'attendu est l'oracle |
| H3 | PRD v1.6 en fin de phase 6 | Une seule réécriture |
| H4 | docs/cadrage/ dès la phase 6, en **version publique allégée** ; la version complète reste la source de vérité | Les cadrages vivent avec le code qu'ils décrivent ; seul le contenu du projet est publié |
| H5 | Balance 6 colonnes ; ouverture de janvier = 0 ; l'apport en capital est un mouvement de janvier | Première année |
| H6 | Densification compte × agence × mois dès le premier mouvement ; rubriques mouvementées × 12 mois au compte de résultat | Un compte sans mouvement garde son solde |
| H7 | Bilan au niveau IMF, soldes calculés sur les **mouvements agrégés**, jamais en sommant les soldes d'agence | Banque créditée dans l'agence approvisionnée (G6) ; test à deux agences ajouté |
| H8 | `rubrique_solde_inverse` dans plan_comptes (seeds v0.5) : liaisons → P3_DETTES_TRESORERIE ; test si solde inversé sans rubrique | Non-compensation portée par le seed |
| H9 | Compte de résultat : montant du mois + cumul ; montants dans le sens de la rubrique, resultat_* = crédit − débit ; type_rubrique déduit de la nature des comptes | Résultat cumulé = ligne RESULTAT_CUMULE du bilan |
| H10 | mart_rapprochements sur **grille complète** fin de mois × agence × contrôle (valeurs manquantes = 0), test du nombre de lignes et écart = 0 | Une ligne absente ne doit pas faire disparaître un contrôle |
| H11 | mart_kpi_portefeuille : numérateurs et dénominateurs seulement ; payé imputé = min(cumul payé, cumul dû échu) **par crédit avant agrégation** ; crédits soldés gardés dans dû et payé | Ratios non additifs ; une avance ne cache pas un retard |
| H12 | Autres KPI dans Power BI ; audit_runs en phase 7 | Rôle du schéma en étoile |

Vérité : jamais dans l'entrepôt. Les tests dbt comparent les marts aux faits ; pytest compare les faits à data/_verite/ (PAR 30, encours, résultat).

## 3. Résultats (seed 42)

- dbt build : PASS = 432 (381 tests : 371 de données, 10 unitaires), 25,9 s ; pytest 152.
- Lignes : balance 879, compte de résultat 48, bilan 72, rapprochements 120, KPI 5 283 (01/02 → 31/12), portefeuille quotidien 404 573.
- Au 31/12/2025 : bilan 2 119 584 054 (A1 1 850 520 623, A2 269 063 431 ; P1 1 847 000 000, résultat −333 130 376, P2 605 714 430, P3 0). Résultat = vérité (produits 164 015 389, charges 497 145 765). PAR 30 = 92 511 316 / 1 850 520 623 (4,9992 %) = vérité. Taux de remboursement 999 172 879 / 1 039 096 786 = 96,16 %. Rapprochements : écart 0.
- Mutations attrapées : sans densification ; sans reclassement H8 ; bilan sommant les soldes d'agence (test à deux agences) ; sans min (KPI).
- 243 remboursements sans intérêts : soldes d'échéances payées en deux fois, l'acompte ayant couvert les intérêts (imputation pénalités → intérêts → capital, par échéance) ; 61 avec pénalité.
- Limite H7 chiffrée sur la **liaison agents seule** (le mobile money a un seul opérateur, son solde IMF est correct) : écart maximal entre P3 IMF et Σ P3 par agence de 13 297 824 au 30/11 ; 9 590 935 au 31/12.

## 4. Pour la phase 7

- Airflow doit bloquer quand dbt build saute des modèles en aval d'un test en échec (l'ancienne table reste en base).
- audit_runs, contrôles de volume.
