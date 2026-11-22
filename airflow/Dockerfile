# Image Airflow du pipeline (phase 7) : Airflow 3.3.2 (dernier patch de la branche 3.3,
# vérifié sur PyPI et Docker Hub le 22/11/2026), Python 3.12.
# Deux environnements séparés :
#   - celui d'Airflow (image officielle), sans dbt ni dépendances du projet ;
#   - le venv du projet, /opt/pipeline-venv, construit par uv depuis uv.lock (dépendances du
#     projet + groupe dbt), sans Airflow.
# Les tâches appellent explicitement /opt/pipeline-venv/bin/... : pas de conflit de dépendances.
FROM apache/airflow:3.3.2-python3.12

# uv, à la même version que le poste de développement.
COPY --from=ghcr.io/astral-sh/uv:0.13.9 /uv /usr/local/bin/uv

USER root
# Interpréteur de base de l'image (sans les paquets d'Airflow, installés à part dans
# /home/airflow/.local) : le venv du projet part d'un Python 3.12 vierge.
ENV UV_PROJECT_ENVIRONMENT=/opt/pipeline-venv \
    UV_PYTHON=/usr/python/bin/python3.12 \
    UV_PYTHON_DOWNLOADS=never \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1
WORKDIR /opt/pipeline-build
COPY pyproject.toml uv.lock .python-version ./
# Projet non packagé : seules les dépendances sont installées (main + groupe dbt, pas le groupe dev).
RUN uv sync --frozen --no-default-groups --group dbt --no-install-project \
    && chown -R airflow:0 /opt/pipeline-venv \
    && rm -rf /opt/pipeline-build

USER airflow
# pytest dans l'environnement Airflow, pour les tests d'intégrité du DAG (make test-airflow).
RUN pip install --no-cache-dir "pytest==9.2.0"

# Contrôles de séparation, à la construction : dbt dans le venv projet et pas dans Airflow ;
# Airflow dans son environnement et pas dans le venv projet.
RUN /opt/pipeline-venv/bin/dbt --version \
    && /opt/pipeline-venv/bin/python -c "import psycopg, dotenv" \
    && ! /opt/pipeline-venv/bin/python -c "import airflow" 2>/dev/null \
    && ! python -c "import dbt" 2>/dev/null \
    && python -c "import airflow; print('Airflow', airflow.__version__)"

WORKDIR /opt/pipeline
