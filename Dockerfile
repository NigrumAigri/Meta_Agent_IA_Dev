# ==============================================================================
# Dockerfile Multi-Stage Multi-Arch : Meta Developer Agent v5.0.0 Enterprise
# Compatible : Windows, macOS (Intel & Apple Silicon M1/M2/M3/M4 ARM64), Linux
# ==============================================================================

# ------------------------------------------------------------------------------
# Étape 1 : Builder (Installation & compilation des dépendances via Poetry)
# ------------------------------------------------------------------------------
FROM python:3.13-slim AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    POETRY_VERSION=1.8.3 \
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

ENV PATH="$POETRY_HOME/bin:$PATH"
RUN curl -sSL https://install.python-poetry.org | python3 -

WORKDIR /app

COPY pyproject.toml ./
RUN poetry install --only main --no-root --no-directory

# ------------------------------------------------------------------------------
# Étape 2 : Runner Final (Image de production ultra-légère et sécurisée)
# ------------------------------------------------------------------------------
FROM python:3.13-slim AS runner

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH" \
    PORT=8000

# Dépendances système minimales pour l'exécution & le healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# Création d'un utilisateur non-root sans privilèges administratifs (Sécurité Absolue)
RUN groupadd -g 1000 appgroup && \
    useradd -u 1000 -g appgroup -s /bin/bash -m appuser

WORKDIR /app

# Copie de l'environnement virtuel pré-compilé depuis le builder
COPY --from=builder --chown=appuser:appgroup /app/.venv /app/.venv

# Copie de l'intégralité du code applicatif
COPY --chown=appuser:appgroup . .

# Création des dossiers de persistance avec permissions pour appuser
RUN mkdir -p /app/data /app/output_projects /app/knowledge_base && \
    chown -R appuser:appgroup /app/data /app/output_projects /app/knowledge_base

# Bascule sur l'utilisateur sécurisé
USER appuser

EXPOSE 8000

# Healthcheck natif pour vérifier la réactivité du serveur
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT}/api/v1/projects || exit 1

CMD ["python", "run.py"]
