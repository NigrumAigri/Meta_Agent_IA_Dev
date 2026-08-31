from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.app import app
from core.domain import McpToolDefinition, McpServerConfig, McpTransport
from services.mcp_hub import mcp_hub
from services.tool_rag import tool_rag
from services.docker_sandbox import docker_sandbox
from storage.repository import mcp_repo


@pytest.fixture
def client():
    return TestClient(app)


def test_tool_rag_keyword_and_intent_matching():
    """Vérifie que le Tool RAG détecte dynamiquement les bons outils selon les intentions utilisateur."""
    # 1. Requête Excel
    tools_excel = tool_rag.search_relevant_tools("Analyse ce fichier tableur excel de dépenses")
    tool_ids_excel = [t.id for t in tools_excel]
    assert "document_extractor" in tool_ids_excel

    # 2. Requête Calcul
    tools_math = tool_rag.search_relevant_tools("Calcule la TVA et le montant total")
    tool_ids_math = [t.id for t in tools_math]
    assert "math_calculator" in tool_ids_math

    # 3. Requête FinOps
    tools_finops = tool_rag.search_relevant_tools("Quel est le coût des tokens et la dépense en dollars ?")
    tool_ids_finops = [t.id for t in tools_finops]
    assert "finops_calculator" in tool_ids_finops

    # 4. Requête Modèles
    tools_models = tool_rag.search_relevant_tools("Trouve le meilleur modèle LLM selon les benchmarks")
    tool_ids_models = [t.id for t in tools_models]
    assert "search_models_catalog" in tool_ids_models


def test_tool_rag_role_default_bias():
    """Vérifie que le Tool RAG pré-charge les outils standards selon le rôle de l'agent."""
    coder_tools = tool_rag.search_relevant_tools("", agent_type="coder")
    coder_ids = [t.id for t in coder_tools]
    assert "ast_validator" in coder_ids
    assert "file_writer_atomic" in coder_ids


def test_mcp_hub_discover_tools_native():
    """Vérifie que l'outil natif discover_tools permet aux agents de s'auto-approvisionner en outils."""
    res = mcp_hub.execute_tool("discover_tools", {"query": "excel tableur", "limit": 2})
    assert res["status"] == "success"
    assert res["count"] > 0
    discovered_ids = [t["id"] for t in res["discovered_tools"]]
    assert "document_extractor" in discovered_ids


def test_mcp_hub_truncation_universal():
    """Vérifie que les retours textuels massifs sont tronqués pour protéger le contexte LLM."""
    huge_text = "A" * 15000
    truncated = mcp_hub._truncate_output(huge_text, max_chars=8000)
    assert len(truncated) < 15000
    assert "tronqué" in truncated.lower()


def test_mcp_hub_idempotence_caching():
    """Vérifie que les requêtes mathématiques et de lecture identiques sont servies depuis le cache."""
    args = {"expression": "42 * 1000 + 7"}
    res1 = mcp_hub.execute_tool("math_calculator", args)
    assert res1["status"] == "success"
    assert res1["result"] == 42007

    # Second appel servi via cache
    res2 = mcp_hub.execute_tool("math_calculator", args)
    assert res2["status"] == "success"
    assert res2["result"] == 42007


def test_project_scoped_mcp_tool_isolation():
    """Vérifie qu'un outil associé à un projet A n'est pas exposé au projet B."""
    proj_a_tool = McpToolDefinition(
        id="tool_proj_a_custom",
        name="Outil Custom Projet A",
        description="Outil privé au projet A",
        category="Projet A",
        project_id="proj_aaa",
        is_active=True,
        is_core=False,
    )
    mcp_repo.save_tool(proj_a_tool)

    # 1. Visible dans le scope du projet A
    tools_a = mcp_repo.list_tools(project_id="proj_aaa")
    assert any(t.id == "tool_proj_a_custom" for t in tools_a)

    # 2. Invisible dans le scope du projet B
    tools_b = mcp_repo.list_tools(project_id="proj_bbb")
    assert not any(t.id == "tool_proj_a_custom" for t in tools_b)

    # Nettoyage
    mcp_repo.delete_tool("tool_proj_a_custom")


def test_api_mcp_search_and_sandbox_endpoints(client):
    """Vérifie les endpoints REST pour la recherche Tool RAG et le statut de la Sandbox."""
    # 1. Recherche Tool RAG via API
    res_search = client.get("/api/v1/mcp/tools/search?q=calculatrice&limit=3")
    assert res_search.status_code == 200
    tools = res_search.json()
    assert len(tools) > 0
    assert any(t["id"] == "math_calculator" for t in tools)

    # 2. Statut Sandbox
    res_sandbox = client.get("/api/v1/mcp/sandbox/status")
    assert res_sandbox.status_code == 200
    data = res_sandbox.json()
    assert "docker_installed" in data
    assert "docker_daemon_running" in data
    assert data["isolation_level"] == "READ_ONLY_NO_NETWORK_512MB"


def test_external_mcp_server_registration_and_execution_lifecycle(client):
    """Vérifie l'enregistrement d'un serveur MCP externe, sa découverte d'outils et son exécution."""
    # 1. Enregistrement d'un serveur externe via l'API
    payload = {
        "name": "Serveur Mock Stdio",
        "transport": "stdio",
        "command_or_url": "python",
        "args": ["-c", "import sys, json; print(json.dumps({'jsonrpc': '2.0', 'id': '1', 'result': {'tools': [{'name': 'custom_stdio_echo', 'description': 'Echo custom', 'inputSchema': {}}]}}))"],
        "env": {},
    }
    res = client.post("/api/v1/mcp/servers", json=payload)
    assert res.status_code == 201
    data = res.json()
    server_id = data["server"]["id"]
    assert data["tools_discovered_count"] >= 1

    # 2. Vérification que l'outil est bien indexé et trouvable
    all_tools = mcp_hub.list_tools()
    matching_tool = next((t for t in all_tools if t.server_id == server_id), None)
    assert matching_tool is not None

    # 3. Exécution déterministe de l'outil via le hub
    exec_res = mcp_hub.execute_tool(matching_tool.id, {"text": "hello mcp"})
    assert "status" in exec_res

    # 4. Nettoyage : Suppression du serveur et de ses outils en cascade
    del_res = client.delete(f"/api/v1/mcp/servers/{server_id}")
    assert del_res.status_code == 204
