# Commandes du projet imf-data-pipeline.
# Chaque cible documentée par « ## » apparaît dans `make help`.

.DEFAULT_GOAL := help
.PHONY: help install up down logs reset-db psql-dwh psql-ops generate generate-small \
	ingest ingest-range ingest-all reset-bronze \
	dbt-deps dbt-build test-verite airflow-up airflow-down airflow-logs airflow-reprendre test-airflow \
	lint format typecheck test test-all check

help: ## Affiche cette aide
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install: ## Installe l'environnement Python (uv sync)
	uv sync

up: ## Démarre PostgreSQL et attend qu'il soit prêt
	docker compose up -d --wait

down: ## Arrête PostgreSQL (les données sont conservées)
	docker compose down

logs: ## Suit les journaux de PostgreSQL
	docker compose logs -f postgres

reset-db: ## SUPPRIME toutes les données puis redémarre PostgreSQL (rejoue l'init)
	@echo "⚠️  ATTENTION : reset-db supprime le volume pgdata et TOUTES les données."
	docker compose down -v
	$(MAKE) up

psql-dwh: ## Ouvre psql sur l'entrepôt imf_dwh (dans le conteneur)
	docker compose exec postgres sh -c 'psql -U "$$POSTGRES_USER" -d imf_dwh'

psql-ops: ## Ouvre psql sur la base opérationnelle imf_ops (dans le conteneur)
	docker compose exec postgres sh -c 'psql -U "$$POSTGRES_USER" -d imf_ops'

generate: ## Génère data/ et recharge imf_ops (configuration par défaut)
	uv run python -m generator

generate-small: ## Génère un petit jeu (100 clients, 150 crédits) et recharge imf_ops
	uv run python -m generator --clients 100 --credits 150

ingest: ## Ingère un jour dans bronze : make ingest DATE=AAAA-MM-JJ
	@test -n "$(DATE)" || { echo "Usage : make ingest DATE=AAAA-MM-JJ"; exit 2; }
	uv run python -m ingestion --date $(DATE)

ingest-range: ## Ingère une période jour par jour : make ingest-range DU=… AU=…
	@test -n "$(DU)" -a -n "$(AU)" || { echo "Usage : make ingest-range DU=AAAA-MM-JJ AU=AAAA-MM-JJ"; exit 2; }
	uv run python -m ingestion --du $(DU) --au $(AU)

ingest-all: ## Ingère tous les jours de l'exercice (rattrapage complet)
	uv run python -m ingestion --exercice

reset-bronze: ## SUPPRIME le schéma bronze de imf_dwh puis le recrée vide
	@echo "⚠️  ATTENTION : reset-bronze supprime toutes les données du schéma bronze (imf_dwh)."
	docker compose exec -T postgres sh -c 'psql -U "$$POSTGRES_USER" -d imf_dwh -v ON_ERROR_STOP=1 \
		-c "DROP SCHEMA IF EXISTS bronze CASCADE" -c "CREATE SCHEMA bronze"'

# dbt lit le .env via uv (profiles.yml : uniquement env_var()).
DBT = uv run --env-file .env dbt
DBT_OPTIONS = --project-dir dbt --profiles-dir dbt

dbt-deps: ## Installe les packages dbt (dbt_utils)
	$(DBT) deps $(DBT_OPTIONS)

dbt-build: ## Seeds + modèles silver + tests dbt (prérequis : make ingest-all)
	@test -d dbt/dbt_packages/dbt_utils || $(MAKE) dbt-deps
	$(DBT) build $(DBT_OPTIONS)

test-verite: ## Compare chaque slv_* à data/_verite/ (prérequis : make ingest-all dbt-build)
	uv run pytest tests/test_silver_verite.py

# Airflow (phase 7) : profil « airflow » du docker-compose, secrets lus dans .env.
AIRFLOW = docker compose --profile airflow

airflow-up: ## Construit l'image et démarre Airflow (attend que tout soit healthy)
	$(AIRFLOW) up -d --build --wait

airflow-down: ## Arrête Airflow (la base de métadonnées est conservée)
	$(AIRFLOW) stop airflow-api-server airflow-scheduler airflow-dag-processor airflow-db
	$(AIRFLOW) rm -f airflow-api-server airflow-scheduler airflow-dag-processor airflow-init airflow-db

airflow-logs: ## Suit les journaux des services Airflow
	$(AIRFLOW) logs -f airflow-api-server airflow-scheduler airflow-dag-processor

airflow-reprendre: ## Reprend un jour en échec : make airflow-reprendre JOUR=AAAA-MM-JJ [ETAPE=…]
	@test -n "$(JOUR)" || { echo "Usage : make airflow-reprendre JOUR=AAAA-MM-JJ [ETAPE=ingerer]"; exit 2; }
	$(AIRFLOW) exec -T airflow-scheduler python airflow/reprendre.py $(JOUR) $(ETAPE)

test-airflow: ## Tests d'intégrité des DAG, dans le conteneur Airflow
	$(AIRFLOW) exec -T airflow-scheduler python -m pytest -q -p no:cacheprovider airflow/tests

lint: ## Vérifie le style (ruff check + ruff format --check)
	uv run ruff check .
	uv run ruff format --check .

format: ## Corrige et formate le code avec ruff
	uv run ruff check --fix .
	uv run ruff format .

typecheck: ## Vérifie les types avec mypy (strict)
	uv run mypy

test: ## Lance les tests rapides (hors tests longs « slow »)
	uv run pytest -m "not slow"

test-all: ## Lance tous les tests, tests longs compris
	uv run pytest

check: lint typecheck dbt-build test-all ## Lint + typecheck + dbt build + tous les tests
