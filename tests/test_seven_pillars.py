from __future__ import annotations

import pytest
from core.domain import HookEventType
from services.mcp_hub import mcp_hub
from services.skills_registry import skills_registry
from services.rules_registry import rules_registry
from services.commands_registry import commands_registry
from services.hooks_engine import hooks_engine


def test_pillar_1_mcp_hub_8_tools_and_execution():
    """Pilier 1 : Vérifie la présence des 8 outils natifs et l'exécution déterministe."""
    tools = mcp_hub.list_tools()
    assert len(tools) >= 8

    # 1. Test AST Validator
    valid_code = "def hello():\n    return 'world'\n"
    res_ast_valid = mcp_hub.execute_tool("ast_validator", {"code_content": valid_code})
    assert res_ast_valid["status"] == "success"
    assert res_ast_valid["is_valid"] is True

    invalid_code = "def bad_syntax(:\n"
    res_ast_invalid = mcp_hub.execute_tool("ast_validator", {"code_content": invalid_code})
    assert res_ast_invalid["is_valid"] is False

    # 2. Test Math Calculator (0% Hallucination)
    res_math = mcp_hub.execute_tool("math_calculator", {"expression": "(100 * 0.2) + 15"})
    assert res_math["status"] == "success"
    assert res_math["result"] == 35.0

    # 3. Test FinOps Calculator
    res_finops = mcp_hub.execute_tool(
        "finops_calculator",
        {"prompt_tokens": 1000000, "completion_tokens": 500000, "price_in_usd": 1.0, "price_out_usd": 2.0},
    )
    assert res_finops["status"] == "success"
    assert res_finops["cost_usd"] == 2.0  # (1*1.0) + (0.5*2.0) = 2.0

    # 4. Test Web Search (READ_ONLY_UNTRUSTED encapsulation)
    res_web = mcp_hub.execute_tool("web_search_and_docs", {"query": "FastAPI"})
    assert res_web["security"] == "READ_ONLY_UNTRUSTED"
    assert "<external_untrusted_data>" in res_web["results"]


def test_pillar_2_skills_registry_jit_and_yaml():
    """Pilier 2 : Vérifie les Playbooks à 2 niveaux et l'injection JIT."""
    skills = skills_registry.sync_filesystem_to_db()
    assert len(skills) >= 2  # fastapi_enterprise, sqlite_wal_persistence

    # Bloc léger au repos
    xml_block = skills_registry.get_available_skills_xml()
    assert "<available_skills>" in xml_block
    assert 'name="fastapi_enterprise"' in xml_block
    assert "<description>" in xml_block

    # Chargement complet à l'activation
    full_body = skills_registry.load_skill_body("fastapi_enterprise")
    assert full_body is not None
    assert "Playbook FastAPI Enterprise" in full_body


def test_pillar_3_rules_registry_dynamic_injection():
    """Pilier 3 : Vérifie l'injection systématique des règles sans hardcoding."""
    rules = rules_registry.sync_filesystem_to_db()
    assert len(rules) >= 4  # security_guardrails, python_pep8_standards, no_emojis, finops_limits

    xml_rules = rules_registry.get_active_rules_xml()
    assert "<rules>" in xml_rules
    assert 'name="security_guardrails"' in xml_rules
    assert 'name="no_emojis"' in xml_rules


def test_pillar_4_slash_commands_0_token_engine():
    """Pilier 4 : Vérifie les 7 commandes natives et l'exécution à zéro coût de token."""
    commands = commands_registry.list_commands()
    assert len(commands) >= 7

    assert commands_registry.is_slash_command("/cadrage") is True
    assert commands_registry.is_slash_command("Bonjour") is False

    # Enregistrer un handler de test personnalisé
    commands_registry.register_handler("custom_test_action", lambda args, context: "Custom Action OK")
    assert commands_registry._handlers["custom_test_action"](None, {}) == "Custom Action OK"

    # Test /audit natif
    exec_res = commands_registry.execute_command("/audit", context={})
    assert exec_res["handled"] is True
    assert exec_res["result"]["type"] == "quality_audit"

    # Test /budget sans argument (Bilan)
    from core.domain import Project
    from storage.repository import project_repo
    test_p = Project(name="Projet Budget Test", budget_limit_usd=10.0)
    project_repo.save(test_p)

    budget_summary_res = commands_registry.execute_command("/budget", context={"project_id": test_p.id})
    assert budget_summary_res["handled"] is True
    assert budget_summary_res["result"]["type"] == "budget_summary"
    assert budget_summary_res["result"]["budget_limit_usd"] == 10.0

    # Test /budget 35.50 (Réglage dynamique du plafond)
    budget_set_res = commands_registry.execute_command("/budget 35.50", context={"project_id": test_p.id})
    assert budget_set_res["handled"] is True
    assert budget_set_res["result"]["type"] == "budget_updated"
    assert budget_set_res["result"]["updated"] is True
    assert budget_set_res["result"]["budget_limit_usd"] == 35.50

    reloaded_p = project_repo.get(test_p.id)
    assert reloaded_p.budget_limit_usd == 35.50
    project_repo.delete(test_p.id)


def test_pillar_5_hooks_lifecycle_engine():
    """Pilier 5 : Vérifie les 5 écouteurs de cycle de vie."""
    triggered_events = []

    def on_post_tool(hook, payload):
        triggered_events.append((hook.name, payload.get("file")))
        return "validated"

    hooks_engine.register_listener(HookEventType.POST_TOOL_CALL, on_post_tool)

    res = hooks_engine.trigger_event(HookEventType.POST_TOOL_CALL, {"file": "main.py"})
    assert res["event"] == "post_tool_call"
    assert res["executed_hooks_count"] >= 1
    assert any(ev[1] == "main.py" for ev in triggered_events)
