# P1 – Phase 6 : notes (lot A)

## Les 243 remboursements sans intérêts : ordre d'imputation du générateur

**Ordre réel.** Le générateur impute chaque paiement échéance par échéance, de la plus ancienne à la
plus récente, et dans chaque échéance dans l'ordre **pénalités → intérêts → capital**
(`EtatCredit.payer`, `generator/simulation.py`). La pénalité (2 % de l'échéance, capital + intérêts,
arrondie au franc) est constatée quand un paiement atteint l'échéance plus de 7 jours après sa date ;
elle est alors imputée en premier. C'est l'ordre d'usage : le générateur n'a pas d'anomalie ici.

**Origine des 243 lignes.** Ce sont toutes des **soldes d'échéance payées en deux fois** (profil
« retard ponctuel », paiement partiel de 30 à 70 % puis solde 1 à 10 jours plus tard). L'acompte paie
d'abord les intérêts, puis une partie du capital ; le solde ne trouve plus que du capital (et la
pénalité si elle est constatée à ce moment), d'où `part_interets = 0`. Vérification sur silver :
les 243 ont un paiement antérieur sur le même crédit ; 61 portent une pénalité (solde payé plus de
7 jours après l'échéance alors que l'acompte était dans le délai de grâce).

**Exemple 1 — sans pénalité.** Crédit `CRD4024447`, échéance 1 du 19/04/2025 : capital 109 695,
intérêts 39 067, total 148 762 XOF.

| Paiement | Date | Montant payé | Pénalités | Intérêts | Capital |
|---|---|---:|---:|---:|---:|
| RMB16941948 (acompte) | 20/04/2025 | 55 042 | 0 | 39 067 | 15 975 |
| RMB10041487 (solde) | 25/04/2025 | 93 720 | 0 | **0** | 93 720 |

L'acompte couvre tous les intérêts (39 067) puis 15 975 de capital ; le solde paie le capital restant,
109 695 − 15 975 = 93 720. Total payé : 55 042 + 93 720 = 148 762 = l'échéance.

**Exemple 2 — avec pénalité.** Crédit `CRD3873739`, échéance 3 du 04/11/2025 : capital 51 616,
intérêts 2 633, total 54 249 XOF ; pénalité possible 2 % × 54 249 = 1 085 XOF.

| Paiement | Date | Montant payé | Pénalités | Intérêts | Capital |
|---|---|---:|---:|---:|---:|
| RMB74053589 (acompte, J+3) | 07/11/2025 | 34 177 | 0 | 2 633 | 31 544 |
| RMB12236637 (solde, J+8) | 12/11/2025 | 21 157 | 1 085 | **0** | 20 072 |

L'acompte arrive 3 jours après l'échéance (délai de grâce : pas de pénalité) et couvre les intérêts
puis 31 544 de capital. Le solde arrive 8 jours après : la pénalité de 1 085 est constatée et imputée
en premier, puis le capital restant, 51 616 − 31 544 = 20 072. Total : 34 177 + 21 157 = 55 334 =
54 249 + 1 085.

**Conséquence pour les marts.** Aucune correction : le compte PRODUIT_INTERETS reçoit bien tous les
intérêts (11 441 lignes, 107 814 953 XOF au lot B), et la couverture FIFO de `fct_echeances` (capital +
intérêts, pénalités exclues) est indépendante de la ventilation entre acompte et solde.
