# P1 – Cas chiffrés de référence pour les unit tests des marts (phase 6)

> Calculés à la main à partir des seeds v0.5 et des règles du cadrage (H5 à H10). Hypothèses : une seule agence (AG_TEST), exercice 2025. **Janvier** = cas 1 du cadrage de la phase 0 (§4) + ouverture. **Février** = reste du second cas. Montants en XOF.

## 1. Écritures

| Pièce | Mois | Journal | Compte | Débit | Crédit |
|---|---|---|---|---:|---:|
| 1 Décaissement | janv. | OD | CREDITS_SAINS | 300 000 | |
| | | | DEPOTS_EPARGNE | | 300 000 |
| 2 Frais de dossier | janv. | OD | DEPOTS_EPARGNE | 6 000 | |
| | | | PRODUIT_FRAIS_DOSSIER | | 6 000 |
| 3 Dépôt guichet | janv. | CAI | TRESO_CAISSE | 20 000 | |
| | | | DEPOTS_EPARGNE | | 20 000 |
| 4 Remboursement mobile | janv. | MOB | TRESO_LIAISON_MM | 30 000 | |
| | | | CREDITS_SAINS | | 25 000 |
| | | | PRODUIT_INTERETS | | 4 500 |
| | | | PRODUIT_PENALITES | | 500 |
| 5 Ouverture (banque) | janv. | OUV | TRESO_BANQUE | 1 000 000 | |
| | | | CAPITAL | | 1 000 000 |
| 6 Retrait agent | févr. | AGT | DEPOTS_EPARGNE | 50 000 | |
| | | | TRESO_LIAISON_AGENT | | 50 000 |
| 7 Remboursement prélèvement | févr. | OD | DEPOTS_EPARGNE | 30 000 | |
| | | | CREDITS_SAINS | | 25 000 |
| | | | PRODUIT_INTERETS | | 5 000 |
| 8 Loyer virement | févr. | BQ | CHARGE_LOYERS | 100 000 | |
| | | | TRESO_BANQUE | | 100 000 |
| 9 Appro de caisse | févr. | VIR | TRESO_CAISSE | 200 000 | |
| | | | TRESO_BANQUE | | 200 000 |

## 2. Balance de janvier (ouverture = 0, H5)

| Compte | Mvt D | Mvt C | Clôture D | Clôture C |
|---|---:|---:|---:|---:|
| CAPITAL | | 1 000 000 | | 1 000 000 |
| TRESO_BANQUE | 1 000 000 | | 1 000 000 | |
| TRESO_CAISSE | 20 000 | | 20 000 | |
| TRESO_LIAISON_MM | 30 000 | | 30 000 | |
| CREDITS_SAINS | 300 000 | 25 000 | 275 000 | |
| DEPOTS_EPARGNE | 6 000 | 320 000 | | 314 000 |
| PRODUIT_FRAIS_DOSSIER | | 6 000 | | 6 000 |
| PRODUIT_INTERETS | | 4 500 | | 4 500 |
| PRODUIT_PENALITES | | 500 | | 500 |
| **Total** | **1 356 000** | **1 356 000** | **1 325 000** | **1 325 000** |

## 3. Balance de février (6 colonnes, densification H6)

| Compte | Ouv. D | Ouv. C | Mvt D | Mvt C | Clôt. D | Clôt. C |
|---|---:|---:|---:|---:|---:|---:|
| CAPITAL | | 1 000 000 | | | | 1 000 000 |
| TRESO_BANQUE | 1 000 000 | | | 300 000 | 700 000 | |
| TRESO_CAISSE | 20 000 | | 200 000 | | 220 000 | |
| TRESO_LIAISON_MM | 30 000 | | | | 30 000 | |
| TRESO_LIAISON_AGENT | | | | 50 000 | | 50 000 |
| CREDITS_SAINS | 275 000 | | | 25 000 | 250 000 | |
| DEPOTS_EPARGNE | | 314 000 | 80 000 | | | 234 000 |
| PRODUIT_FRAIS_DOSSIER | | 6 000 | | | | 6 000 |
| PRODUIT_INTERETS | | 4 500 | | 5 000 | | 9 500 |
| PRODUIT_PENALITES | | 500 | | | | 500 |
| CHARGE_LOYERS | | | 100 000 | | 100 000 | |
| **Total** | **1 325 000** | **1 325 000** | **380 000** | **380 000** | **1 300 000** | **1 300 000** |

Lignes sans mouvement en février mais présentes (H6) : CAPITAL, TRESO_LIAISON_MM, PRODUIT_FRAIS_DOSSIER, PRODUIT_PENALITES.

## 4. Compte de résultat (H9)

| Rubrique | Janv. | Févr. | Cumul fin févr. |
|---|---:|---:|---:|
| R1_PRODUITS_FINANCIERS | 5 000 | 5 000 | 10 000 |
| R2_COMMISSIONS | 6 000 | 0 | 6 000 |
| R4_CHARGES_GENERALES | 0 | 100 000 | 100 000 |
| **Résultat** | **11 000** | **−95 000** | **−84 000** |

## 5. Rapprochements (H10)

| Fin de mois | Contrôle | Gestion | Compta | Écart |
|---|---|---:|---:|---:|
| 31/01 | CREDITS | 275 000 | 275 000 | 0 |
| 31/01 | DEPOTS | 314 000 | 314 000 | 0 |
| 28/02 | CREDITS | 250 000 | 250 000 | 0 |
| 28/02 | DEPOTS | 234 000 | 234 000 | 0 |

## 6. Bilan (niveau IMF, H7 et H8)

| Rubrique | 31/01 | 28/02 |
|---|---:|---:|
| A1_CREDITS_CLIENTELE | 275 000 | 250 000 |
| A2_TRESORERIE | 1 050 000 | 950 000 |
| **Total actif** | **1 325 000** | **1 200 000** |
| P1_CAPITAUX_PROPRES (capital) | 1 000 000 | 1 000 000 |
| Résultat cumulé | 11 000 | −84 000 |
| P2_DEPOTS_CLIENTELE | 314 000 | 234 000 |
| P3_DETTES_TRESORERIE (liaison agents, solde inversé) | 0 | 50 000 |
| **Total passif + résultat** | **1 325 000** | **1 200 000** |

Contrôle H8 : sans reclassement, la trésorerie serait de 900 000 et le total de 1 150 000. Le bilan resterait équilibré, mais il compenserait une dette envers les agents. Le test doit donc vérifier que P3 = 50 000 au 28/02.
