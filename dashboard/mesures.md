# Mesures DAX du dashboard

Mesures de la table `_Mesures` du modèle `senfinance_dashboard.pbix` (cadrage de la phase 8,
K1 à K14), et la colonne calculée `est_etat_final` de `audit_runs`. Formules recopiées du modèle
(TMDL). Modèle de données : [`modele_donnees.md`](modele_donnees.md).

**Types.** *Stock semi-additif* : valeur à une date, évaluée au dernier jour qui a des données,
jamais sommée dans le temps (K2). *Flux* : mouvement d'une période, se somme. *Ratio* : calculé
par `DIVIDE` à chaque niveau d'agrégation, jamais stocké (K7). *Qualité* : fraîcheur, audit,
contrôles et mise en forme.

**Affichée** : visible sur l'une des trois pages (captures dans [`captures/`](captures/)).

## 1. Fraîcheur et audit (K1, K13)

| Mesure | Type | Affichée | Description |
|---|---|---|---|
| Date du gold | Qualité | Oui | Date de situation réelle du gold : `max(date_situation)` de `mart_bilan`, sans aucun filtre. Ce que le dashboard montre vraiment (K1). |
| Dernier run réussi | Qualité | Oui | Dernière `date_logique` d'une ligne `RUN` en `SUCCES` de l'audit, sans filtre (K1). |
| Statut dernier run | Qualité | Non (sert à l'alerte) | Statut de la dernière ligne `RUN` écrite (plus grand `id_audit`). |
| Bandeau arrêté | Qualité | Oui | Texte « Données arrêtées au … » en tête de chaque page, sur la date du gold. |
| Alerte fraîcheur | Qualité | Oui (si non vide) | Alerte rouge si le dernier run est en échec, ou si la date du gold diffère du dernier run réussi (gold reconstruit à la main, run en échec). Vide sinon (K1). |
| Runs réussis | Qualité | Oui | Lignes `RUN` en `SUCCES`, état final de chaque jour seulement (K13) : un jour rejoué ne compte qu'une fois. |
| Runs en échec | Qualité | Oui | Lignes `RUN` en échec de contrôle ou technique, état final seulement ; `+ 0` affiche 0 au lieu d'un vide. |
| Durée moyenne (s) | Qualité | Oui | Durée moyenne des étapes (hors ligne `RUN`, de durée nulle), états finaux seulement. |
| Incidents (historique) | Qualité | Oui | Toutes les lignes d'audit qui ne sont pas en `SUCCES`, tentatives et pannes démontrées comprises (K13 : on les montre au lieu de les filtrer). |
| Nœuds dbt réussis (dernier run) | Qualité | Oui | `nb_pass` du dernier `dbt_build` réussi de l'audit (dernier run Airflow, pas un `dbt build` manuel). |

```dax
Date du gold = CALCULATE ( MAX ( mart_bilan[date_situation] ), REMOVEFILTERS () )

Dernier run réussi = CALCULATE ( MAX ( audit_runs[date_logique] ), audit_runs[etape] = "RUN", audit_runs[statut] = "SUCCES", REMOVEFILTERS () )

Statut dernier run = VAR idmax = CALCULATE ( MAX ( audit_runs[id_audit] ), audit_runs[etape] = "RUN", REMOVEFILTERS () ) RETURN CALCULATE ( MAX ( audit_runs[statut] ), audit_runs[id_audit] = idmax, REMOVEFILTERS () )

Bandeau arrêté = "Données arrêtées au " & FORMAT ( [Date du gold], "dd/mm/yyyy" )

Alerte fraîcheur = SWITCH ( TRUE (), [Statut dernier run] <> "SUCCES", "⚠ Dernier run en échec : certaines tables peuvent dater d'un autre arrêté", [Date du gold] <> [Dernier run réussi], "⚠ Gold au " & FORMAT ( [Date du gold], "dd/mm/yyyy" ) & ", dernier run réussi au " & FORMAT ( [Dernier run réussi], "dd/mm/yyyy" ), "" )

Runs réussis = CALCULATE ( COUNTROWS ( audit_runs ), audit_runs[etape] = "RUN", audit_runs[statut] = "SUCCES", audit_runs[est_etat_final] = TRUE () )

Runs en échec = CALCULATE ( COUNTROWS ( audit_runs ), audit_runs[etape] = "RUN", audit_runs[statut] IN { "ECHEC_CONTROLE", "ECHEC_TECHNIQUE" }, audit_runs[est_etat_final] = TRUE () ) + 0

Durée moyenne (s) = CALCULATE ( AVERAGE ( audit_runs[duree_s] ), KEEPFILTERS ( audit_runs[etape] <> "RUN" ), audit_runs[est_etat_final] = TRUE () )

Incidents (historique) = CALCULATE ( COUNTROWS ( audit_runs ), audit_runs[statut] <> "SUCCES" )

Nœuds dbt réussis (dernier run) = VAR idmax = CALCULATE ( MAX ( audit_runs[id_audit] ), audit_runs[etape] = "dbt_build", audit_runs[statut] = "SUCCES", REMOVEFILTERS () ) RETURN CALCULATE ( MAX ( audit_runs[nb_pass] ), audit_runs[id_audit] = idmax, REMOVEFILTERS () )
```

### Colonne calculée `audit_runs[est_etat_final]` (K13)

Vrai pour la dernière ligne écrite (plus grand `id_audit`) de chaque couple (`date_logique`,
`etape`). `run_id` n'étant pas unique d'un backfill à l'autre, c'est elle qui identifie l'état
final d'un jour après rejeux ; les indicateurs de runs (réussis, en échec, durées) ne portent que
sur ces lignes, l'historique des incidents sur toutes.

```dax
est_etat_final = audit_runs[id_audit] = CALCULATE ( MAX ( audit_runs[id_audit] ), ALLEXCEPT ( audit_runs, audit_runs[date_logique], audit_runs[etape] ) )
```

## 2. Portefeuille (K2, K7)

Toutes les mesures de stock du portefeuille sont évaluées à la **Date de référence** : le
dernier jour qui a des données dans la période sélectionnée, calculé **sans** les filtres agence
et produit (même jour pour toutes les agences) et plafonné à la date du gold. Pas de `LASTDATE` :
`dim_date` couvre l'exercice + 2 ans, et `LASTDATE` tomberait sur une date sans données.

| Mesure | Type | Affichée | Description |
|---|---|---|---|
| Date de référence | Stock semi-additif (date pivot) | Non (pivot des autres) | Dernier jour de `mart_kpi_portefeuille` dans la période, sans filtres agence / produit, ≤ date du gold. |
| Encours brut | Stock semi-additif | Oui | Σ `encours` au jour de référence. 1 850 520 623 XOF au 31/12/2025 (= vérité du générateur). |
| Encours PAR 30 | Stock semi-additif | Non (numérateur) | Σ encours des crédits à plus de 30 jours de retard, au jour de référence. |
| PAR 30 % | Ratio | Oui | Encours PAR 30 / encours brut, recalculé à chaque niveau (agence, produit, mois). |
| Taux de remboursement % | Ratio (de stocks) | Oui | Payé imputé cumulé / dû échu cumulé, au jour de référence ; numérateur déjà plafonné par crédit dans le mart (FIFO, G11). |
| Crédits actifs | Stock semi-additif | Oui | Σ `nb_credits_actifs` au jour de référence. |
| Encours d'épargne | Stock semi-additif | Oui (« Épargne ») | Σ soldes des comptes clients à la dernière `date_situation` de `fct_solde_compte_mensuel` dans la période, sans filtre agence, ≤ date du gold. |
| Clients actifs | Flux (comptage distinct) | Oui | Clients distincts ayant eu au moins une opération dans la période, frais de tenue exclus (G12). |
| Dépôts | Flux | Non | Σ des dépôts de la période. |
| Retraits | Flux | Non | Σ des retraits de la période. |

```dax
Date de référence = VAR dgold = [Date du gold] RETURN CALCULATE ( MAX ( mart_kpi_portefeuille[date] ), REMOVEFILTERS ( dim_agence ), REMOVEFILTERS ( dim_produit_credit ), KEEPFILTERS ( dim_date[date] <= dgold ) )

Encours brut = VAR d = [Date de référence] RETURN CALCULATE ( SUM ( mart_kpi_portefeuille[encours] ), dim_date[date] = d )

Encours PAR 30 = VAR d = [Date de référence] RETURN CALCULATE ( SUM ( mart_kpi_portefeuille[encours_par30] ), dim_date[date] = d )

PAR 30 % = DIVIDE ( [Encours PAR 30], [Encours brut] )

Taux de remboursement % = VAR d = [Date de référence] RETURN DIVIDE ( CALCULATE ( SUM ( mart_kpi_portefeuille[paye_impute_cumule] ), dim_date[date] = d ), CALCULATE ( SUM ( mart_kpi_portefeuille[du_echu_cumule] ), dim_date[date] = d ) )

Crédits actifs = VAR d = [Date de référence] RETURN CALCULATE ( SUM ( mart_kpi_portefeuille[nb_credits_actifs] ), dim_date[date] = d )

Encours d'épargne = VAR dgold = [Date du gold] VAR d = CALCULATE ( MAX ( fct_solde_compte_mensuel[date_situation] ), REMOVEFILTERS ( dim_agence ), KEEPFILTERS ( dim_date[date] <= dgold ) ) RETURN CALCULATE ( SUM ( fct_solde_compte_mensuel[solde] ), dim_date[date] = d )

Clients actifs = CALCULATE ( DISTINCTCOUNT ( fct_operations[id_client] ), fct_operations[est_activite_client] = TRUE () )

Dépôts = CALCULATE ( SUM ( fct_operations[montant] ), fct_operations[type_operation] = "DEPOT" )

Retraits = CALCULATE ( SUM ( fct_operations[montant] ), fct_operations[type_operation] = "RETRAIT" )
```

## 3. États financiers

| Mesure | Type | Affichée | Description |
|---|---|---|---|
| Solde bilan | Stock semi-additif | Oui | Σ `montant` de `mart_bilan` à la dernière `date_situation` du contexte (fin de mois choisie, ou date du gold). |
| Total actif | Stock semi-additif | Oui | Solde bilan, côté ACTIF. |
| Total passif | Stock semi-additif | Non (sert au contrôle) | Solde bilan, côté PASSIF (résultat cumulé compris). |
| Contrôle équilibre bilan | Qualité | Oui | Total actif − total passif ; attendu 0, vert si nul, rouge sinon. |
| Résultat du mois | Flux | Oui (« Résultat de la période ») | Σ `resultat_mois` : se somme sur les mois de la période. |
| Résultat cumulé | Stock semi-additif | Oui | `resultat_cumul` à la dernière `date_situation` du contexte ; la colonne de cumul ne se somme jamais sur plusieurs mois (K2). |
| Écart rapprochements | Qualité | Oui | Σ des écarts absolus gestion ↔ comptabilité ; attendu 0, vert si nul, rouge sinon. |
| Couleur équilibre | Qualité (mise en forme) | Non (couleur de carte) | Vert `#1B7F3B` si le bilan est équilibré, rouge `#B42318` (réservé aux alertes, thème) sinon. |
| Couleur rapprochements | Qualité (mise en forme) | Non (couleur de carte) | Même règle pour l'écart des rapprochements. |
| Mouvements débit | Flux | Non | Σ des débits du mois (`mart_balance`), pour une balance avec exploration. |
| Mouvements crédit | Flux | Non | Σ des crédits du mois (`mart_balance`). |
| Solde clôture débit | Stock semi-additif | Non | Soldes débiteurs de clôture à la dernière `date_situation` de la balance, calculée sans filtres agence / compte. |
| Solde clôture crédit | Stock semi-additif | Non | Soldes créditeurs de clôture, même règle. |

Les rubriques s'affichent par `libelle_rubrique` (K14), triées par `ordre` (bilan) ou par
`rubrique` (compte de résultat, K12).

```dax
Solde bilan = VAR d = MAX ( mart_bilan[date_situation] ) RETURN CALCULATE ( SUM ( mart_bilan[montant] ), dim_date[date] = d )

Total actif = CALCULATE ( [Solde bilan], mart_bilan[cote] = "ACTIF" )

Total passif = CALCULATE ( [Solde bilan], mart_bilan[cote] = "PASSIF" )

Contrôle équilibre bilan = [Total actif] - [Total passif]

Résultat du mois = SUM ( mart_compte_resultat[resultat_mois] )

Résultat cumulé = VAR d = MAX ( mart_compte_resultat[date_situation] ) RETURN CALCULATE ( SUM ( mart_compte_resultat[resultat_cumul] ), dim_date[date] = d )

Écart rapprochements = SUMX ( mart_rapprochements, ABS ( mart_rapprochements[ecart] ) )

Couleur équilibre = IF ( [Contrôle équilibre bilan] = 0, "#1B7F3B", "#B42318" )

Couleur rapprochements = IF ( [Écart rapprochements] = 0, "#1B7F3B", "#B42318" )

Mouvements débit = SUM ( mart_balance[mouvement_debit] )

Mouvements crédit = SUM ( mart_balance[mouvement_credit] )

Solde clôture débit = VAR d = CALCULATE ( MAX ( mart_balance[date_situation] ), REMOVEFILTERS ( dim_agence ), REMOVEFILTERS ( dim_compte_comptable ) ) RETURN CALCULATE ( SUM ( mart_balance[solde_cloture_debit] ), dim_date[date] = d )

Solde clôture crédit = VAR d = CALCULATE ( MAX ( mart_balance[date_situation] ), REMOVEFILTERS ( dim_agence ), REMOVEFILTERS ( dim_compte_comptable ) ) RETURN CALCULATE ( SUM ( mart_balance[solde_cloture_credit] ), dim_date[date] = d )
```

## 4. Mesures de contrôle non affichées

Utilisées pendant la construction pour vérifier le modèle contre la base (`imf_dwh`).

| Mesure | Type | Valeur attendue | Description |
|---|---|---|---|
| Lignes d'audit | Qualité | 3 201 | Nombre total de lignes de `audit_runs` : vérifie que l'import est complet. |
| Tentatives multiples | Qualité | 16 | Lignes d'audit à la tentative 2 ou plus : retries et reprises (`make airflow-reprendre`) de la démonstration de la phase 7 ; aucune dans le backfill de l'exercice. |

```dax
Lignes d'audit = COUNTROWS ( audit_runs )

Tentatives multiples = CALCULATE ( COUNTROWS ( audit_runs ), audit_runs[tentative] > 1 )
```

## Chiffres de contrôle

| Indicateur | Au 31/12/2025 | Au 15/03/2025 (test « à date ») |
|---|---:|---:|
| Encours brut | 1 850 520 623 | 163 386 715 |
| PAR 30 % | 4,9992 % | 0,0000 % |
| Taux de remboursement % | 96,16 % | 90,36 % |
| Total actif (= total passif) | 2 119 584 054 | 1 876 010 446 |
| Résultat cumulé | −333 130 376 | −82 888 129 |
| Contrôle équilibre bilan, écart rapprochements | 0, 0 | 0, 0 |
| Alerte fraîcheur | vide | « ⚠ Gold au 15/03/2025, dernier run réussi au 31/12/2025 » |
