from __future__ import annotations

from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from api.app import app

client = TestClient(app)


def test_health_check_endpoint():
    """Vérifie le point de santé /health."""
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["database"] == "sqlite_wal"


def test_static_index_html_serving():
    """Vérifie que la racine / sert l'application SPA index.html."""
    res = client.get("/")
    assert res.status_code == 200
    assert "Meta Developer Agent v5.0.0" in res.text
    assert "lucide" in res.text


def test_projects_crud_and_zip_export_endpoints():
    """Vérifie les routes API /projects, threads, documents et export ZIP."""
    # 1. Création projet
    res = client.post(
        "/api/v1/projects",
        json={"name": "Test API Project", "budget_limit_usd": 15.0, "selected_finops_profile": "sweet_spot"},
    )
    assert res.status_code == 201
    project = res.json()
    project_id = project["id"]

    # 2. Lecture projet
    res = client.get(f"/api/v1/projects/{project_id}")
    assert res.status_code == 200
    assert res.json()["name"] == "Test API Project"

    # 3. Création thread
    res = client.post(f"/api/v1/projects/{project_id}/threads", json={"title": "Nouveau Thread"})
    assert res.status_code == 201
    thread_id = res.json()["id"]

    # 4. Upload document
    res = client.post(
        f"/api/v1/projects/{project_id}/documents",
        json={"filename": "specs.txt", "content": "Spécification API", "content_type": "text/plain"},
    )
    assert res.status_code == 201

    # 5. Export ZIP
    res = client.get(f"/api/v1/projects/{project_id}/export/zip")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/zip"
    assert len(res.content) > 0


def test_chat_message_and_command_endpoints():
    """Vérifie le tour de chat Inception et l'exécution d'une slash command."""
    # Créer projet pour le chat
    res_p = client.post("/api/v1/projects", json={"name": "Chat Project", "budget_limit_usd": 10.0})
    p_id = res_p.json()["id"]

    # Envoi message chat
    res_chat = client.post(
        "/api/v1/chat/message",
        json={"project_id": p_id, "message": "Propose une architecture backend pour un CRM."},
    )
    assert res_chat.status_code == 200
    data = res_chat.json()
    assert data["status"] == "success"
    assert "reply" in data

    # Exécution Slash command
    res_cmd = client.post("/api/v1/chat/command", json={"command": "/budget", "project_id": p_id})
    assert res_cmd.status_code == 200
    assert res_cmd.json()["handled"] is True


def test_copilot_system_endpoints():
    """Vérifie les routes de discussion étanches avec le Copilote Système."""
    res_chat = client.post("/api/v1/copilot/chat", json={"message": "Quel est l'état du système ?"})
    assert res_chat.status_code == 200
    assert "reply" in res_chat.json()

    res_msgs = client.get("/api/v1/copilot/messages")
    assert res_msgs.status_code == 200
    assert len(res_msgs.json()) >= 2  # 1 user + 1 assistant


