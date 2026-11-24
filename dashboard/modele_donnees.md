# Modèle de données du dashboard Power BI

Tables lues par Power BI (phase 8, cadrage `P1_phase8_cadrage.md`, K1 à K11) : colonnes et types
relevés dans `imf_dwh` après un `dbt build` par défaut (arrêté au 31/12/2025), grain, clés et
nature des montants (**stock** : valeur à une date, ne se somme pas dans le temps ; **flux** :
mouvement d'une période, se somme).

## Connexion

| Paramètre | Valeur |
|---|---|
| Serveur | `localhost:5433` (port publié par le conteneur `imf-postgres`, `POSTGRES_PORT`) |
| Base | `imf_dwh` |
| Rôle | `powerbi_lecteur` (lecture seule sur `gold` et `audit`, `make powerbi-role`, mot de passe `POWERBI_PASSWORD` du `.env`) |
| Mode | Import (K4) |

**Ne pas utiliser le port 5432** : sous Windows, il est occupé par un PostgreSQL local (processus
`postgres`) ; Power BI s'y connecterait sans prévenir. Le port 5433 est servi par Docker Desktop
(`com.docker.backend`, relais `wslrelay`).

**Chiffrement : décocher « Chiffrer les connexions ».** Le serveur du conteneur n'a pas de SSL ; le
connecteur PostgreSQL de Power BI coche cette option par défaut et la connexion échoue. *Fichier >
Options et paramètres > Paramètres de la source de données*, sélectionner `localhost:5433;imf_dwh`,
*Modifier les autorisations*, décocher *Chiffrer les connexions* (données fictives, poste local).

Test du port depuis Windows (PowerShell) :

```powershell
Test-NetConnection localhost -Port 5433    # TcpTestSucceeded : True
```

Contrôle d'identité du serveur, à lancer une fois connecté (requête native ou client SQL) :

```sql
select current_database(), inet_server_port(), host(inet_server_addr()),
       current_setting('server_version'), current_user;
-- imf_dwh | 5432 | 172.18.0.2 | 17.12 (Debian …) | powerbi_lecteur
```

`inet_server_port()` renvoie **5432**, port interne du conteneur, et non 5433 : il ne distingue
donc pas ce serveur du PostgreSQL local. Les marqueurs fiables sont `current_database() = imf_dwh`,
l'adresse réseau Docker (`172.18.x.x`) et la version 17 de Debian.

## Relations

| De | Vers | Remarque |
|---|---|---|
| `mart_kpi_portefeuille[date]`, `fct_operations[date_operation]` | `dim_date[date]` | `dim_date` : table de dates (K6) |
| `date_fin_mois` des marts mensuels et de `fct_solde_compte_mensuel` | `dim_date[date]` | ou `date_situation` (K6, K8) |
| `id_agence` des faits et marts | `dim_agence[id_agence]` | `mart_bilan` n'a pas d'agence (niveau IMF) |
| `code_produit` de `mart_kpi_portefeuille`, `dim_credit` | `dim_produit_credit[code_produit]` | |
| `mart_balance[code_compte]` | `dim_compte_comptable[code_compte]` | |

## Dimensions

### `gold.dim_date` — 1 095 lignes

Grain : un jour calendaire, du 01/01/2025 au 31/12/2027 (exercice + 2 ans, pour les échéances
postérieures). Clé : `date`. Les deux années après l'exercice n'ont aucune donnée de fait (K2 :
pas de `LASTDATE`) ; `dans_exercice` les écarte.

`date` date, `annee` integer, `mois` integer, `annee_mois` text (AAAA-MM), `trimestre` integer,
`jour_semaine` integer (ISO, 1 = lundi … 7 = dimanche), `exercice` integer, `dans_exercice`
boolean, `est_fin_de_mois` boolean (dernier jour calendaire), `est_jour_ouvre` boolean (lundi à
samedi, sans jours fériés).

### `gold.dim_agence` — 6 lignes

Grain : une agence, siège compris (`est_siege`, aucun client ; seul le siège a `est_siege` vrai).
Clé : `id_agence`.

`id_agence` text, `nom` text, `ville` text, `region` text, `type_agence` text, `est_siege` boolean.

### `gold.dim_produit_credit` — 4 lignes

Grain : un produit de crédit. Clé : `code_produit`.

`code_produit` text, `libelle` text, `taux_annuel` numeric, `taux_frais_dossier` numeric,
`duree_min_mois` smallint, `duree_max_mois` smallint, `periodicite` text.

### `gold.dim_credit` — 3 000 lignes

Grain : un crédit. Clé : `id_credit` ; vers `dim_produit_credit` par `code_produit`.
Attributs d'octroi (`montant_accorde`, `frais_dossier`) : montants fixes, ni stock ni flux.
**Toujours utiliser `statut_a_l_arrete`** (EN_COURS / SOLDE à la date d'arrêté) ;
`statut_au_31_12` est connu dès le décaissement et ne sert à aucune analyse à date (J17).

`id_credit` text, `id_client` text, `id_compte_epargne` text, `code_produit` text,
`date_decaissement` date, `montant_accorde` bigint, `frais_dossier` bigint, `duree_mois` smallint,
`taux_annuel` numeric, `statut_au_31_12` text, `statut_a_l_arrete` text.

### `gold.dim_compte_comptable` — 21 lignes

Grain : un compte du plan de comptes simplifié. Clé : `code_compte`. `etat` = BILAN ou CR ;
`nature` = ACTIF, PASSIF, PRODUIT ou CHARGE. Aucune colonne d'ordre de présentation.

`code_compte` text, `libelle` text, `nature` text, `sens_normal` text, `etat` text, `rubrique`
text, `compte_sfd` text, `compte_syscohada_equiv` text, `statut_correspondance` text, `mvp`
boolean, `rubrique_solde_inverse` text.

## Faits

### `gold.fct_operations` — 66 514 lignes — flux

Grain : une opération d'un compte client (01/01 → 31/12). Clé : `id_operation`.
`type_operation` : DEPOT, RETRAIT, FRAIS_TENUE ; `canal` : GUICHET, AGENT, MOBILE.
`montant` est un **flux** (somme sur la période). Clients actifs : comptage distinct de
`id_client` avec `est_activite_client` vrai (FRAIS_TENUE exclu, G12).

`id_operation` text, `date_operation` date, `id_compte` text, `id_client` text, `id_agence` text,
`type_operation` text, `canal` text, `montant` bigint, `est_activite_client` boolean.

### `gold.fct_solde_compte_mensuel` — 14 946 lignes — stock

Grain : un compte client ouvert × une fin de mois (12 dates). Clé : (`id_compte`,
`date_fin_mois`). `type_compte` : COURANT, EPARGNE. `solde` est un **stock** (jamais négatif) :
dernière fin de mois, jamais de somme dans le temps (K2).

`date_fin_mois` date, `id_compte` text, `id_client` text, `id_agence` text, `type_compte` text,
`solde` bigint, `date_situation` date.

## Marts

Les marts mensuels portent `date_situation = least(fin de mois, date_arrete)` : égal à
`date_fin_mois`, sauf pour le mois en cours d'un arrêté intermédiaire (J15, K8).

### `gold.mart_kpi_portefeuille` — 5 283 lignes — stocks

Grain : jour calendaire × agence × produit. Clé : (`date`, `id_agence`, `code_produit`).
Toutes les colonnes sont des **stocks** au jour (`du_echu_cumule` et `paye_impute_cumule` sont des
cumuls depuis le décaissement : stocks aussi) ; numérateurs et dénominateurs seulement (K7) :
PAR 30 = `encours_par30` / `encours`, taux de remboursement = `paye_impute_cumule` /
`du_echu_cumule`.

**Densification : partielle.** Le mart n'est **pas** densifié sur la grille complète jour × agence ×
produit : une ligne n'existe qu'à partir du premier décaissement du couple agence × produit, puis
chaque jour jusqu'à l'arrêté (la grille part de chaque crédit, du décaissement à l'arrêté, même
soldé). Constaté au 31/12 : 334 jours (du 01/02, premier décaissement, au 31/12 ; aucune ligne en
janvier), 20 couples (5 agences hors siège × 4 produits), chacun continu de sa première date au
31/12 ; 3 couples le 01/02, 15 le 30/06, 20 le 31/12 (dernier couple apparu le 02/08). Le dernier
jour avec données est donc le même pour toutes les agences, mais un couple n'a aucune ligne avant
son premier crédit (K2 : dernier jour calculé sans les filtres agence / produit).

`date` date, `id_agence` text, `code_produit` text, `nb_credits_actifs` integer, `encours`
bigint, `encours_par30` bigint, `du_echu_cumule` bigint, `paye_impute_cumule` bigint.

### `gold.mart_balance` — 879 lignes — flux et stocks

Grain : compte comptable × agence × fin de mois. Clé : (`date_fin_mois`, `code_compte`,
`id_agence`). Soldes d'ouverture et de clôture : **stocks** ; mouvements du mois : **flux**.
Densifiée dès le premier mouvement du couple compte × agence (H6) : 76 couples, chacun présent
chaque mois à partir de son premier mouvement. Aucune colonne d'ordre (tri par `code_compte` ou
par `dim_compte_comptable[rubrique]`).

`date_fin_mois` date, `code_compte` text, `id_agence` text, `solde_ouverture_debit` bigint,
`solde_ouverture_credit` bigint, `mouvement_debit` bigint, `mouvement_credit` bigint,
`solde_cloture_debit` bigint, `solde_cloture_credit` bigint, `date_situation` date.

### `gold.mart_compte_resultat` — 48 lignes — flux et cumuls

Grain : rubrique × fin de mois (4 rubriques × 12 mois : R1_PRODUITS_FINANCIERS,
R2_COMMISSIONS, R3_CHARGES_PERSONNEL, R4_CHARGES_GENERALES). Clé : (`date_fin_mois`,
`rubrique`). `montant_mois`, `resultat_mois` : **flux** du mois ; `montant_cumul`,
`resultat_cumul` : cumuls depuis le 01/01, **ne jamais les sommer** sur plusieurs mois (K2).
Résultat = Σ `resultat_*` des rubriques (signé : produits positifs, charges négatives).

**Ordre d'affichage : trier sur `rubrique`** (tri alphabétique, celui de Power BI par défaut),
pas de colonne d'ordre (K12). Vérifié sur les six rubriques de compte de résultat du plan de
comptes, en collation `en_US.utf8` comme en tri binaire : R1_PRODUITS_FINANCIERS <
R2_COMMISSIONS < R3_CHARGES_PERSONNEL < R4_CHARGES_GENERALES < R5_COUT_DU_RISQUE (bonus) <
R6_CHARGES_FINANCIERES (bonus), soit l'ordre des codes, celui des documents du projet (cas
chiffrés H9 : produits puis charges). Le mart ne contient que les quatre rubriques mouvementées
(R1 à R4). Limites : le préfixe à un chiffre ne tient que jusqu'à R9 ; si les rubriques bonus
sont activées et qu'on veut la présentation bancaire usuelle (charges financières R6 juste après
les produits financiers R1), le tri alphabétique ne suffira plus et une colonne `ordre` construite
comme celle de `mart_bilan` deviendra nécessaire.

