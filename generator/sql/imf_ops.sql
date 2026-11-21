-- =============================================================================
-- imf_ops.sql – Schéma de la base opérationnelle simulée (source du pipeline)
--
-- Rejoué à chaque génération : les tables sont supprimées puis recréées, et
-- rechargées dans la même transaction (rechargement complet, atomique).
-- Montants en BIGINT (XOF, entiers) ; date_maj = horodatage métier déterministe
-- qui servira de filigrane à l'ingestion incrémentale (phase 3).
-- =============================================================================

-- Suppression dans l'ordre inverse des dépendances
DROP TABLE IF EXISTS remboursements, echeancier, credits, comptes, clients, produits_credit;

-- Catalogue des produits de crédit
CREATE TABLE produits_credit (
    code_produit        VARCHAR(20)   PRIMARY KEY,
    libelle             TEXT          NOT NULL,
    taux_annuel         NUMERIC(6, 4) NOT NULL,
    taux_frais_dossier  NUMERIC(6, 4) NOT NULL,
    duree_min_mois      SMALLINT      NOT NULL,
    duree_max_mois      SMALLINT      NOT NULL,
    date_maj            TIMESTAMP     NOT NULL
);

-- Clients ; id_agence renvoie à agences.csv (hors de cette base, donc sans clé étrangère).
-- date_naissance et secteur_activite peuvent être NULL (anomalie NULL_NON_CRITIQUE).
CREATE TABLE clients (
    id_client         VARCHAR(12) PRIMARY KEY,
    id_agence         VARCHAR(8)  NOT NULL,
    prenom            TEXT        NOT NULL,
    nom               TEXT        NOT NULL,
    sexe              CHAR(1)     NOT NULL,
    date_naissance    DATE,
    secteur_activite  VARCHAR(20),
    date_adhesion     DATE        NOT NULL,
    date_maj          TIMESTAMP   NOT NULL
);

-- Comptes d'épargne et comptes courants
CREATE TABLE comptes (
    id_compte       VARCHAR(12) PRIMARY KEY,
    id_client       VARCHAR(12) NOT NULL REFERENCES clients (id_client),
    type_compte     VARCHAR(10) NOT NULL,
    date_ouverture  DATE        NOT NULL,
    statut          VARCHAR(10) NOT NULL,
    date_maj        TIMESTAMP   NOT NULL
);

-- Crédits, versés sur le compte d'épargne du client
CREATE TABLE credits (
    id_credit          VARCHAR(12)   PRIMARY KEY,
    id_client          VARCHAR(12)   NOT NULL REFERENCES clients (id_client),
    id_compte_epargne  VARCHAR(12)   NOT NULL REFERENCES comptes (id_compte),
    code_produit       VARCHAR(20)   NOT NULL REFERENCES produits_credit (code_produit),
    date_decaissement  DATE          NOT NULL,
    montant_accorde    BIGINT        NOT NULL,
    frais_dossier      BIGINT        NOT NULL,
    duree_mois         SMALLINT      NOT NULL,
    taux_annuel        NUMERIC(6, 4) NOT NULL,
    statut             VARCHAR(10)   NOT NULL,
    date_maj           TIMESTAMP     NOT NULL
);

-- Échéancier théorique (échéances postérieures au 31/12 comprises)
CREATE TABLE echeancier (
    id_credit      VARCHAR(12) NOT NULL REFERENCES credits (id_credit),
    num_echeance   SMALLINT    NOT NULL,
    date_echeance  DATE        NOT NULL,
    capital        BIGINT      NOT NULL,
    interets       BIGINT      NOT NULL,
    montant        BIGINT      NOT NULL,
    date_maj       TIMESTAMP   NOT NULL,
    PRIMARY KEY (id_credit, num_echeance)
);

-- Remboursements ; pas de contrainte CHECK : les anomalies (date antérieure au
-- décaissement, montant payé incohérent) doivent être détectées par le pipeline.
CREATE TABLE remboursements (
    id_remboursement    VARCHAR(12) PRIMARY KEY,
    id_credit           VARCHAR(12) NOT NULL REFERENCES credits (id_credit),
    date_remboursement  DATE        NOT NULL,
    montant_paye        BIGINT      NOT NULL,
    part_capital        BIGINT      NOT NULL,
    part_interets       BIGINT      NOT NULL,
    penalites           BIGINT      NOT NULL,
    canal               VARCHAR(20) NOT NULL,
    date_maj            TIMESTAMP   NOT NULL
);

-- Index sur date_maj : filigrane de l'ingestion incrémentale
CREATE INDEX ON produits_credit (date_maj);
CREATE INDEX ON clients (date_maj);
CREATE INDEX ON comptes (date_maj);
CREATE INDEX ON credits (date_maj);
CREATE INDEX ON echeancier (date_maj);
CREATE INDEX ON remboursements (date_maj);