def test_agents_and_topology_endpoints():
    """Vérifie la liste des 5 agents, la mise à jour PATCH/PUT et le basculement de topologie."""
    res_agents = client.get("/api/v1/agents")
    assert res_agents.status_code == 200
    agents = res_agents.json()
    assert len(agents) >= 5

    # Test PATCH mise à jour d'un agent avec rôle, goal et backstory
    res_patch = client.patch(
        "/api/v1/agents/agent_architect",
        json={
            "role": "Lead Tech & Architecte Cloud Senior",
            "goal": "Concevoir des architectures découplées 100% conformes",
            "backstory": "15 ans d'expérience en Clean Architecture",
            "timeout_seconds": 120.0,
            "budget_limit_usd": 8.0,
        },
    )
    assert res_patch.status_code == 200
    data = res_patch.json()
    assert data["role"] == "Lead Tech & Architecte Cloud Senior"
    assert data["budget_limit_usd"] == 8.0

    # Switch topology
    res_topo = client.post("/api/v1/agents/topology", json={"topology": "consensus_debate"})
    assert res_topo.status_code == 200
    assert res_topo.json()["topology"] == "consensus_debate"

    # Test PATCH position
    res_pos = client.patch(
        "/api/v1/agents/agent_architect/position",
        json={"canvas_x": 120.0, "canvas_y": 140.0},
    )
    assert res_pos.status_code == 200
    assert res_pos.json()["canvas_x"] == 120.0
    assert res_pos.json()["canvas_y"] == 140.0

    # Test GET /api/v1/agents/links
    res_links = client.get("/api/v1/agents/links")
    assert res_links.status_code == 200
    assert isinstance(res_links.json(), list)

    # Test POST /api/v1/agents/links/template
    res_tmpl = client.post("/api/v1/agents/links/template", json={"template_name": "hierarchical"})
    assert res_tmpl.status_code == 200
    links = res_tmpl.json()
    assert len(links) == 5
    assert any(l["link_type"] == "supervision" for l in links)

    # Test POST /api/v1/agents/links (nouveau câble interactif)
    res_new_link = client.post(
        "/api/v1/agents/links",
        json={
            "source_agent_id": "agent_coder",
            "target_agent_id": "agent_copilot",
            "link_type": "data_flow",
            "label": "Code ➔ Copilot Direct",
        },
    )
    assert res_new_link.status_code == 201
    link_id = res_new_link.json()["id"]

    # Test DELETE /api/v1/agents/links/{id}
    res_del_link = client.delete(f"/api/v1/agents/links/{link_id}")
    assert res_del_link.status_code == 204


def test_finops_and_benchmarks_endpoints():
    """Vérifie les routes FinOps, 19 benchmarks et matching 1-clic."""
    res_ledger = client.get("/api/v1/finops/ledger")
    assert res_ledger.status_code == 200

    res_bench = client.get("/api/v1/finops/benchmarks")
    assert res_bench.status_code == 200
    assert len(res_bench.json()) >= 6

    res_match = client.get("/api/v1/finops/models/match?role=coding")
    assert res_match.status_code == 200
    assert "sweet_spot" in res_match.json()

    # Test catalogue complet OpenRouter
    res_models = client.get("/api/v1/finops/models")
    assert res_models.status_code == 200
    models_list = res_models.json()
    assert len(models_list) >= 10
    first_model = models_list[0]
    assert "id" in first_model
    assert "pin" in first_model
    assert "pout" in first_model
    assert "reasoning" in first_model


def test_mcp_and_pillars_endpoints():
    """Vérifie les routes MCP natifs et les 7 piliers (Skills, Rules, Hooks, Commands)."""
    # 1. MCP Tools
    res_tools = client.get("/api/v1/mcp/tools")
    assert res_tools.status_code == 200
    assert len(res_tools.json()) >= 8

    # 2. Exécution outil
    res_exec = client.post(
        "/api/v1/mcp/tools/math_calculator/execute",
        json={"arguments": {"expression": "25 * 4"}},
    )
    assert res_exec.status_code == 200
    assert res_exec.json()["result"] == 100

    # 3. Skills & Rules
    res_skills = client.get("/api/v1/pillars/skills")
    assert res_skills.status_code == 200

    res_rules = client.get("/api/v1/pillars/rules")
    assert res_rules.status_code == 200

    # 4. HITL Requests
    res_hitl = client.get("/api/v1/hitl/requests")
    assert res_hitl.status_code == 200


def test_config_endpoints():
    """Vérifie la lecture et la mise à jour de la configuration."""
    res = client.get("/api/v1/config")
    assert res.status_code == 200
    data = res.json()
    assert "llm_discovery_model" in data

    # Update config
    res_up = client.put("/api/v1/config", json={"llm_discovery_model": "moonshotai/kimi-k3"})
    assert res_up.status_code == 200
    assert res_up.json()["status"] == "success"