`date_fin_mois` date, `rubrique` text, `libelle_rubrique` text, `type_rubrique` text (PRODUITS,
CHARGES, MIXTE), `montant_mois` bigint, `montant_cumul` bigint, `resultat_mois` bigint,
`resultat_cumul` bigint, `date_situation` date.

**Libellé à afficher : `libelle_rubrique`** (K14), trié par `rubrique` (*Trier par colonne*).

### `gold.mart_bilan` — 72 lignes — stocks

Grain : rubrique × fin de mois, **niveau IMF** (pas d'agence). Clé : (`date_fin_mois`,
`rubrique`). `montant` : **stock** (dernière fin de mois, jamais de somme dans le temps).
**Colonne d'ordre : `ordre`** (1 A1_CREDITS_CLIENTELE, 2 A2_TRESORERIE, 3 P1_CAPITAUX_PROPRES,
4 RESULTAT_CUMULE, 5 P2_DEPOTS_CLIENTELE, 6 P3_DETTES_TRESORERIE). Actif = passif (résultat
cumulé compris, côté PASSIF).

`date_fin_mois` date, `ordre` integer, `cote` text (ACTIF, PASSIF), `rubrique` text,
`libelle_rubrique` text, `montant` bigint, `date_situation` date.

**Libellé à afficher : `libelle_rubrique`** (K14), trié par `ordre` (*Trier par colonne*).

