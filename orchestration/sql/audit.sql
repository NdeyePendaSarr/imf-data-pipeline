-- =============================================================================
-- audit.sql – Journal d'exécution du pipeline (phase 7), DDL idempotent
--
-- Une ligne par tentative de chaque étape du DAG imf_quotidien, plus une ligne
-- etape = 'RUN' par exécution (statut global, écrite par la tâche teardown).
-- Table en ajout seul : aucune ligne n'est jamais modifiée ni supprimée.
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS audit;

CREATE TABLE IF NOT EXISTS audit.audit_runs (
    id_audit         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    dag_id           TEXT        NOT NULL,
    run_id           TEXT        NOT NULL,
    date_logique     DATE        NOT NULL,
    etape            TEXT        NOT NULL,
    tentative        INTEGER     NOT NULL,
    statut           TEXT        NOT NULL CHECK (statut IN (
                         'SUCCES', 'AVERTISSEMENT', 'ECHEC_CONTROLE', 'ECHEC_TECHNIQUE', 'NON_EXECUTE')),
    debut            TIMESTAMPTZ NOT NULL,
    fin              TIMESTAMPTZ NOT NULL,
    duree_s          NUMERIC(10, 3) NOT NULL,
    lignes_chargees  BIGINT,
    nb_pass          INTEGER,
    nb_warn          INTEGER,
    nb_error         INTEGER,
    nb_skip          INTEGER,
    noeuds_en_echec  TEXT[],
    noeuds_sautes    TEXT[],
    version_mapping  TEXT,
    commit_git       TEXT,
    message          TEXT
);

CREATE INDEX IF NOT EXISTS audit_runs_date_logique ON audit.audit_runs (date_logique, etape);
