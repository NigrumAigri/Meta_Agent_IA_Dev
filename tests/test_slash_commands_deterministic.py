from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from api.app import app
from core.domain import CommandDefinition, Project, RuleScope
from services.commands_registry import commands_registry
from storage.repository import commands_repo, project_repo


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def sample_project():
    proj = Project(name="Projet Test Slash Commands", budget_limit_usd=10.0)
    return project_repo.save(proj)


def test_commands_declarative_sync_and_catalog():
    """Vérifie que les 10 commandes officielles sont bien synchronisées depuis data/commands.json."""
    cmds = commands_registry.sync_filesystem_to_db()
    assert len(cmds) >= 10

    all_cmds = commands_repo.list_commands(active_only=False)
    cmd_map = {c.command: c for c in all_cmds}

    expected_commands = [
        "/cadrage", "/benchmarks", "/models", "/match", "/audit",
        "/rollback", "/export", "/budget", "/goal", "/clear"
    ]
    for exp in expected_commands:
        assert exp in cmd_map, f"Commande manquante : {exp}"
        c = cmd_map[exp]
        assert c.name != "", f"Nom manquant pour {exp}"
        assert c.description != "", f"Description manquante pour {exp}"
        assert c.usage != "", f"Usage manquant pour {exp}"
        assert c.category != "", f"Catégorie manquante pour {exp}"
        assert c.scope == RuleScope.GLOBAL


def test_command_cadrage_handler(sample_project):
    """Vérifie le déclenchement déterministe de /cadrage."""
    res = commands_registry.execute_command("/cadrage", context={"project_id": str(sample_project.id)})
    assert res["handled"] is True
    assert "cadrage" in res["result"]["type"]
    assert sample_project.name in res["result"]["message"]


def test_command_benchmarks_and_matching():
    """Vérifie les commandes d'évaluation et de matching de modèles."""
    res_b = commands_registry.execute_command("/benchmarks coding", context={})
    assert res_b["handled"] is True
    assert res_b["result"]["type"] == "benchmarks_card"
    assert "Sweet Spot" in res_b["result"]["message"]

    res_m = commands_registry.execute_command("/match finance", context={})
    assert res_m["handled"] is True
    assert res_m["result"]["type"] == "benchmarks_card"
    assert res_m["result"]["role"] == "finance"


def test_command_audit_quality(sample_project):
    """Vérifie le déclenchement de l'audit qualité déterministe /audit."""
    res = commands_registry.execute_command("/audit", context={"project_id": str(sample_project.id)})
    assert res["handled"] is True
    assert res["result"]["type"] == "quality_audit"
    assert "Score Global de Conformité" in res["result"]["message"]
    assert "matrix" in res["result"]


def test_command_budget_inspection_and_update(sample_project):
    """Vérifie l'inspection et la modification du plafond budgétaire via /budget."""
    pid = str(sample_project.id)
    
    # 1. Bilan simple
    res_info = commands_registry.execute_command("/budget", context={"project_id": pid})
    assert res_info["handled"] is True
    assert res_info["result"]["type"] == "budget_summary"
    assert res_info["result"]["budget_limit_usd"] == 10.0

    # 2. Mise à jour du plafond à 25.50 $
    res_up = commands_registry.execute_command("/budget 25.50", context={"project_id": pid})
    assert res_up["handled"] is True
    assert res_up["result"]["type"] == "budget_updated"
    assert res_up["result"]["updated"] is True
    assert res_up["result"]["budget_limit_usd"] == 25.50

    # Vérification en BDD
    reloaded = project_repo.get(sample_project.id)
    assert reloaded.budget_limit_usd == 25.50


def test_command_rollback_time_travel(sample_project):
    """Vérifie la tentative de rollback déterministe /rollback."""
    pid = str(sample_project.id)
    res = commands_registry.execute_command("/rollback", context={"project_id": pid})
    assert res["handled"] is True
    assert res["result"]["type"] == "time_travel_rollback"


def test_command_export_zip(sample_project):
    """Vérifie la préparation de l'archive de production /export."""
    pid = str(sample_project.id)
    res = commands_registry.execute_command("/export", context={"project_id": pid})
    assert res["handled"] is True
    assert res["result"]["type"] == "project_export_zip"
    assert res["result"]["status"] == "success"
    assert f"/api/v1/projects/{pid}/export/zip" in res["result"]["export_url"]


def test_command_goal_autonomous_mode():
    """Vérifie l'enclenchement de la boucle autonome haute intensité /goal."""
    res = commands_registry.execute_command("/goal Construire l'API REST", context={})
    assert res["handled"] is True
    assert res["result"]["type"] == "goal_mode"
    assert res["result"]["active"] is True
    assert "Construire l'API REST" in res["result"]["goal"]


def test_command_clear_thread(sample_project):
    """Vérifie la réinitialisation du fil actif /clear."""
    pid = str(sample_project.id)
    res = commands_registry.execute_command("/clear", context={"project_id": pid})
    assert res["handled"] is True
    assert res["result"]["type"] == "clear_thread"
    assert res["result"]["status"] == "cleared"


def test_unknown_command_returns_guidance():
    """Vérifie qu'une commande inconnue renvoie une aide sans faire planter le système."""
    res = commands_registry.execute_command("/inconnue_xyz", context={})
    assert res["handled"] is False
    assert "Commande inconnue" in res["message"]


def test_api_slash_command_endpoints(client, sample_project):
    """Vérifie l'API REST FastAPI pour l'exécution et la gestion des commandes."""
    # 1. GET /api/v1/pillars/commands
    r_list = client.get("/api/v1/pillars/commands")
    assert r_list.status_code == 200
    cmds = r_list.json()
    assert len(cmds) >= 10

    # 2. POST /api/v1/chat/command
    r_exec = client.post("/api/v1/chat/command", json={
        "command": "/budget 40",
        "project_id": str(sample_project.id)
    })
    assert r_exec.status_code == 200
    res = r_exec.json()
    assert res["handled"] is True
    assert res["result"]["budget_limit_usd"] == 40.0