def test_proposals_and_scoped_agents_endpoints():
    """Vérifie le cloisonnement des agents par projet et les propositions proactives d'actions."""
    # 1. Studio agents (les 5 Méta-Agents maîtres)
    res_studio = client.get("/api/v1/agents?project_id=studio")
    assert res_studio.status_code == 200
    studio_agents = res_studio.json()
    assert len(studio_agents) == 6
    assert all(a["is_core_meta_agent"] for a in studio_agents)

    # 2. Création d'un agent spécifique à un projet
    from uuid import uuid4
    test_pid = f"proj_test_scope_{uuid4().hex[:8]}"
    ag_id = f"ag_csv_{uuid4().hex[:6]}"
    res_create = client.post(
        "/api/v1/agents",
        json={
            "id": ag_id,
            "name": "Agent Parser CSV Dédié",
            "project_id": test_pid,
            "role_description": "Parser haute précision de balances comptables",
            "model": "moonshotai/kimi-k3",
        },
    )
    assert res_create.status_code == 201
    created = res_create.json()
    assert created["project_id"] == test_pid

    # 3. Filtrage étanche du projet
    res_proj_agents = client.get(f"/api/v1/agents?project_id={test_pid}")
    assert res_proj_agents.status_code == 200
    proj_agents = res_proj_agents.json()
    assert len(proj_agents) == 1
    assert proj_agents[0]["id"] == ag_id

    # 4. Création d'une proposition proactive
    res_prop = client.post(
        "/api/v1/proposals",
        json={
            "project_id": test_pid,
            "proposal_type": "agent",
            "title": "Ajout de l'Agent Security Audit",
            "description": "Pour analyser les injections SQL dans les requêtes CSV",
            "benefit": "+100% de conformité de sécurité",
            "payload": {
                "id": "agent_sec_audit",
                "name": "Agent Security Audit",
                "model": "moonshotai/kimi-k3",
                "connect_to_agent_id": "agent_test_csv_parser",
            },
        },
    )
    assert res_prop.status_code == 201
    prop_id = res_prop.json()["id"]

    # 5. Acceptation de la proposition en 1 clic
    res_accept = client.post(f"/api/v1/proposals/{prop_id}/accept")
    assert res_accept.status_code == 200
    assert res_accept.json()["status"] == "applied"

    # 6. Vérifier que le nouvel agent et son câble sont créés sur le projet
    res_updated_proj = client.get(f"/api/v1/agents?project_id={test_pid}")
    assert len(res_updated_proj.json()) == 2

    # 7. FAIL-03 : Test création et acceptation d'une proposition de type RULE
    res_prop_rule = client.post(
        "/api/v1/proposals",
        json={
            "project_id": test_pid,
            "proposal_type": "rule",
            "title": "Strict Type Safety Rule",
            "description": "Exiger Pydantic v2 sur tous les DTOs",
            "benefit": "Zéro bug de type à l'exécution",
            "payload": {
                "name": "strict_type_safety",
                "category": "Architecture",
                "content": "Toujours typer strictement les modèles avec Pydantic v2.",
            },
        },
    )
    assert res_prop_rule.status_code == 201
    prop_rule_id = res_prop_rule.json()["id"]

    res_accept_rule = client.post(f"/api/v1/proposals/{prop_rule_id}/accept")
    assert res_accept_rule.status_code == 200
    assert res_accept_rule.json()["status"] == "applied"
    assert "rule" in res_accept_rule.json()
    assert res_accept_rule.json()["rule"]["name"] == "strict_type_safety"


