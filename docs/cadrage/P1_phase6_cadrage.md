# P1 – Phase 6 : cadrage marts (v0.1, 21/11/2026)

> Complète le PRD v1.5 et les cadrages des phases 0 à 5. Décisions H1 à H12 **validées par Ndeye Penda le 21/11/2026** (avec G1–G15 de la phase 5). Écarts au PRD à reporter dans la v1.6, rédigée en fin de phase 6.

## 1. Lots

| Lot | Contenu | Critère | Statut |
|---|---|---|---|
| A | H1 (grain calendaire), H4 (docs/), seeds v0.5 (H8), vérification des 243 remboursements sans intérêts | dbt build vert ; PAR 30 au 31/12 = vérité ; 31/08 et 30/11 présents | à faire |
| B | mart_balance, mart_compte_resultat + tests | Σ D = Σ C par agence × mois ; cumul décembre = fct_ecritures | à faire |
| C | mart_bilan, mart_rapprochements + unit tests du second cas (calculé à la main) | Actif = passif + résultat chaque fin de mois ; 0 écart ; cas chiffré vert | à faire |
| D | mart_kpi_portefeuille + README phase 6 | Jalon : dépôt public, README à jour ; vrais chiffres du run | à faire |

## 2. Décisions

| # | Décision | Justification |
|---|---|---|
| H1 | fct_portefeuille_quotidien passe à **tous les jours calendaires** (colonne est_jour_ouvre conservée) | Un encours est un stock ; le retard se compte en jours calendaires ; aucun cas particulier pour les fins de mois du dimanche (31/08, 30/11). Écart PRD (« jour d'activité ») |
| H2 | Second cas chiffré → **dbt unit tests, un par mart** (balance, bilan, rapprochements), parents simulés, attendus calculés à la main | Un unit test dbt teste un modèle, pas une chaîne |
| H3 | PRD v1.6 en fin de phase 6 (écarts phases 4, 5, 6) | Une seule réécriture |
| H4 | docs/cadrage/ créé dès la phase 6 : cadrages P1 (0, 2 à 6), checklist SFD, PRD P1. **Aucun document hors du projet** | Claude Code doit les trouver ; seuls les documents du projet sont publiés |
| H5 | Balance 6 colonnes : solde d'ouverture D/C, mouvements D/C, solde de clôture D/C. Ouverture de janvier = 0 ; l'apport en capital est un mouvement de janvier (OUV) | Première année : pas d'à-nouveaux |
| H6 | Densification : une ligne compte × agence × mois dès le premier mouvement, même sans mouvement du mois | Sinon un compte sans mouvement disparaît malgré son solde |
| H7 | Bilan au niveau de l'IMF, sur mouvements agrégés ; pas de bilan par agence | G6 : la banque peut être créditrice dans une agence ; cohérent avec D19 |
| H8 | Colonne `rubrique_solde_inverse` dans plan_comptes (seeds v0.5, version_mapping v0.5) ; renseignée pour les liaisons (MM, agents) ; test en erreur si solde inversé et colonne vide | Non-compensation ; règle portée par le seed, aucun CASE sur les codes de comptes |
| H9 | Compte de résultat : rubrique × mois, montant du mois + cumul ; résultat = produits − charges ; le cumul à fin m alimente le bilan à fin m | Pas d'écriture de clôture ; test actif = passif + résultat |
| H10 | mart_rapprochements : fin de mois × agence × contrôle (DEPOTS, CREDITS), valeur gestion, valeur compta, écart ; test écart = 0 | D9 testé, pas seulement affiché. Nouveau modèle (PRD §6.2) |
| H11 | mart_kpi_portefeuille (jour × agence × produit) : numérateurs et dénominateurs seulement (encours, encours > 30 j, dû échu, payé imputé). Taux de remboursement = Σ min(cumul payé, cumul dû échu) / Σ dû échu, par crédit, FIFO (G11) | Ratios non additifs, recalculés dans Power BI ; min = pas de dépassement de 100 % par anticipation |
| H12 | Autres KPI (volumes, clients actifs, encours d'épargne, produits d'intérêts) calculés dans Power BI depuis les faits ; audit_runs reporté en phase 7 | Rôle du schéma en étoile ; correction PRD §6.2 vs §8.3 |

## 3. Limites à ajouter au README

- Commissions mobile money de décembre facturées en m+1 : hors exercice (pas de charges à payer).
- 243 remboursements sans intérêts : ordre d'imputation du générateur à documenter (lot A), sans correction.