### Libellés des rubriques (K14)

Les deux états portent `libelle_rubrique`, joint sur `rubrique` depuis le seed
`dbt/seeds/rubriques_etats.csv` (12 rubriques : A1, A2, P1, P2, P3, RESULTAT_CUMULE, R1 à R6 ;
UTF-8, accents et apostrophes compris). Seed de **présentation** : il ne touche ni à `ordre` ni à
`version_mapping`. Il est rangé dans `silver`, que `powerbi_lecteur` ne lit pas : Power BI prend
les libellés dans les marts, jamais dans le seed. Tests : `not_null` sur `libelle_rubrique`,
`relationships` de `rubrique` vers le seed (toute rubrique des marts a un libellé ; R5 et R6, sans
mouvement, sont dans le seed mais pas dans les marts).

| Rubrique | Libellé |
|---|---|
| A1_CREDITS_CLIENTELE | Crédits à la clientèle |
| A2_TRESORERIE | Trésorerie |
| P1_CAPITAUX_PROPRES | Capitaux propres |
| P2_DEPOTS_CLIENTELE | Dépôts de la clientèle |
| P3_DETTES_TRESORERIE | Dettes de trésorerie |
| RESULTAT_CUMULE | Résultat de l'exercice |
| R1_PRODUITS_FINANCIERS | Produits financiers |
| R2_COMMISSIONS | Commissions |
| R3_CHARGES_PERSONNEL | Charges de personnel |
| R4_CHARGES_GENERALES | Charges générales d'exploitation |
| R5_COUT_DU_RISQUE | Coût du risque |
| R6_CHARGES_FINANCIERES | Charges financières |

