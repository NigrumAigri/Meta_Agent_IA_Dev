from __future__ import annotations

import pytest
from core.domain import HitlRequestStatus
from services.lessons_engine import lessons_engine
from services.tool_maker import tool_maker


def test_lessons_engine_recording_and_rule_conversion():
    """Vérifie l'enregistrement d'une leçon apprise et sa conversion en règle modulaire."""
    lesson = lessons_engine.record_lesson(
        topic="SQLite Concurrency Locks",
        problem_statement="Erreur database locked lors d'écritures simultanées",
        solution_applied="Activation de PRAGMA journal_mode = WAL et busy_timeout",
        prevention_rule="Toujours configurer SQLite en mode WAL pour les architectures multi-agents.",
    )
    assert lesson.topic == "SQLite Concurrency Locks"

    # Recherche par mot-clé
    found = lessons_engine.find_relevant_lessons("concurrency")
    assert len(found) > 0

    # Conversion en règle
    converted = lessons_engine.convert_lesson_to_rule(lesson.id)
    assert converted is True

    # Vérification du prompt context
    ctx = lessons_engine.get_lessons_prompt_context("sqlite")
    assert "<lessons_learned>" in ctx
    assert "PRAGMA journal_mode = WAL" in ctx


def test_tool_maker_synthesis_and_hitl_gating():
    """Vérifie la synthèse d'un nouvel outil MCP supervisé par une requête HITL."""
    tool_def, hitl_req = tool_maker.synthesize_new_tool(
        tool_name="github_repo_cloner",
        description="Clone un dépôt Git externe dans le sandbox local",
        category="DevOps",
        parameters_schema={"type": "object", "properties": {"repo_url": {"type": "string"}}},
        requires_hitl=True,
    )

    assert tool_def.id == "github_repo_cloner"
    assert tool_def.is_active is False  # Doit être inactif tant que non approuvé
    assert hitl_req is not None
    assert hitl_req.request_type == "new_tool"
    assert hitl_req.status == HitlRequestStatus.PENDING
