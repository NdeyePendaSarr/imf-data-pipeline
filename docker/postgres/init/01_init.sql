-- =============================================================================
-- 01_init.sql – Initialisation des bases et des schémas
--
-- ATTENTION : ce script n'est exécuté par l'image officielle PostgreSQL qu'au
-- PREMIER démarrage, lorsque le volume de données est vide. Si le volume
-- existe déjà, toute modification ici est ignorée : lancer `make reset-db`
-- (supprime toutes les données) pour le rejouer.
--
-- La base imf_dwh est créée par la variable POSTGRES_DB du docker-compose.yml.
-- =============================================================================

-- Base opérationnelle simulée : la source des données (agences, crédits, opérations)
CREATE DATABASE imf_ops;

-- Bascule sur l'entrepôt de données pour y créer les couches du modèle médaillon
\connect imf_dwh

-- Couche bronze : données brutes ingérées telles quelles depuis les sources
CREATE SCHEMA IF NOT EXISTS bronze;

-- Couche silver : données nettoyées, typées et standardisées (dbt)
CREATE SCHEMA IF NOT EXISTS silver;

-- Couche gold : schéma en étoile, écritures comptables, états financiers et KPI (dbt)
CREATE SCHEMA IF NOT EXISTS gold;
