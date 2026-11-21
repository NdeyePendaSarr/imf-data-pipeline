# Relecture d'un plan de comptes simplifié d'IMF – points à vérifier

**Contexte.** Je construis un projet de portfolio en data : le pipeline de données d'une institution de microfinance **fictive**, qui va de données de gestion générées jusqu'à une balance, un compte de résultat et un bilan simplifiés. Ce n'est pas un outil de production et il ne sert à aucun reporting BCEAO. Je veux toutefois que les écritures soient défendables devant un professionnel. Le plan de comptes et le mapping sont joints (`plan_comptes.csv`, `mapping_comptable.csv`).

**Textes de référence que j'ai identifiés** (à confirmer, ou à compléter s'ils ont été remplacés) :
- Instruction BCEAO n° 025-02-2009 instituant le Référentiel comptable spécifique des SFD de l'UMOA (RCSFD) ;
- Instruction n° 026-02-2009, sur la mise en œuvre du plan de comptes ;
- Instruction n° 021-12-2010, sur la version allégée du référentiel.

**Ce que je vous demande** : une réponse courte à chaque question. « Oui », « non » ou un numéro de compte suffisent.

## A. Textes applicables

| # | Question |
|---|---|
| A1 | Ces trois instructions sont-elles toujours en vigueur en 2026, ou ont-elles été révisées ? |
| A2 | Une IMF d'environ 2 000 clients et 3 000 crédits relèverait-elle de la version allégée ? Si oui, quels comptes ou états la version allégée change-t-elle ? |
| A3 | Où se trouvent les modèles officiels du bilan et du compte de résultat d'un SFD ? |

## B. Numéros de comptes RCSFD (colonne `compte_sfd`, vide aujourd'hui)

Pour chaque ligne : le compte RCSFD à utiliser, au niveau de détail que vous jugez pertinent.

| # | Code interne | Libellé | Compte RCSFD ? |
|---|---|---|---|
| B1 | CAPITAL | Capital ou dotation initiale (SA fictive) | |
| B2 | TRESO_BANQUE | Compte courant chez une banque correspondante | |
| B3 | TRESO_CAISSE | Caisse des agences | |
| B4 | TRESO_LIAISON_MM | Liaison avec l'opérateur mobile money | |
| B5 | TRESO_LIAISON_AGENT | Liaison avec les agents de collecte | |
| B6 | CREDITS_SAINS | Crédits à la clientèle, encours sain | |
| B7 | DEPOTS_EPARGNE | Dépôts de la clientèle (épargne non rémunérée) | |
| B8 | PRODUIT_INTERETS | Intérêts sur crédits | |
| B9 | PRODUIT_PENALITES | Pénalités de retard | |
| B10 | PRODUIT_FRAIS_DOSSIER | Frais de dossier | |
| B11 | PRODUIT_FRAIS_TENUE | Frais de tenue de compte | |
| B12 | CHARGE_* | Personnel, loyers, télécommunications et logiciel, fournitures, commissions versées à l'opérateur et aux agents | |

## C. Règles de comptabilisation

| # | Mon hypothèse simplificatrice | Question |
|---|---|---|
| C1 | Les intérêts sont constatés **à l'encaissement** | Le RCSFD est en comptabilité d'engagement : comment traite-t-il les intérêts courus et les intérêts échus non payés ? Je veux décrire correctement l'écart dans les limites du projet |
| C2 | Les frais de dossier sont un produit **en une fois**, au décaissement | Faut-il les étaler sur la durée du crédit ? |
| C3 | Les pénalités de retard sont un produit financier | Est-ce la bonne catégorie de produit ? |
| C4 | Le décaissement se fait par virement sur le compte d'épargne du client (débit crédits / crédit dépôts) | Cette écriture est-elle correcte, ou passe-t-on par un compte d'attente ? |
| C5 | Un remboursement par prélèvement débite le compte d'épargne | Même question |
| C6 | Les comptes de liaison (mobile money, agents) ne sont pas compensés dans le projet | Avec quelle périodicité se règlent-ils en pratique ? |
| C7 | Le résultat est calculé, sans écriture de clôture | Acceptable pour une présentation simplifiée ? |

## D. Créances en souffrance et provisions (hors du premier périmètre, prévues ensuite)

| # | Question |
|---|---|
| D1 | Quel texte fixe le classement des crédits en souffrance d'un SFD, et à partir de combien de jours de retard ? |
| D2 | Quels taux de dépréciation par tranche d'ancienneté ? |
| D3 | Quels comptes utilise-t-on pour le reclassement, la dépréciation, la dotation et la reprise ? |

## E. Indicateurs

| # | Question |
|---|---|
| E1 | Je calcule le PAR 30 : l'encours des crédits ayant plus de 30 jours de retard, divisé par l'encours total. Ce calcul est-il conforme à l'usage ? Les crédits restructurés doivent-ils être inclus ? |
| E2 | Quel ratio réglementaire BCEAO sur la qualité du portefeuille faudrait-il afficher à côté ? |
| E3 | Taux de remboursement = montants remboursés / montants échus : quelle définition utilise-t-on en pratique ? |

## F. Correspondance avec le SYSCOHADA général (colonne `compte_syscohada_equiv`)

Une correspondance indicative vers le SYSCOHADA révisé est proposée dans le plan de comptes. Pour les crédits, les dépôts et les comptes de liaison, je l'ai marquée « approximative ».

| # | Question |
|---|---|
| F1 | Ces correspondances vous paraissent-elles défendables ? |
| F2 | Faut-il plutôt indiquer qu'il n'existe pas d'équivalent pour certains comptes ? |
| F3 | Le RCSFD contient-il une table de passage vers le SYSCOHADA (je n'ai repéré qu'une table de passage vers le Plan comptable bancaire) ? |

Merci pour votre temps.
