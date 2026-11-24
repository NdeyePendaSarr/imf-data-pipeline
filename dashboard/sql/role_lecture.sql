-- Rôle de lecture pour Power BI (phase 8, K3) : SELECT seulement, sur gold et audit.
-- Idempotent : se rejoue sans erreur (make powerbi-role). À lancer avec le rôle qui exécute
-- dbt et l'orchestration (POSTGRES_USER), propriétaire des tables reconstruites à chaque build.
-- Mot de passe : variable d'environnement POWERBI_PASSWORD, lue par \getenv (jamais en argument).

SET client_min_messages = warning;

\getenv mot_de_passe POWERBI_PASSWORD
\if :{?mot_de_passe}
\else
  DO $$ BEGIN RAISE EXCEPTION 'POWERBI_PASSWORD absent : renseigne-le dans .env'; END $$;
\endif

SELECT current_user AS proprietaire \gset

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'powerbi_lecteur') THEN
    CREATE ROLE powerbi_lecteur LOGIN;
  END IF;
END $$;

ALTER ROLE powerbi_lecteur WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION
  PASSWORD :'mot_de_passe';
-- Ceinture et bretelles : toute transaction de ce rôle est en lecture seule.
ALTER ROLE powerbi_lecteur SET default_transaction_read_only = on;

GRANT CONNECT ON DATABASE imf_dwh TO powerbi_lecteur;

-- audit est créé par l'orchestration à la première écriture ; le créer ici permet de donner
-- les droits avant le premier run (même propriétaire, même instruction que orchestration/sql/audit.sql).
CREATE SCHEMA IF NOT EXISTS audit;

GRANT USAGE ON SCHEMA gold, audit TO powerbi_lecteur;
GRANT SELECT ON ALL TABLES IN SCHEMA gold, audit TO powerbi_lecteur;

-- dbt reconstruit les tables gold (DROP / CREATE) : un GRANT sur table sauterait au build
-- suivant. Les privilèges par défaut du propriétaire les redonnent à chaque création.
ALTER DEFAULT PRIVILEGES FOR ROLE :"proprietaire" IN SCHEMA gold, audit
  GRANT SELECT ON TABLES TO powerbi_lecteur;

\echo 'powerbi_lecteur : SELECT sur gold et audit (privilèges par défaut de' :proprietaire ')'