def test_finops_summary_and_csv_export():
    """Vérifie le point de synthèse FinOps multi-projets /summary et l'export CSV /export/csv."""
    res_summary = client.get("/api/v1/finops/summary")
    assert res_summary.status_code == 200
    data = res_summary.json()
    assert "total_cost_usd" in data
    assert "total_tokens" in data
    assert "projects_breakdown" in data
    assert "agents_breakdown" in data
    assert isinstance(data["projects_breakdown"], list)
    assert isinstance(data["agents_breakdown"], list)

    res_csv = client.get("/api/v1/finops/export/csv")
    assert res_csv.status_code == 200
    assert "text/csv" in res_csv.headers["content-type"]
    assert "ID Transaction,Horodatage,Projet,Agent,Modele LLM" in res_csv.text


def test_agent_links_crud_and_patch():
    """Vérifie la création, modification (type et label) et suppression d'une liaison sur le Canvas."""
    # 1. Création de deux agents
    res_a1 = client.post("/api/v1/agents", json={"id": "agent_test_src", "name": "Architecte Source", "role": "Architecte"})
    assert res_a1.status_code == 201
    a1_id = res_a1.json()["id"]

    res_a2 = client.post("/api/v1/agents", json={"id": "agent_test_tgt", "name": "Développeur Cible", "role": "Développeur"})
    assert res_a2.status_code == 201
    a2_id = res_a2.json()["id"]

    # 2. Création de liaison
    res_link = client.post(
        "/api/v1/agents/links",
        json={
            "source_agent_id": a1_id,
            "target_agent_id": a2_id,
            "link_type": "direct",
            "label": "Flux Initial"
        }
    )
    assert res_link.status_code == 201
    link = res_link.json()
    link_id = link["id"]
    assert link["link_type"] == "direct"
    assert link["label"] == "Flux Initial"

    # 3. Modification du type de hiérarchie (ex: débat) et du label
    res_patch = client.patch(
        f"/api/v1/agents/links/{link_id}",
        json={
            "link_type": "debate",
            "label": "Boucle Débat Contradictoire"
        }
    )
    assert res_patch.status_code == 200
    updated_link = res_patch.json()
    assert updated_link["link_type"] == "debate"
    assert updated_link["label"] == "Boucle Débat Contradictoire"

    # 4. Vérification de la persistance en base
    res_list = client.get("/api/v1/agents/links/all")
    assert res_list.status_code == 200
    found = next((l for l in res_list.json() if l["id"] == link_id), None)
    assert found is not None
    assert found["link_type"] == "debate"
    assert found["label"] == "Boucle Débat Contradictoire"

    # 5. Suppression de la liaison
    res_del = client.delete(f"/api/v1/agents/links/{link_id}")
    assert res_del.status_code == 204


def test_system_config_security_guardrails():
    """Vérifie la lecture et la mise à jour des 4 garde-fous de sécurité système via l'API."""
    # 1. Lecture de la configuration actuelle
    res_get = client.get("/api/v1/config")
    assert res_get.status_code == 200
    cfg = res_get.json()
    assert "ast_validation_enabled" in cfg
    assert "hitl_validation_enabled" in cfg
    assert "circuit_breaker_enabled" in cfg
    assert "prompt_caching_enabled" in cfg

    # 2. Mise à jour des 4 règles de sécurité
    res_patch = client.patch(
        "/api/v1/config",
        json={
            "ast_validation_enabled": True,
            "hitl_validation_enabled": True,
            "circuit_breaker_enabled": False,
            "prompt_caching_enabled": True,
        }
    )
    assert res_patch.status_code == 200
    data = res_patch.json()
    assert data["status"] == "success"
    assert data["config"]["ast_validation_enabled"] is True
    assert data["config"]["hitl_validation_enabled"] is True
    assert data["config"]["circuit_breaker_enabled"] is False
    assert data["config"]["prompt_caching_enabled"] is True

    # 3. Rétablissement du circuit breaker à True
    res_reset = client.patch(
        "/api/v1/config",
        json={
            "circuit_breaker_enabled": True,
        }
    )
    assert res_reset.status_code == 200
    assert res_reset.json()["config"]["circuit_breaker_enabled"] is True


