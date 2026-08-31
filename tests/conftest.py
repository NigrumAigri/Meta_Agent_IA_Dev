from __future__ import annotations

import sys
import tempfile
import shutil
from pathlib import Path
import pytest

import os

# 1. Isoler immédiatement le chemin de DB et le dossier output_dir avant tout import applicatif
_TEMP_TEST_DIR = tempfile.mkdtemp(prefix="meta_agent_test_")
_TEST_DB_PATH = Path(_TEMP_TEST_DIR) / "test_meta_agent.db"
_TEST_OUTPUT_DIR = Path(_TEMP_TEST_DIR) / "output_projects"
_TEST_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

os.environ["META_DATA_DIR"] = str(_TEMP_TEST_DIR)
os.environ["META_OUTPUT_DIR"] = str(_TEST_OUTPUT_DIR)
os.environ["META_TEST_MODE"] = "1"

# Ajouter Meta_Agent_Dev_V5 au sys.path
V5_DIR = Path(__file__).resolve().parents[1]
if str(V5_DIR) not in sys.path:
    sys.path.insert(0, str(V5_DIR))

from core.config import settings
from storage.sqlite_db import db, _LOCAL_STORAGE

# Redirection immédiate
_ORIG_DB_PATH = settings.db_path
_ORIG_OUTPUT_DIR = settings.output_dir
settings.db_path = _TEST_DB_PATH
settings.output_dir = _TEST_OUTPUT_DIR
db.db_path = _TEST_DB_PATH


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Isole complètement la base de données pour la suite de tests."""
    settings.db_path = _TEST_DB_PATH
    db.db_path = _TEST_DB_PATH
    if hasattr(_LOCAL_STORAGE, "connection"):
        try:
            if _LOCAL_STORAGE.connection:
                _LOCAL_STORAGE.connection.close()
        except Exception:
            pass
        _LOCAL_STORAGE.connection = None

    db.init_schema()

    # Initialisation des semences dans la base de test isolée
    from storage.repository import (
        agent_repo,
        agent_links_repo,
        openrouter_models_repo,
    )
    from services.mcp_hub import mcp_hub
    from services.commands_registry import commands_registry
    from services.hooks_engine import hooks_engine
    from services.benchmarks_client import benchmarks_client
    from services.rules_registry import rules_registry

    agent_repo._seed_default_meta_agents()
    agent_links_repo.ensure_seeded()
    mcp_hub._seed_core_tools()
    commands_registry._seed_native_commands()
    hooks_engine._seed_default_hooks()
    rules_registry.sync_filesystem_to_db()
    benchmarks_client._seed_cache()
    openrouter_models_repo.ensure_seeded()

    yield

    # Nettoyage après la session de test
    if hasattr(_LOCAL_STORAGE, "connection"):
        try:
            if _LOCAL_STORAGE.connection:
                _LOCAL_STORAGE.connection.close()
        except Exception:
            pass
        _LOCAL_STORAGE.connection = None

    settings.db_path = _ORIG_DB_PATH
    settings.output_dir = _ORIG_OUTPUT_DIR
    db.db_path = _ORIG_DB_PATH
    shutil.rmtree(_TEMP_TEST_DIR, ignore_errors=True)


@pytest.fixture(autouse=True)
def ensure_db_schema():
    """Garantit l'intégrité du schéma SQLite avant chaque test."""
    db.init_schema()
    yield
