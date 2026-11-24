# P1 – Phase 3 : ingestion bronze (cadrage et bilan, 21/11/2026)

> Complète le PRD v1.5. Critère de fin : relancer un jour déjà ingéré ne crée aucun doublon ; bronze = volumes bruts du manifeste. ✅ Atteint le 21/11/2026.

## 1. Décisions

| # | Décision | Pourquoi (pour l'entretien) |
|---|---|---|
| I1 | Bronze = `imf_dwh.bronze`, une table par objet : `csv_*`, `ops_*`, `meta_catalogue_anomalies` | La source se lit dans le nom de la table |
| I2 | CSV → toutes les colonnes en `TEXT` ; `imf_ops` → types de la source | Un export mal formé ne bloque jamais le chargement ; typage en silver |
| I3 | Métadonnées : `_id_run` (`AAAA-MM-JJ#n`, déterministe), `_source`, `_num_ligne` (ligne physique, en-tête = 1), `_sha256`, `_charge_le` | Traçabilité ligne par ligne ; `_num_ligne` distingue les doublons exacts |
| I4 | Bronze ne dédoublonne jamais ; idempotence des CSV par fichier : `DELETE WHERE _source` puis `COPY` ; même SHA-256 → `IGNORE` | Un `ON CONFLICT` effacerait les `DOUBLON_EXACT`, que silver doit détecter |
| I5 | `imf_ops` : fenêtre `filigrane < date_maj < J+1 00:00`, filigrane = max(date_maj) extrait ; ajout seul, `UNIQUE (pk, date_maj)` en filet de sécurité ; silver prendra la dernière version | Filigrane du PRD ; historique des versions conservé |
| I6 | Borne haute fonction de J, jamais de `now()` | Un run = fonction de (données, J) : rattrapage reproductible |
| I7 | Une transaction par jour (données + filigranes + journal `bronze._ingestions`) | Un jour passe en entier ou pas du tout |
| I8 | Extractions `imf_ops` écrites dans `data/landing/imf_ops/<table>/date=J/` (triées par clé), puis même chargeur que les CSV ; extraction vide → aucun fichier | Extraction → fichier immuable et haché → chargement ; phase 9 = simple envoi vers Cloud Storage |
| I9 | Fichier absent : erreur s'il figure au manifeste, sinon `VIDE` | Jour sans activité ≠ export perdu |
| I10 | **Correction du générateur** : `credits.date_maj` = décaissement, toujours (remplace la règle 9.1 de la phase 2 pour les crédits soldés) | Avec la date du solde, le crédit restait invisible en bronze entre décaissement et solde alors que son échéancier et ses remboursements l'étaient. Coût : le `statut` reflète le 31/12 dès le décaissement → silver ne l'utilise jamais pour une analyse à date |
| I11 | `charges` et `appro_caisse` découpés par jour comme `operations` ; `agences`, `ouverture`, catalogue = instantanés rechargés si leur SHA change | Sinon le bronze du 10/03 connaîtrait les charges de décembre |
| I12 | Empreinte de génération (paramètres, lignes, indicateurs, fichiers du manifeste) ; autre empreinte → erreur et `make reset-bronze` | On ne mélange jamais deux générations |
| I13 | Aucune nouvelle dépendance (`COPY` psycopg, pas de pandas) | Bronze ne transforme rien |
| I14 | **Correction du générateur** : décaissements selon une courbe mensuelle (`CROISSANCE_MENSUELLE`, quotas par produit et par mois, dates tirées parmi les jours ouvrés, aucun report) ; janvier = 0 ; février exempté du test « mois ≤ 1,25 × précédent » (comme mai et août) | Avant : date uniforme dans la fenêtre d'éligibilité → clients tardifs entassés en décembre (785 crédits, 26 %) et faux pics du lundi (dimanches reportés). Janvier à 0 : IMF créée le 01/01, compte ouvert depuis 30 jours exigé |

Point à défendre : les runs `imf_ops` sont **cumulatifs**. Un premier run au 31/12 charge toute l'année d'`imf_ops` mais seulement le CSV de ce jour ; rejouer un jour passé ne recharge rien (`make reset-bronze` pour tout rejouer).

## 2. Résultats (seed 42, configuration par défaut)

- Décaissements par mois : 01:0, 02:91, 03:113, 04:137, 05:264, 06:302, 07:340, 08:345, 09:380, 10:415, 11:295, 12:318 (vérifié en SQL). Jour max : 29/09 (29).
- Manifeste : 3 000 crédits ; PAR 30 au 31/12 = 5,00 % (paramètre ciblé, G6) ; capital = 1 797 000 000 XOF (avant : 1 999 000 000) ; 141 approvisionnements ; caisse minimale = 3 002 580 XOF ; remboursements 11 684 (vérité) / 11 918 (brut) ; échéances 34 037 ; opérations 68 848.
- Bronze = manifeste sur les 12 tables ; `make ingest-all` : 26,8 s pour 365 runs.
- Run du 31/12 : 2 952 lignes, dont 2 354 `FRAIS_TENUE` (dernier jour ouvré du mois).
- `make check` : 130 tests verts. Commits : 3fb9891, 94ead6b, c8a3acf, b201a67, c60a615, 1006dbc.

## 3. Leçons

- Une explication non vérifiée qui contredit une règle n'est pas une preuve : les « 3 569 lignes du 31/12 » avaient été justifiées à tort. Tout chiffre surprenant se justifie par une requête.
- Test de mutation manuel : casser la règle testée et vérifier que le test échoue.

## 4. À surveiller (phases 4 à 6)

- Silver : dernière version par clé dans `ops_*` ; ne jamais utiliser `credits.statut` pour une analyse à date.
- `FRAIS_TENUE` exclus des KPI d'activité et des flux d'espèces ; clé de `ouverture` = (agence, canal).
- PAR 30 : 5 % est un paramètre de la simulation ; le pipeline doit le **retrouver** en phase 6.
- Capital élevé : pas de refinancement, comptes de liaison non compensés (Limites).
- `test_relance_meme_jour` : remplacer `== 12` par `len(TABLES_BRONZE)`.
