# Commandes du projet imf-data-pipeline.
# Chaque cible documentée par « ## » apparaît dans `make help`.

.DEFAULT_GOAL := help
.PHONY: help install up down logs reset-db psql-dwh psql-ops generate generate-small \
	ingest ingest-range ingest-all reset-bronze lint format typecheck test test-all check

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

check: lint typecheck test-all ## Lint + typecheck + tous les tests
