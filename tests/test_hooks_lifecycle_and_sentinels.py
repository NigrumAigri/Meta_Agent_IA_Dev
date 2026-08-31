from __future__ import annotations

import json
import pytest
from fastapi.testclient import TestClient

from core.domain import HookEventType, HookDefinition, RuleScope
from api.app import app
from services.hooks_engine import hooks_engine
from storage.repository import hooks_repo
from services.mcp_hub import mcp_hub


@pytest.fixture
def client():
    return TestClient(app)


def test_hooks_declarative_filesystem_sync():
    """Vérifie que data/hooks.json est chargé dynamiquement et synchronisé en SQLite."""
    synced = hooks_engine.sync_filesystem_to_db()
    assert len(synced) >= 7
    hook_names = {h.name for h in synced}
    assert any("Sécurité" in name for name in hook_names)
    assert any("AST" in name for name in hook_names)
    assert any("Budgétaire" in name or "Circuit Breaker" in name for name in hook_names)


def test_security_validator_blocks_malicious_paths():
    """Vérifie que la sentinelle de sécurité bloque les chemins suspects et autorise les chemins sains."""
    # Test bloquant : path traversal
    blocked_payload = {
        "tool_id": "file_writer_atomic",
        "arguments": {"file_path": "../../secret/.env", "content": "KEY=123"},
    }
    res_blocked = hooks_engine.trigger_event(HookEventType.PRE_TOOL_CALL, blocked_payload)
    assert res_blocked["is_blocked"] is True
    assert "formellement bloqué" in res_blocked["block_reason"]

    # Test autorisé : chemin propre dans le projet
    safe_payload = {
        "tool_id": "file_writer_atomic",
        "arguments": {"file_path": "services/user_service.py", "content": "class UserService:\n    pass\n"},
    }
    res_safe = hooks_engine.trigger_event(HookEventType.PRE_TOOL_CALL, safe_payload)
    assert res_safe["is_blocked"] is False


def test_ast_validator_detects_syntax_errors():
    """Vérifie que la sentinelle AST valide le code propre et détecte les erreurs de syntaxe."""
    # Code Python valide
    valid_payload = {
        "arguments": {"code_content": "def calculate(a: int, b: int) -> int:\n    return a + b\n"}
    }
    res_valid = hooks_engine.test_hook("hook_post_tool_ast", valid_payload)
    assert res_valid["result"]["status"] == "success"
    assert res_valid["result"]["is_valid"] is True

    # Code Python invalide (faute de syntaxe)
    invalid_payload = {
        "arguments": {"code_content": "def broken_func(:\n    return"}
    }
    res_invalid = hooks_engine.test_hook("hook_post_tool_ast", invalid_payload)
    assert res_invalid["result"]["status"] == "error"
    assert res_invalid["result"]["is_valid"] is False
    assert "Erreur de syntaxe Python" in res_invalid["result"]["error"]


def test_finops_circuit_breaker_thresholds():
    """Vérifie les paliers de sécurité FinOps (80% alerte et 100% hard stop)."""
    # 50% de consommation : autorisé
    res_nominal = hooks_engine.test_hook("hook_budget_threshold", {
        "cost_usd": 2.50,
        "budget_limit_usd": 5.00,
        "project_id": "demo_project"
    })
    assert res_nominal["result"]["status"] == "success"

    # 85% de consommation : avertissement
    res_warning = hooks_engine.test_hook("hook_budget_threshold", {
        "cost_usd": 4.25,
        "budget_limit_usd": 5.00,
        "project_id": "demo_project"
    })
    assert res_warning["result"]["status"] == "warning"
    assert "Avertissement" in res_warning["result"]["message"]

    # 105% de consommation : coupure d'urgence (hard stop)
    res_stop = hooks_engine.test_hook("hook_budget_threshold", {
        "cost_usd": 5.25,
        "budget_limit_usd": 5.00,
        "project_id": "demo_project"
    })
    assert res_stop["result"]["status"] == "blocked"
    assert res_stop["result"]["action"] == "hard_stop"


def test_hooks_audit_trail_recorded():
    """Vérifie que chaque exécution de hook est enregistrée dans le journal d'audit SQLite."""
    hooks_engine.trigger_event(HookEventType.ON_BUDGET_THRESHOLD, {
        "cost_usd": 1.0,
        "budget_limit_usd": 10.0,
        "project_id": "audit_test"
    })
    logs = hooks_repo.list_audit_logs(limit=10)
    assert len(logs) > 0
    latest = logs[0]
    assert latest.event_type == HookEventType.ON_BUDGET_THRESHOLD
    assert latest.status in ["success", "warning", "blocked"]
    assert latest.duration_ms >= 0.0


def test_mcp_hub_wires_pre_tool_security_hook():
    """Vérifie que mcp_hub.execute_tool déclenche automatiquement l'interception de sécurité."""
    res = mcp_hub.execute_tool("file_writer_atomic", {"file_path": "../../../root.key", "content": "hack"})
    assert res.get("status") == "blocked"
    assert "PRE_TOOL_CALL" in res.get("message") or "bloqué" in res.get("message")


def test_api_hooks_endpoints(client: TestClient):
    """Vérifie les routes API REST du Pilier 5."""
    # 1. GET /api/v1/pillars/hooks
    r = client.get("/api/v1/pillars/hooks")
    assert r.status_code == 200
    hooks_list = r.json()
    assert len(hooks_list) >= 7

    # 2. GET /api/v1/pillars/hooks/history
    r_hist = client.get("/api/v1/pillars/hooks/history")
    assert r_hist.status_code == 200
    assert isinstance(r_hist.json(), list)

    # 3. POST /api/v1/pillars/hooks/{id}/test
    r_test = client.post(
        "/api/v1/pillars/hooks/hook_post_tool_ast/test",
        json={"test_payload": {"arguments": {"code_content": "x = 42\n"}}},
    )
    assert r_test.status_code == 200
    data = r_test.json()
    assert data["result"]["status"] == "success"
    assert data["result"]["is_valid"] is True