def test_config_test_connection_endpoint():
    """Vérifie le point d'accès de test de connectivité API OpenRouter."""
    # Test avec clé invalide/vide
    res_invalid = client.post("/api/v1/config/test-connection", json={"api_key": "invalid_short"})
    assert res_invalid.status_code == 200
    data_inv = res_invalid.json()
    assert data_inv["is_connected"] is False
    assert data_inv["status"] == "error"

    # Test avec pas de clé
    res_empty = client.post("/api/v1/config/test-connection", json={"api_key": ""})
    assert res_empty.status_code == 200


def test_project_multi_threads_hierarchy_and_custom_target_path():
    """Vérifie la création d'un projet avec target_path personnalisé et le cycle de vie des multi-threads."""
    custom_path = "c:/Users/ofakl/Desktop/IA/TestWorkspace/MultiThreadApp"
    res_p = client.post(
        "/api/v1/projects",
        json={
            "name": "Multi Thread Workspace",
            "budget_limit_usd": 15.0,
            "target_path": custom_path,
        },
    )
    assert res_p.status_code == 201
    p_data = res_p.json()
    p_id = p_data["id"]
    expected_path = str(Path(custom_path).resolve())
    assert p_data["target_path"] == expected_path

    # 1. Lister les threads initiaux (au moins 1 thread principal créé automatiquement)
    res_threads = client.get(f"/api/v1/projects/{p_id}/threads")
    assert res_threads.status_code == 200
    threads = res_threads.json()
    assert len(threads) >= 1
    main_t_id = threads[0]["id"]

    # 2. Créer 2 sous-threads dédiés (anti-inflation de tokens)
    res_t1 = client.post(
        f"/api/v1/projects/{p_id}/threads",
        json={"title": "Analyse Document RAG"},
    )
    assert res_t1.status_code == 201
    t1_id = res_t1.json()["id"]

    res_t2 = client.post(
        f"/api/v1/projects/{p_id}/threads",
        json={"title": "Mermaid Schema & Architecture"},
    )
    assert res_t2.status_code == 201
    t2_id = res_t2.json()["id"]

    # 3. Mettre à jour (PATCH) : épingler t2 et renommer
    res_patch = client.patch(
        f"/api/v1/projects/{p_id}/threads/{t2_id}",
        json={"is_pinned": True, "title": "Mermaid Schema V2"},
    )
    assert res_patch.status_code == 200
    assert res_patch.json()["is_pinned"] is True
    assert res_patch.json()["title"] == "Mermaid Schema V2"

    # 4. Envoyer un message dans le thread t1
    res_chat = client.post(
        "/api/v1/chat/message",
        json={
            "project_id": p_id,
            "thread_id": t1_id,
            "message": "Analyse les documents comptables.",
        },
    )
    assert res_chat.status_code == 200

    # 5. Vérifier que les messages sont bien isolés dans t1
    res_msgs_t1 = client.get(f"/api/v1/projects/{p_id}/threads/{t1_id}/messages")
    assert res_msgs_t1.status_code == 200
    assert len(res_msgs_t1.json()) >= 1

    # 6. Supprimer le thread t2
    res_del = client.delete(f"/api/v1/projects/{p_id}/threads/{t2_id}")
    assert res_del.status_code == 200
    assert res_del.json()["status"] == "deleted"

    # Vérifier que t2 n'est plus dans la liste
    res_threads_after = client.get(f"/api/v1/projects/{p_id}/threads")
    remaining_ids = [t["id"] for t in res_threads_after.json()]
    assert t2_id not in remaining_ids
    assert t1_id in remaining_ids


def test_browse_folder_endpoint():
    """Vérifie que le point d'accès /api/v1/projects/browse-folder répond avec un schéma JSON conforme."""
    res = client.post("/api/v1/projects/browse-folder")
    assert res.status_code == 200
    data = res.json()
    assert "status" in data
    assert "path" in data