### `gold.mart_rapprochements` — 120 lignes — stocks

Grain : fin de mois × agence × contrôle (DEPOTS, CREDITS) ; 5 agences hors siège × 2 × 12.
Clé : (`date_fin_mois`, `id_agence`, `controle`). Valeurs de fin de mois : **stocks** ; `ecart`
= gestion − compta, attendu 0.

`date_fin_mois` date, `id_agence` text, `controle` text, `valeur_gestion` bigint, `valeur_compta`
bigint, `ecart` bigint, `date_situation` date.

## Audit : `audit.audit_runs` — 3 201 lignes

Grain : une étape × une tentative d'un run, plus une ligne `etape = 'RUN'` par run (teardown).
Clé : `id_audit` (identité, ordre d'écriture). Ajout seul (J13).

| Colonne | Valeurs distinctes (au 22/11/2026) |
|---|---|
| `etape` | verifier_environnement, attendre_fichiers, ingerer, controler_completude, controler_volume, dbt_build, RUN |
| `statut` | SUCCES, AVERTISSEMENT, ECHEC_CONTROLE, ECHEC_TECHNIQUE (`NON_EXECUTE` est autorisé par la contrainte mais n'apparaît que dans le `message` des lignes RUN) |

**À savoir pour le dashboard (K1, K5) :**
- la table contient **3 201 lignes, pas 2 555** : les 2 555 lignes du backfill de l'exercice
  (lot D, `debut >= 2026-11-22 16:15:32+00`) et 646 lignes de la démonstration du trimestre
  (lot C, pannes comprises) ;
- **`run_id` n'est pas unique d'un backfill à l'autre** (`backfill__2025-01-01T00:00:00+00:00` existe
  dans les deux) : 365 `run_id` distincts. Le dernier état d'un jour = la ligne de plus grand
  `id_audit` (ou `debut`) pour ce `date_logique` ;
- les ECHEC_* et AVERTISSEMENT de l'historique viennent tous du lot C ; le lot D n'a que des SUCCES.

`id_audit` bigint, `dag_id` text, `run_id` text, `date_logique` date, `etape` text, `tentative`
integer, `statut` text, `debut` timestamptz, `fin` timestamptz, `duree_s` numeric,
`lignes_chargees` bigint, `nb_pass` integer, `nb_warn` integer, `nb_error` integer, `nb_skip`
integer, `noeuds_en_echec` text[], `noeuds_sautes` text[], `version_mapping` text, `commit_git`
text, `message` text.

## Contrôle de référence : encours brut au 31/12/2025

| Source | Encours brut (XOF) |
|---|---:|
| Vérité du générateur, `data/_verite/par30.csv` (`encours_total`) | **1 850 520 623** |
| Vérité recalculée : Σ `montant_accorde` − Σ `part_capital` remboursée (`data/_verite/`) | 1 850 520 623 |
| `gold.mart_kpi_portefeuille`, Σ `encours` au 31/12 | 1 850 520 623 |
| `gold.mart_bilan`, A1_CREDITS_CLIENTELE au 31/12 | 1 850 520 623 |
| `gold.mart_rapprochements`, CREDITS au 31/12 (gestion = compta, écart 0) | 1 850 520 623 |

La carte « Encours brut » sans filtre ou sur « année 2025 » doit afficher **1 850 520 623 XOF**
(1 850,5 M XOF) : un `SUM` sur la période donnerait environ 30 fois plus par mois (K2).
