# Commandes du projet imf-data-pipeline.
# Chaque cible documentée par « ## » apparaît dans `make help`.

.DEFAULT_GOAL := help
.PHONY: help install up down logs reset-db psql-dwh psql-ops lint format typecheck test check

help: ## Affiche cette aide
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

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

lint: ## Vérifie le style (ruff check + ruff format --check)
	uv run ruff check .
	uv run ruff format --check .

format: ## Corrige et formate le code avec ruff
	uv run ruff check --fix .
	uv run ruff format .

typecheck: ## Vérifie les types avec mypy (strict)
	uv run mypy

test: ## Lance les tests avec pytest
	uv run pytest

check: lint typecheck test ## Lint + typecheck + tests
