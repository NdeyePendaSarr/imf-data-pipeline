# P1 – Phase 0 : cadrage (v0.3, 21/11/2026)

> Complète le PRD `PRD_pipeline_IMF_SYSCOHADA.md`. Statut : **validé par Ndeye Penda le 21/11/2026**. Ce document liste les décisions et le modèle de données. Les seeds sont dans `dbt/seeds/`.
> **v0.2 (21/11/2026)** : trois corrections de cohérence dans les seeds (D15, D16, D17) ; nouveau seed `canaux_autorises.csv`.
> **v0.3 (21/11/2026, rouverte pendant la phase 2)** : approvisionnement des caisses par la banque (D18), banque ≥ 0 (D19), TEG sous le taux d'usure (D20), anomalies sans altération de la vérité (D21). Nouvelle source `appro_caisse`, nouvelle source de référence `produits_credit`, nouveau journal `VIR`, colonne `traitement_attendu` dans `catalogue_anomalies`. Seeds modifiés : `mapping_comptable.csv`, `journaux.csv`.

## 1. Décisions de cadrage

| # | Décision | Justification (à défendre en entretien) |
|---|---|---|
| D1 | **Référentiel : option hybride.** Comptes à code interne stable, colonne `compte_sfd` (à remplir depuis le RCSFD), colonne `compte_syscohada_equiv` + `statut_correspondance` (EQUIVALENT / APPROXIMATIF / A_VERIFIER) | Une IMF relève du RCSFD de la BCEAO. Le code interne découple le pipeline de la numérotation : changer de référentiel = changer un seed, pas le code |
| D2 | **Aucune affectation par défaut.** Un événement sans règle de mapping va dans `int_evenements_rejetes` ; un test dbt exige que cette table soit vide | Une affectation par défaut donne une balance équilibrée et fausse |
| D3 | **Intérêts à l'encaissement** (MVP) | Simple. **Écart au RCSFD**, qui repose sur une comptabilité d'engagement → section Limites |
| D4 | **Provisions en bonus** | Bilan surévalué si PAR 30 > 0 → section Limites |
| D5 | **Décaissement par virement sur le compte d'épargne du client** ; frais de dossier prélevés sur ce compte | Pratique courante des IMF ; crée le lien gestion ↔ comptabilité testé en D9 |
| D6 | **Épargne non rémunérée** (MVP) | Compte `CHARGE_INTERETS_EPARGNE` prévu, inactif |
| D7 | **Trésorerie résolue par le canal** (`@TRESORERIE` + `mapping_canal_tresorerie.csv`) : guichet → caisse, agent → liaison agents, mobile → liaison mobile money, virement → banque, prélèvement → compte d'épargne | Un seul mapping par type d'opération au lieu d'un par couple type × canal |
| D8 | **IMF en première année d'activité** : création le 01/01, apport en capital en banque et fonds de caisse par agence (`ouverture`), pas d'à-nouveaux | Évite de générer un portefeuille historique. Limite : PAR faible en début d'année |
| D9 | **Rapprochement gestion ↔ comptabilité testé** : solde comptable `DEPOTS_EPARGNE` = Σ soldes des comptes clients ; solde `CREDITS_SAINS` = Σ encours du portefeuille, à chaque fin de mois | C'est le problème n°4 du PRD ; c'est le test le plus parlant pour un recruteur finance |
| D10 | **Montants en XOF entiers** (`BIGINT`), jamais de flottants ; la dernière échéance absorbe l'arrondi | Le franc CFA n'a pas de centimes ; un flottant casse débit = crédit |
| D11 | **Exercice = année civile**, paramétrable (`EXERCICE=2025` par défaut) ; 12 mois, ~2 000 clients, ~3 000 crédits, paramètres du générateur | Choix de la porteuse |
| D12 | **Pas d'écriture de clôture dans le MVP** : le résultat est calculé (produits − charges) dans `mart_bilan` | Le résultat reste calculé ; l'écriture de clôture est hors MVP |
| D13 | **Comptes de liaison non compensés** (MVP) : ils s'accumulent sur l'année | Limite ; compensation hors MVP |
| D14 | **Caisse jamais négative** : test dbt par agence et par jour ; le générateur approvisionne les caisses depuis la banque (D18) | Contrôle métier réaliste |
| D15 | **Priorité des journaux** (colonne `priorite` de `journaux.csv`) : 1 = journal fixé par le type d'événement (OUV, VIR), 2 = journal du canal de trésorerie (CAI, AGT, MOB, BQ), 3 = OD. Une écriture prend le journal de priorité la plus forte | Sans règle, l'ouverture recevait deux journaux : OUV par le type, BQ ou CAI par le canal. Une écriture n'a qu'un journal |
| D16 | **Canaux autorisés par source** (seed `canaux_autorises.csv`) : opérations = GUICHET, AGENT, MOBILE ; remboursements = les 4 ; charges = VIREMENT, GUICHET ; ouverture = VIREMENT, GUICHET. Test `relationships` (source, canal) en silver. `appro_caisse` n'a pas de canal : ses deux comptes sont fixes | Sans borne, une charge payée en PRELEVEMENT débiterait le compte d'épargne d'un client. Le canal PRELEVEMENT n'a de sens que pour un remboursement |
| D17 | **Rubrique `R6_CHARGES_FINANCIERES`** pour `CHARGE_INTERETS_EPARGNE` (bonus) | Le compte était rangé dans `R1_PRODUITS_FINANCIERS` : une charge dans une rubrique de produits fausse le compte de résultat |
| **D18** | **Approvisionnement des caisses par la banque.** Nouvelle source `appro_caisse` (id, date, agence, montant), nouvel événement `APPRO_CAISSE` : débit `TRESO_CAISSE`, crédit `TRESO_BANQUE`, dans un journal dédié **`VIR`** (virements internes de fonds, priorité 1). Le générateur déclenche un approvisionnement quand la caisse prévisionnelle d'une agence passe sous un seuil, pour la ramener à un plafond (paramètres). Le fonds de caisse d'ouverture = le plafond | Sans cet événement, les retraits des crédits décaissés (D5) vident les caisses ; il aurait fallu des fonds de caisse de dizaines de millions par agence, irréalistes. Journal dédié : l'écriture touche deux comptes de trésorerie et n'a pas de ligne `@TRESORERIE`, elle tomberait en OD par D15. La pratique comptable passe par un compte de virements internes (585), écarté ici ; on garde donc une seule pièce |
| **D19** | **Banque ≥ 0, chaque jour, au niveau de l'IMF** (toutes agences confondues). Le générateur calcule le besoin maximal de la banque (approvisionnements + charges par virement) et fixe le capital d'ouverture (agence SIEGE, canal VIREMENT) = besoin × (1 + marge), arrondi au million supérieur | La banque est un seul compte de l'IMF ; l'agence portée par l'écriture est un axe analytique. Par agence, le solde « banque » d'une agence approvisionnée est négatif par construction : le test se fait donc au niveau de l'IMF |
| **D20** | **TEG sous le taux d'usure (24 % l'an).** Le TEG inclut les frais de dossier (pas les pénalités, qui ne sont dues qu'en cas de retard). Il est calculé **en taux actuariel**, la méthode la plus stricte (≥ taux proportionnel), sur l'échéancier de chaque crédit ; test pytest sur tous les crédits | Le taux d'usure s'apprécie sur le TEG, pas sur le taux nominal. Exemple calculé : 15 % nominal + 2 % de frais sur 6 mois → TEG actuariel 24,51 %, au-dessus du plafond |
| **D21** | **Les anomalies n'altèrent jamais la vérité propre.** Les défauts qui seraient rejetés ou dédoublonnés en silver portent sur des **lignes ajoutées** ; seules deux catégories touchent de vraies lignes : les altérations que silver corrige à l'identique (casse, espaces : STANDARDISER) et les nulls sur des colonnes non critiques (secteur, date de naissance : ACCEPTER_NULL). Colonne `traitement_attendu` dans `catalogue_anomalies` | Si silver rejette une vraie ligne, les soldes changent, la caisse ou un compte client peut devenir négatif et les rapprochements D9 deviennent faux. Avec D21, silver nettoyé = vérité, au franc près |

## 2. Sources (zone brute) après corrections

| Source | Ajouts par rapport au PRD §6.1 |
|---|---|
| `agences` | Une agence `SIEGE` (porte le capital et les charges centrales) |
| `operations` | Types : DEPOT, RETRAIT, FRAIS_TENUE. Canal ∈ {GUICHET, AGENT, MOBILE} |
| **`produits_credit`** (nouvelle, v0.3) | code, libellé, taux nominal annuel, taux de frais de dossier, durée min et max (mois), périodicité (MENSUELLE au MVP). Source de `dim_produit_credit` |
| `credits` | + `frais_dossier` (XOF), + `id_compte_epargne` (compte crédité au décaissement) |
| `remboursements` | + `canal` ∈ {GUICHET, AGENT, MOBILE, PRELEVEMENT}. Règle : `montant_paye = part_capital + part_interets + penalites` (test silver) |
| **`charges`** (nouvelle) | id, date, agence, categorie (PERSONNEL, LOYERS, TELECOM_SI, FOURNITURES, COMMISSIONS_MM), montant, canal |
| **`ouverture`** (nouvelle) | agence, canal (VIREMENT = banque, GUICHET = caisse), montant |
| **`appro_caisse`** (nouvelle, v0.3) | id, date, agence approvisionnée, montant. Pas de canal (D16, D18) |
| **`catalogue_anomalies`** (sortie du générateur) | nature, table, id_ligne, nombre, **traitement_attendu** (DEDOUBLONNER / REJETER / STANDARDISER / ACCEPTER_NULL) — la liste des défauts injectés, pour prouver que les tests les attrapent |

Les mouvements induits sur les comptes d'épargne (virement du crédit, frais de dossier, prélèvements) **ne sont pas** dans `operations` : ils sont dérivés en silver (`int_mouvements_compte`). Une écriture n'a donc qu'une seule source, ce qui évite les doublons.

## 3. Schéma en étoile (gold)

### Dimensions

| Table | Grain | Attributs principaux | Remarque |
|---|---|---|---|
| `dim_date` | un jour | date, mois, trimestre, exercice, `est_fin_de_mois` | Jouée en plusieurs rôles (opération, échéance, décaissement) |
| `dim_agence` | une agence | nom, région | Inclut SIEGE |
| `dim_client` | un client | sexe, tranche d'âge, secteur, agence, date d'adhésion | SCD 1 au MVP ; SCD 2 en bonus |
| **`dim_compte_client`** (nouvelle) | un compte d'épargne | type (épargne / courant), statut, date d'ouverture, client | Correction 7 : ne pas confondre avec le compte comptable |
| `dim_produit_credit` | un produit | libellé, taux, durée type, périodicité | Issue de la source `produits_credit` (v0.3) |
| **`dim_credit`** (nouvelle) | un crédit | montant accordé, taux, durée, date de décaissement, frais de dossier, produit, client | Nécessaire au snapshot quotidien |
| `dim_compte_comptable` | un compte du plan | code interne, libellé, nature, sens normal, état, rubrique, `compte_sfd`, `compte_syscohada_equiv`, statut de correspondance | Issue du seed `plan_comptes.csv` |
| **`dim_journal`** (nouvelle) | un journal | code, libellé | Issue du seed `journaux.csv` (7 journaux en v0.3, dont VIR) |

Canal et type d'opération restent des **attributs dégénérés** dans les faits (moins de 6 valeurs chacun).

### Faits

| Table | Grain | Mesures | Clés | Volume |
|---|---|---|---|---|
| `fct_operations` | une opération de compte client | montant | date, compte client, client, agence, canal, type | paramètre du générateur |
| **`fct_echeances`** (nouvelle) | une échéance (crédit × n°) | capital dû, intérêts dus, payé à date, jours de retard | date prévue, crédit, client, agence, produit | ≈ crédits × durée moyenne |
| `fct_remboursements` | un remboursement | montant payé, part capital, part intérêts, pénalités | date, crédit, client, agence, canal | |
| `fct_portefeuille_quotidien` | un crédit × un jour d'activité | encours, jours de retard, tranche de retard | date, crédit, client, agence, produit | ≤ 3 000 × 365 ≈ 1,1 M (borne haute) |
| **`fct_solde_compte_mensuel`** (nouvelle) | un compte client × une fin de mois | solde | date, compte client, client, agence | ≈ comptes × 12 |
| `fct_ecritures` | une ligne d'écriture | débit, crédit (un des deux nul) | **`id_ecriture`** (pièce), `num_ligne`, date, journal, agence, compte comptable, `type_evenement`, `source_table`, `source_id`, `version_mapping` | ≈ 2 à 4 lignes par événement |

### Marts

| Mart | Grain |
|---|---|
| `mart_balance` | compte × agence × mois : solde d'ouverture D/C, mouvements D/C, solde de clôture D/C (balance à 6 colonnes) |
| `mart_compte_resultat` | rubrique × mois, plus le cumul de l'exercice |
| `mart_bilan` | rubrique × fin de mois (le 31/12 = bilan de l'exercice) |
| `mart_kpi_portefeuille` | jour × agence × produit |
| `audit_runs` | une exécution du pipeline |

### Tests clés (phases 4 à 6)

- Par `id_ecriture` : Σ débit = Σ crédit ; exactement un des deux > 0 par ligne.
- Tout `code_compte` de `fct_ecritures` existe dans `dim_compte_comptable` ; `int_evenements_rejetes` est vide.
- Chaque couple (source, canal) existe dans `canaux_autorises.csv` (D16) ; chaque `id_ecriture` a exactement un journal (D15) ; toute écriture `APPRO_CAISSE` est au journal VIR (D18).
- Toute rubrique d'un compte de nature CHARGE est une rubrique de charges, et inversement pour les produits (D17).
- Rapprochements D9 à chaque fin de mois.
- `mart_bilan` : actif = passif + résultat, à chaque fin de mois.
- Caisse ≥ 0 par agence et par jour (D14) ; banque ≥ 0 par jour au niveau de l'IMF (D19).
- Chaque anomalie de `catalogue_anomalies` est attrapée par au moins un test, avec le traitement attendu (D21).

Tests du générateur (phase 2, pytest) : TEG actuariel ≤ 24 % pour chaque crédit (D20) ; caisse ≥ 0 et banque ≥ 0 sur la vérité propre ; appliquer le catalogue aux sorties brutes redonne la vérité (D21).

## 4. Exemple chiffré (sert de cas de test dbt en phase 5)

Un crédit de 300 000 XOF avec 6 000 XOF de frais de dossier, puis un dépôt de 20 000 XOF au guichet, puis un remboursement par mobile money de 30 000 XOF (25 000 de capital, 4 500 d'intérêts, 500 de pénalités).

| Pièce | Journal | Compte | Débit | Crédit |
|---|---|---|---:|---:|
| 1 Décaissement | OD | CREDITS_SAINS | 300 000 | |
| | | DEPOTS_EPARGNE | | 300 000 |
| 2 Frais de dossier | OD | DEPOTS_EPARGNE | 6 000 | |
| | | PRODUIT_FRAIS_DOSSIER | | 6 000 |
| 3 Dépôt guichet | CAI | TRESO_CAISSE | 20 000 | |
| | | DEPOTS_EPARGNE | | 20 000 |
| 4 Remboursement mobile | MOB | TRESO_LIAISON_MM | 30 000 | |
| | | CREDITS_SAINS | | 25 000 |
| | | PRODUIT_INTERETS | | 4 500 |
| | | PRODUIT_PENALITES | | 500 |
| **Total** | | | **356 000** | **356 000** |

- Rapprochements : `CREDITS_SAINS` a un solde débiteur de 275 000, égal à l'encours de gestion (300 000 − 25 000). `DEPOTS_EPARGNE` a un solde créditeur de 314 000, égal au solde du compte client (300 000 − 6 000 + 20 000).
- Bilan : à l'actif, 275 000 de crédits + 50 000 de trésorerie = 325 000. Au passif, 314 000 de dépôts + 11 000 de résultat = 325 000.

**Second cas, à calculer toi-même** (il deviendra un test) : ouverture de 1 000 000 en banque ; un retrait de 50 000 par un agent sur le compte ci-dessus ; un remboursement par prélèvement de 30 000 (25 000 de capital, 5 000 d'intérêts) ; un loyer de 100 000 payé par virement. Donne les écritures, la balance, les deux rapprochements et le bilan. *(v0.3 : ajoute un approvisionnement de caisse de 200 000 depuis la banque, journal VIR.)*

## 6. Modifications à reporter dans le PRD (après validation)

v0.2 : reportées dans le PRD v1.1 à v1.3. v0.3 : reportées dans le PRD v1.4 (§6.1, §6.3, §8.3, §9, §10, §12).

## 7. Récap de phase

> **P1 – Phase 0 terminée (v0.3).** Option hybride : codes internes + `compte_sfd` (RCSFD, à remplir après relecture) + `compte_syscohada_equiv`. Décisions D1 à D21 dans `P1_phase0_cadrage.md`. Seeds v0.3 : `plan_comptes.csv` (21 comptes, dont 16 au MVP, inchangé), `mapping_comptable.csv` (+ APPRO_CAISSE), `mapping_canal_tresorerie.csv`, `journaux.csv` (7 journaux avec priorité, dont VIR), `canaux_autorises.csv`. Étoile : 8 dimensions, 6 faits, 4 marts + `audit_runs`. Sources ajoutées : `charges`, `ouverture`, `appro_caisse`, `produits_credit`, sortie `catalogue_anomalies` (avec `traitement_attendu`).
