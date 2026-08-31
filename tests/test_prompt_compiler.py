from __future__ import annotations

import pytest
from core.domain import AgentDefinition, AgentType
from services.prompt_compiler import prompt_compiler


def test_xml_system_prompt_compilation_with_official_tags():
    """Vérifie que les balises XML officielles sont générées et que les registres sont injectés."""
    agent = AgentDefinition(
        id="agent_coder",
        name="Agent 2 : Développeur Logiciel",
        role_description="Développement de microservices",
        agent_type=AgentType.CODER,
        model="qwen/qwen-2.5-coder-32b-instruct",
        tools=["file_writer_atomic", "ast_validator"],
        max_iter=5,
    )

    compiled_prompt = prompt_compiler.compile_agent_system_prompt(agent)

    # 1. Vérification des balises officielles
    assert "<agent_identity>" in compiled_prompt
    assert "</agent_identity>" in compiled_prompt
    assert "<mission>" in compiled_prompt
    assert "</mission>" in compiled_prompt
    assert "<assigned_tools>" in compiled_prompt
    assert "</assigned_tools>" in compiled_prompt
    assert "<available_skills>" in compiled_prompt
    assert "</available_skills>" in compiled_prompt
    assert "<rules>" in compiled_prompt
    assert "</rules>" in compiled_prompt
    assert "<output_format>" in compiled_prompt
    assert "</output_format>" in compiled_prompt

    # 2. Vérification du moindre privilège (seuls les outils cochés sont présents)
    assert "file_writer_atomic" in compiled_prompt
    assert "ast_validator" in compiled_prompt

    # 3. Vérification de l'injection des règles actives
    assert "security_guardrails" in compiled_prompt


def test_auto_prompt_enhancer():
    """Vérifie la transformation d'une consigne brute en spécification d'ingénieur senior."""
    raw = "crée une api de gestion de stock"
    enhanced = prompt_compiler.enhance_user_prompt(raw)

    assert "Spécification d'Ingénierie" in enhanced
    assert "Pydantic v2 strict" in enhanced
    assert "AST" in enhanced
