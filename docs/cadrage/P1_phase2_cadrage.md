# P1 – Phase 2 : générateur de données (cadrage, 21/11/2026)

> Complète le PRD v1.4 et le cadrage `P1_phase0_cadrage.md` v0.3 (D18 à D21 ajoutées pendant ce cadrage).
> Critère de fin : **jeux de données générés et reproductibles** (même seed → mêmes fichiers, au SHA-256 près), tests pytest au vert.

## 1. Décisions de la phase 2

| # | Décision | Pourquoi (pour l'entretien) |
|---|---|---|
| G1 | **Vérité propre d'abord, anomalies ensuite** (D21). La vérité est gardée dans `data/_verite/` (jamais ingérée) | Silver nettoyé doit retomber sur la vérité au franc près : c'est testable en phase 4 |
| G2 | **Sources** : `imf_ops` = logiciel de gestion du portefeuille (`produits_credit`, `clients`, `comptes`, `credits`, `echeancier`, `remboursements`) ; CSV = exports d'agences et de la comptabilité (`agences`, `operations`, `charges`, `ouverture`, `appro_caisse`) | Deux sources de nature différente, comme dans une vraie IMF |
| G3 | **Opérations découpées par jour** : `data/operations/date=AAAA-MM-JJ/operations.csv` ; colonne `date_maj` dans chaque table de `imf_ops` | Prépare l'incrémental de la phase 3 (fichier du jour J ; filigrane `date_maj`) |
| G4 | **Intérêts dégressifs** : annuités constantes, échéances mensuelles, montants entiers, la dernière échéance absorbe l'arrondi (D10) | Taux affiché = taux réel ; cohérent avec l'encours |
| G5 | **TEG actuariel ≤ 24 %**, frais de dossier inclus (D20), testé sur chaque crédit | Le taux d'usure s'apprécie sur le TEG |
| G6 | **PAR 30 visé au 31/12 : 5 %** (tolérance 4 à 6 % sur la configuration par défaut), atteint par des profils de remboursement | Paramètre de simulation, pas un chiffre réel |
| G7 | **Noms** : listes maison de prénoms et de noms sénégalais ; **pas de Faker** | Une seule source d'aléa (`random.Random`) ; Faker n'apporterait rien aux colonnes du modèle. Écart au PRD v1.3 signalé, reporté en v1.4 |
| G8 | **Une seule bibliothèque d'aléa, des flux nommés** : `random.Random(f"{seed}-verite")` et `random.Random(f"{seed}-anomalies")` | La vérité ne dépend pas du taux d'anomalies : on peut changer ce taux sans changer la vérité. Une graine `str` est hachée en SHA-512 par Python, donc stable d'une exécution à l'autre |
| G9 | **Identifiants non séquentiels** (tirés sans remise dans un grand espace), pour la vérité comme pour les lignes ajoutées | Une ligne ajoutée ne doit pas se reconnaître à son identifiant : silver doit la détecter par une règle, pas par un trou de numérotation |
| G10 | **Crédits** : au plus un crédit actif par produit et au plus deux crédits actifs en même temps par client ; décaissement ≥ ouverture du compte + 30 jours ; écart à `nb_credits` > 5 % → erreur explicite | Avec un seul crédit actif par client, environ 3 000 crédits pour environ 2 000 clients adhérant au fil de l'année ne tiennent pas en 12 mois. Le crédit scolaire à côté d'un crédit AGR est réaliste |
| G11 | **Approvisionnements de caisse** (D18) : en début de journée, si la caisse prévisionnelle de l'agence passe sous `seuil_caisse`, on la ramène à `plafond_caisse` (arrondi aux 100 000 XOF supérieurs). Fonds de caisse d'ouverture = `plafond_caisse` | Caisse ≥ 0 sans fonds de caisse irréaliste |
| G12 | **Capital** (D19) = besoin maximal de la banque × (1 + `marge_capital`), arrondi au million supérieur, calculé en fin de simulation | La banque reste ≥ 0 chaque jour |
| G13 | **Pénalités** : forfait de 2 % de l'échéance (capital + intérêts), arrondi au franc, si l'échéance est payée plus de 7 jours après sa date ; imputation des paiements : pénalités → intérêts → capital, échéance la plus ancienne d'abord | Règle simple, explicable et testable |
| G14 | **Dépendances** : psycopg 3 ; ni Faker, ni numpy, ni pandas dans le générateur | Dataclasses typées, mypy strict, reproductibilité indépendante de bibliothèques tierces |

## 2. Produits de crédit (paramètres de simulation)

TEG actuariel calculé sur la durée la plus courte (cas le plus défavorable), frais de dossier inclus :

| Code | Libellé | Taux nominal | Frais de dossier | Durée (mois) | Saisonnalité | TEG max |
|---|---|---:|---:|---|---|---:|
| AGR | Crédit activité génératrice de revenus | 15 % | 1,5 % | 6–12 | toute l'année | 22,33 % |
| AGRICOLE | Crédit de campagne agricole | 14 % | 1,5 % | 6–9 | mai à juillet | 21,12 % |
| SCOLAIRE | Crédit scolaire | 12 % | 1 % | 6–10 | août à octobre | 16,67 % |
| EQUIPEMENT | Crédit d'équipement | 16 % | 2 % | 12–24 | toute l'année | 21,81 % |

Contre-exemple (sert de test) : 15 % nominal + 2 % de frais sur 6 mois → TEG actuariel 24,51 %, au-dessus du plafond.

## 3. Anomalies injectées (taux par défaut : environ 1 % par type)

| Nature | Table | Où | Mode | `traitement_attendu` |
|---|---|---|---|---|
| DOUBLON_EXACT | operations | CSV | copie exacte d'une vraie ligne (même id) | DEDOUBLONNER |
| ORPHELIN_COMPTE | operations | CSV | ligne ajoutée, compte inexistant | REJETER |
| MONTANT_NEGATIF | operations | CSV | ligne ajoutée | REJETER |
| CANAL_NON_AUTORISE | charges | CSV | ligne ajoutée, canal PRELEVEMENT | REJETER |
| FORMAT_CANAL | operations | CSV | vraie ligne, canal en minuscules ou avec espaces | STANDARDISER |
| DATE_INCOHERENTE | remboursements | `imf_ops` | ligne ajoutée, date < décaissement | REJETER |
| MONTANT_PAYE_INCOHERENT | remboursements | `imf_ops` | ligne ajoutée, montant ≠ somme des parts | REJETER |
| NULL_NON_CRITIQUE | clients | `imf_ops` | vraie ligne, secteur ou date de naissance à NULL | ACCEPTER_NULL |

## 5. Ce que je relis à la fin de la phase

- Le manifeste : PAR 30, capital, nombre d'approvisionnements, caisse et banque minimales — sont-ils plausibles ?
- Un crédit tiré au hasard : échéancier, TEG, remboursements, pénalités, à la main.
- Un jour d'une agence : caisse de la veille + entrées − sorties + approvisionnement = caisse du jour.
- Le test « catalogue appliqué = vérité » : c'est la preuve que les anomalies ne cassent pas la comptabilité.
