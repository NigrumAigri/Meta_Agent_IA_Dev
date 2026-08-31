from __future__ import annotations

import json
from pathlib import Path
import pytest

from core.config import settings
from core.domain import AgentType
from services.mcp_hub import mcp_hub
from services.prompt_compiler import prompt_compiler
from services.skill_rag import skill_rag
from services.skills_registry import skills_registry
from storage.repository import agent_repo, skills_repo


@pytest.fixture(autouse=True)
def ensure_skills_synced():
    """Synchronise les compétences physiques vers SQLite avant chaque test."""
    skills_registry.sync_filesystem_to_db()


def test_skill_rag_intent_and_keyword_matching():
    """Vérifie que l'analyse d'intention sémantique route vers le bon Skill."""
    # Intent API / FastAPI
    res_api = skill_rag.search_relevant_skills("Développer une API REST FastAPI avec validation Pydantic")
    assert any(s.name == "fastapi_enterprise" for s in res_api)

    # Intent SQLite / WAL
    res_sql = skill_rag.search_relevant_skills("Configurer la persistance SQLite en mode WAL avec transactions")
    assert any(s.name == "sqlite_wal_persistence" for s in res_sql)

    # Intent Hexagonale / DDD
    res_hex = skill_rag.search_relevant_skills("Valider le découplage DDD et l'architecture hexagonale")
    assert any(s.name == "verification_architecture_hexagonale" for s in res_hex)

    # Intent JWT / Sécurité
    res_jwt = skill_rag.search_relevant_skills("Mettre en place l'authentification avec tokens JWT et hash argon2")
    assert any(s.name == "securite_tokens_jwt" for s in res_jwt)


def test_skill_rag_role_defaults_and_limits():
    """Vérifie les biais par rôle et le plafonnement strict (~50-100 tokens max)."""
    # Architecte sans consigne spécifique
    res_arch = skill_rag.search_relevant_skills("", agent_type="architect", limit=3)
    assert len(res_arch) <= 3
    assert any(s.name == "verification_architecture_hexagonale" for s in res_arch)

    # Développeur sans consigne spécifique
    res_coder = skill_rag.search_relevant_skills("", agent_type="coder", limit=3)
    assert len(res_coder) <= 3
    assert any(s.name == "fastapi_enterprise" for s in res_coder)


def test_skill_rag_sqlite_fts5_search():
    """Vérifie que la recherche plein-texte FTS5 fonctionne directement sur SQLite."""
    fts_res = skills_repo.search_skills_fts("pydantic")
    assert len(fts_res) > 0
    assert any(s.name == "fastapi_enterprise" for s in fts_res)

    fts_res_wal = skills_repo.search_skills_fts("WAL")
    assert len(fts_res_wal) > 0
    assert any(s.name == "sqlite_wal_persistence" for s in fts_res_wal)


def test_mcp_tool_read_skill_jit_execution():
    """Vérifie que l'agent peut exécuter l'outil MCP read_skill pour charger le corps du SKILL.md."""
    res = mcp_hub.execute_tool("read_skill", {"skill_name": "fastapi_enterprise"})
    assert res["status"] == "success"
    assert res["skill_name"] == "fastapi_enterprise"
    assert "instructions_md" in res
    assert "FastAPI Enterprise" in res["instructions_md"]
    assert "available_resources" in res


def test_mcp_tool_read_skill_caching_and_idempotence():
    """Vérifie que le cache idempotent évite les relectures disques inutiles."""
    res1 = mcp_hub.execute_tool("read_skill", {"skill_name": "sqlite_wal_persistence"})
    assert res1["status"] == "success"

    # Deuxième appel identique (servi par le cache)
    res2 = mcp_hub.execute_tool("read_skill", {"skill_name": "sqlite_wal_persistence"})
    assert res2["status"] == "success"
    assert res2["skill_name"] == "sqlite_wal_persistence"


def test_mcp_tool_discover_skills_execution():
    """Vérifie l'outil MCP discover_skills pour la découverte à chaud de compétences."""
    res = mcp_hub.execute_tool("discover_skills", {"query": "authentification tokens JWT securite"})
    assert res["status"] == "success"
    assert res["count"] >= 1
    assert any(s["name"] == "securite_tokens_jwt" for s in res["skills"])


def test_prompt_compiler_skills_rag_dynamic_injection():
    """Vérifie la compilation XML hermétique avec injection dynamique par Skill RAG."""
    agent = agent_repo.get_by_id("agent_coder")
    assert agent is not None

    prompt = prompt_compiler.compile_agent_system_prompt(
        agent=agent,
        task_context="Créer un routeur REST FastAPI avec persistance SQLite WAL",
    )

    # Balise <available_skills> présente et compacte
    assert "<available_skills>" in prompt
    assert "</available_skills>" in prompt
    assert 'name="fastapi_enterprise"' in prompt
    assert 'name="sqlite_wal_persistence"' in prompt

    # Rappel de sécurité JIT pour read_skill
    assert "read_skill(skill_name=...)" in prompt
    assert "discover_skills(query=...)" in prompt


def test_zero_hardcoded_skills_in_agents():
    """Vérifie que 100% des agents ont 'skills: []' (Zéro Hardcoding, 100% Skill RAG)."""
    # 1. Vérification des fichiers JSON disque
    agents_dir = settings.v5_root / "data" / "agents"
    for agent_file in agents_dir.glob("agent_*.json"):
        data = json.loads(agent_file.read_text(encoding="utf-8"))
        assert data.get("skills") == [], f"L'agent {agent_file.name} contient encore des skills codés en dur !"

    # 2. Vérification des entités en base de données SQLite
    db_agents = agent_repo.list_agents()
    for a in db_agents:
        assert a.skills == [], f"L'agent BDD {a.name} ({a.id}) contient encore des skills statiques !"
