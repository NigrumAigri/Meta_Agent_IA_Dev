from __future__ import annotations

import pytest
from pydantic import ValidationError

from core.domain import (
    AgentDefinition,
    AgentType,
    FinOpsBadge,
    Message,
    MessageRole,
    Project,
    ProjectStatus,
    QualityScoreMatrix,
)


def test_strict_pydantic_forbid_extra():
    """Vérifie que les modèles Pydantic rejettent strictement tout champ non autorisé."""
    # Test sur Message
    with pytest.raises(ValidationError):
        Message(
            role=MessageRole.USER,
            content="Hello",
            unauthorized_field="interdit",  # Doit lever ValidationError
        )


def test_project_model_creation():
    project = Project(name="SaaS Automation Platform")
    assert project.status == ProjectStatus.DRAFT
    assert project.selected_finops_profile == FinOpsBadge.SWEET_SPOT
    assert project.budget_limit_usd == 10.0
    
    # Thread creation
    thread = project.get_or_create_main_thread()
    assert thread.project_id == str(project.id)
    assert len(project.threads) == 1


def test_agent_definition_types():
    agent = AgentDefinition(
        id="agent_architect",
        name="Agent 1 : Architecte",
        role_description="Architecture multi-agents",
        agent_type=AgentType.ARCHITECT,
        model="moonshotai/kimi-k3",
        temperature=0.2,
        max_tokens=4096,
        tools=["web_search_and_docs"],
    )
    assert agent.agent_type == AgentType.ARCHITECT
    assert agent.temperature == 0.2
    assert agent.is_active is True


def test_quality_score_matrix_math():
    score = QualityScoreMatrix(
        technical_health=35.0,
        robustness_security=25.0,
        functional_coverage=30.0,
        documentation=10.0,
        total_score=100.0,
        verdict="SUCCÈS",
    )
    assert score.total_score == 100.0
    assert score.verdict == "SUCCÈS"
