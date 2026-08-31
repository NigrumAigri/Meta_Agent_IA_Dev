from __future__ import annotations

import asyncio
import pytest

from core.domain import FinOpsMetric, Project
from storage.repository import finops_repo, project_repo
from services.circuit_breaker import BudgetExceededError, circuit_breaker


def test_circuit_breaker_budget_limits():
    """Vérifie le disjoncteur budgétaire à 80% (warning) et 100% (coupure hard)."""
    project = Project(name="Budget Test App", budget_limit_usd=1.0)
    project_repo.save(project)

    # 1. Budget normal (< 80%)
    res_ok = circuit_breaker.check_project_budget(str(project.id))
    assert res_ok["status"] == "ok"

    # 2. Seuil d'alerte (80%)
    m_warn = FinOpsMetric(
        project_id=str(project.id),
        agent_id="agent_coder",
        agent_name="Développeur",
        model="qwen",
        task_name="Dev",
        cost_usd=0.85,
    )
    finops_repo.record_inference(m_warn)

    res_warn = circuit_breaker.check_project_budget(str(project.id))
    assert res_warn["status"] == "warning"
    assert "80%" in res_warn["warning_message"]

    # 3. Coupure Circuit Breaker (>= 100%)
    m_stop = FinOpsMetric(
        project_id=str(project.id),
        agent_id="agent_coder",
        agent_name="Développeur",
        model="qwen",
        task_name="Dev",
        cost_usd=0.20,  # Total = 1.05 > 1.0
    )
    finops_repo.record_inference(m_stop)

    with pytest.raises(BudgetExceededError) as exc_info:
        circuit_breaker.check_project_budget(str(project.id))
    assert "Disjoncteur FinOps Activé" in str(exc_info.value)


def test_circuit_breaker_strict_3_retries():
    """Vérifie que le gestionnaire exécute 3 retries sur le même modèle avant d'abandonner."""
    attempts = 0

    async def flaky_call():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise ConnectionError("Timeout temporaire")
        return "success"

    async def runner():
        res = await circuit_breaker.execute_with_strict_retries(flaky_call, max_retries=3, backoff_base=0.01)
        assert res == "success"
        assert attempts == 3

        # Test échec définitif après 3 tentatives
        async def always_fail():
            raise ValueError("Erreur fatale modèle")

        with pytest.raises(RuntimeError) as exc_info:
            await circuit_breaker.execute_with_strict_retries(always_fail, max_retries=3, backoff_base=0.01)
        assert "3 tentatives" in str(exc_info.value)

    asyncio.run(runner())
