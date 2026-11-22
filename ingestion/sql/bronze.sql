-- =============================================================================
-- bronze.sql – Couche bronze de l'entrepôt imf_dwh (DDL idempotent)
--
-- Rejoué au début de chaque exécution de l'ingestion : CREATE ... IF NOT EXISTS
-- uniquement, aucune donnée n'est supprimée. Pour repartir de zéro :
-- make reset-bronze.
--
-- Colonnes techniques communes à toutes les tables de données :
--   _id_run     run d'ingestion (jour#n)        _source   chemin relatif du fichier
--   _num_ligne  ligne physique dans le fichier  _sha256   empreinte du fichier
--   _charge_le  horodatage du chargement (seule colonne non déterministe)
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS bronze;

-- -----------------------------------------------------------------------------
-- Fichiers CSV des agences : colonnes métier en TEXT, telles que reçues
-- (aucun dédoublonnage : les doublons exacts doivent rester visibles).
-- -----------------------------------------------------------------------------

-- Instantané : référentiel des agences
CREATE TABLE IF NOT EXISTS bronze.csv_agences (
    id_agence    TEXT,
    nom          TEXT,
    ville        TEXT,
    region       TEXT,
    type_agence  TEXT,
    _id_run      TEXT        NOT NULL,
    _source      TEXT        NOT NULL,
    _num_ligne   INTEGER     NOT NULL,
    _sha256      CHAR(64)    NOT NULL,
    _charge_le   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Instantané : capital et fonds de caisse d'ouverture
CREATE TABLE IF NOT EXISTS bronze.csv_ouverture (
    id_agence       TEXT,
    date_ouverture  TEXT,
    canal           TEXT,
    montant         TEXT,
    _id_run         TEXT        NOT NULL,
    _source         TEXT        NOT NULL,
    _num_ligne      INTEGER     NOT NULL,
    _sha256         CHAR(64)    NOT NULL,
    _charge_le      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Partition du jour : opérations des comptes (dépôts, retraits, frais de tenue)
CREATE TABLE IF NOT EXISTS bronze.csv_operations (
    id_operation    TEXT,
    id_compte       TEXT,
    id_agence       TEXT,
    date_operation  TEXT,
    type_operation  TEXT,
    canal           TEXT,
    montant         TEXT,
    _id_run         TEXT        NOT NULL,
    _source         TEXT        NOT NULL,
    _num_ligne      INTEGER     NOT NULL,
    _sha256         CHAR(64)    NOT NULL,
    _charge_le      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS csv_operations_source ON bronze.csv_operations (_source);

-- Partition du jour : charges de fonctionnement
CREATE TABLE IF NOT EXISTS bronze.csv_charges (
    id_charge    TEXT,
    id_agence    TEXT,
    date_charge  TEXT,
    categorie    TEXT,
    canal        TEXT,
    montant      TEXT,
    _id_run      TEXT        NOT NULL,
    _source      TEXT        NOT NULL,
    _num_ligne   INTEGER     NOT NULL,
    _sha256      CHAR(64)    NOT NULL,
    _charge_le   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS csv_charges_source ON bronze.csv_charges (_source);

-- Partition du jour : approvisionnements des caisses (D18)
CREATE TABLE IF NOT EXISTS bronze.csv_appro_caisse (
    id_appro    TEXT,
    id_agence   TEXT,
    date_appro  TEXT,
    montant     TEXT,
    _id_run     TEXT        NOT NULL,
    _source     TEXT        NOT NULL,
    _num_ligne  INTEGER     NOT NULL,
    _sha256     CHAR(64)    NOT NULL,
    _charge_le  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS csv_appro_caisse_source ON bronze.csv_appro_caisse (_source);

-- Instantané : catalogue des anomalies (métadonnée de test, pas une source métier)
CREATE TABLE IF NOT EXISTS bronze.meta_catalogue_anomalies (
    nature              TEXT,
    "table"             TEXT,
    id_ligne            TEXT,
    nombre              TEXT,
    traitement_attendu  TEXT,
    date_ligne          TEXT,
    _id_run             TEXT        NOT NULL,
    _source             TEXT        NOT NULL,
    _num_ligne          INTEGER     NOT NULL,
    _sha256             CHAR(64)    NOT NULL,
    _charge_le          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- -----------------------------------------------------------------------------
-- Extractions incrémentales de imf_ops : mêmes types que la source, sans clé
-- primaire ni étrangère métier. Une ligne par version : UNIQUE (clé, date_maj).
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS bronze.ops_produits_credit (
    code_produit        VARCHAR(20),
    libelle             TEXT,
    taux_annuel         NUMERIC(6, 4),
    taux_frais_dossier  NUMERIC(6, 4),
    duree_min_mois      SMALLINT,
    duree_max_mois      SMALLINT,
    date_maj            TIMESTAMP,
    _id_run             TEXT        NOT NULL,
    _source             TEXT        NOT NULL,
    _num_ligne          INTEGER     NOT NULL,
    _sha256             CHAR(64)    NOT NULL,
    _charge_le          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (code_produit, date_maj)
);

CREATE TABLE IF NOT EXISTS bronze.ops_clients (
    id_client         VARCHAR(12),
    id_agence         VARCHAR(8),
    prenom            TEXT,
    nom               TEXT,
    sexe              CHAR(1),
    date_naissance    DATE,
    secteur_activite  VARCHAR(20),
    date_adhesion     DATE,
    date_maj          TIMESTAMP,
    _id_run           TEXT        NOT NULL,
    _source           TEXT        NOT NULL,
    _num_ligne        INTEGER     NOT NULL,
    _sha256           CHAR(64)    NOT NULL,
    _charge_le        TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (id_client, date_maj)
);

CREATE TABLE IF NOT EXISTS bronze.ops_comptes (
    id_compte       VARCHAR(12),
    id_client       VARCHAR(12),
    type_compte     VARCHAR(10),
    date_ouverture  DATE,
    statut          VARCHAR(10),
    date_maj        TIMESTAMP,
    _id_run         TEXT        NOT NULL,
    _source         TEXT        NOT NULL,
    _num_ligne      INTEGER     NOT NULL,
    _sha256         CHAR(64)    NOT NULL,
    _charge_le      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (id_compte, date_maj)
);

CREATE TABLE IF NOT EXISTS bronze.ops_credits (
    id_credit          VARCHAR(12),
    id_client          VARCHAR(12),
    id_compte_epargne  VARCHAR(12),
    code_produit       VARCHAR(20),
    date_decaissement  DATE,
    montant_accorde    BIGINT,
    frais_dossier      BIGINT,
    duree_mois         SMALLINT,
    taux_annuel        NUMERIC(6, 4),
    statut             VARCHAR(10),
    date_maj           TIMESTAMP,
    _id_run            TEXT        NOT NULL,
    _source            TEXT        NOT NULL,
    _num_ligne         INTEGER     NOT NULL,
    _sha256            CHAR(64)    NOT NULL,
    _charge_le         TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (id_credit, date_maj)
);

CREATE TABLE IF NOT EXISTS bronze.ops_echeancier (
    id_credit      VARCHAR(12),
    num_echeance   SMALLINT,
    date_echeance  DATE,
    capital        BIGINT,
    interets       BIGINT,
    montant        BIGINT,
    date_maj       TIMESTAMP,
    _id_run        TEXT        NOT NULL,
    _source        TEXT        NOT NULL,
    _num_ligne     INTEGER     NOT NULL,
    _sha256        CHAR(64)    NOT NULL,
    _charge_le     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (id_credit, num_echeance, date_maj)
);

CREATE TABLE IF NOT EXISTS bronze.ops_remboursements (
    id_remboursement    VARCHAR(12),
    id_credit           VARCHAR(12),
    date_remboursement  DATE,
    montant_paye        BIGINT,
    part_capital        BIGINT,
    part_interets       BIGINT,
    penalites           BIGINT,
    canal               VARCHAR(20),
    date_maj            TIMESTAMP,
    _id_run             TEXT        NOT NULL,
    _source             TEXT        NOT NULL,
    _num_ligne          INTEGER     NOT NULL,
    _sha256             CHAR(64)    NOT NULL,
    _charge_le          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (id_remboursement, date_maj)
);

-- -----------------------------------------------------------------------------
-- Pilotage de l'ingestion
-- -----------------------------------------------------------------------------

-- Filigrane de chaque table de imf_ops : plus grand date_maj déjà extrait
CREATE TABLE IF NOT EXISTS bronze._filigranes (
    table_source  TEXT      PRIMARY KEY,
    filigrane     TIMESTAMP NOT NULL
);

-- Journal : une ligne par objet traité et par run
CREATE TABLE IF NOT EXISTS bronze._ingestions (
    id_run                TEXT        NOT NULL,
    empreinte_generation  CHAR(64)    NOT NULL,
    jour                  DATE        NOT NULL,
    source                TEXT        NOT NULL CHECK (source IN ('csv', 'imf_ops', 'meta')),
    objet                 TEXT        NOT NULL,
    chemin                TEXT,
    sha256                CHAR(64),
    nb_lignes             INTEGER     NOT NULL,
    filigrane_avant       TIMESTAMP,
    filigrane_apres       TIMESTAMP,
    statut                TEXT        NOT NULL CHECK (statut IN ('CHARGE', 'IGNORE', 'VIDE')),
    debut                 TIMESTAMPTZ NOT NULL,
    fin                   TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (id_run, objet)
);
