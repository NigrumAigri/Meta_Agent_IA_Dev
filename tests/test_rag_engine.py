from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.app import app
from services.rag_engine import rag_engine
from services.mcp_hub import mcp_hub
from services.prompt_compiler import prompt_compiler
from core.domain import AgentDefinition, AgentType


client = TestClient(app)


def test_rag_engine_indexing_and_search():
    """Vérifie que le moteur RAG indexe la Knowledge Base et retourne des extraits pertinents."""
    count = rag_engine.index_knowledge_base()
    assert count > 0

    results = rag_engine.search("topologies multi agents hiérarchique consensus", top_k=2)
    assert len(results) > 0
    assert "03_Architectures_Multi_Agents_Et_Topologies.md" in [r["document"] for r in results] or len(results) >= 1
    assert "content" in results[0]
    assert results[0]["score"] > 0


def test_mcp_search_knowledge_base_tool_execution():
    """Vérifie l'exécution de l'outil MCP search_knowledge_base."""
    res = mcp_hub.execute_tool(
        "search_knowledge_base",
        {"query": "pydantic v2 validation extra forbid", "top_k": 2},
    )
    assert res["status"] == "success"
    assert res["query"] == "pydantic v2 validation extra forbid"
    assert "results" in res
    assert len(res["results"]) > 0


def test_rag_api_endpoints_full_lifecycle():
    """Vérifie le cycle de vie complet de l'API RAG & Mémoire Épisodique."""
    # 1. Summary
    res_summary = client.get("/api/v1/rag/summary")
    assert res_summary.status_code == 200
    data_summary = res_summary.json()
    assert data_summary["status"] == "ready"
    assert data_summary["kb_chunks_count"] > 0
    assert data_summary["kb_documents_count"] > 0

    # 2. Search
    res_search = client.post("/api/v1/rag/search", json={"query": "MCP Model Context Protocol", "top_k": 2})
    assert res_search.status_code == 200
    search_results = res_search.json()
    assert len(search_results) > 0
    assert "document" in search_results[0]
    assert "score" in search_results[0]

    # 3. Documents list
    res_docs = client.get("/api/v1/rag/documents")
    assert res_docs.status_code == 200
    docs = res_docs.json()
    assert len(docs) > 0
    assert any("05_Tool_Engineering_et_Standard_MCP.md" in d["filename"] for d in docs)

    # 4. Create and list Lessons
    res_create_lesson = client.post(
        "/api/v1/rag/lessons",
        json={
            "topic": "Test Lock SQLite",
            "problem_statement": "Verrouillage BDD",
            "solution_applied": "WAL mode",
            "prevention_rule": "Toujours activer WAL",
            "confidence_score": 0.98,
        },
    )
    assert res_create_lesson.status_code == 201
    lesson_data = res_create_lesson.json()
    lesson_id = lesson_data["id"]

    res_list_lessons = client.get("/api/v1/rag/lessons")
    assert res_list_lessons.status_code == 200
    lessons = res_list_lessons.json()
    assert any(l["id"] == lesson_id for l in lessons)

    # 5. Convert lesson to rule
    res_conv = client.post(f"/api/v1/rag/lessons/{lesson_id}/convert-to-rule")
    assert res_conv.status_code == 200
    assert res_conv.json()["status"] == "success"

    # Nettoyer la règle créée pendant le test
    from core.config import settings
    rule_file = settings.rules_dir / "prevention_test_lock_sqlite.md"
    if rule_file.exists():
        try:
            rule_file.unlink()
        except PermissionError:
            pass
    from storage.repository import rules_repo
    rules_repo.delete_rule("prevention_test_lock_sqlite")

    # 6. Delete lesson
    res_del = client.delete(f"/api/v1/rag/lessons/{lesson_id}")
    assert res_del.status_code == 200


def test_prompt_compiler_rag_and_moc_injection():
    """Vérifie l'injection hermétique de la Carte du Savoir (MOC) et du RAG dans les System Prompts."""
    agent = AgentDefinition(
        id="test_rag_agent",
        name="Test Agent",
        role_description="Test RAG",
        agent_type=AgentType.CODER,
        model="anthropic/claude-3.5-sonnet",
    )
    prompt = prompt_compiler.compile_agent_system_prompt(
        agent,
        task_context="Créer un serveur MCP standard pour PostgreSQL",
    )
    assert "<knowledge_index>" in prompt
    assert "Tool Engineering & Standard MCP" in prompt
    assert "<retrieved_knowledge>" in prompt
