from __future__ import annotations

import asyncio
import pytest
from unittest.mock import AsyncMock, patch

from core.domain import FinOpsMetric
from services.token_continuation import token_continuation


def test_auto_continuation_on_length_finish_reason():
    """Vérifie que le middleware recolle automatiquement les morceaux si finish_reason == 'length'."""
    metric1 = FinOpsMetric(
        agent_id="agent_coder",
        agent_name="Développeur Logiciel",
        model="test-model",
        task_name="Génération Part 1",
        prompt_tokens=100,
        completion_tokens=200,
        cost_usd=0.0002,
        latency_ms=150,
    )
    metric2 = FinOpsMetric(
        agent_id="agent_coder",
        agent_name="Développeur Logiciel",
        model="test-model",
        task_name="Génération Part 2",
        prompt_tokens=150,
        completion_tokens=100,
        cost_usd=0.0001,
        latency_ms=100,
    )

    mock_responses = [
        ("def generated_part_1():\n    pass\n", metric1, "length"),
        ("def generated_part_2():\n    return True\n", metric2, "stop"),
    ]

    async def runner():
        with patch("services.token_continuation.openrouter_client.generate_chat_completion", new_callable=AsyncMock) as mock_gen:
            mock_gen.side_effect = mock_responses

            full_code, final_metric = await token_continuation.execute_with_auto_continuation(
                messages=[{"role": "user", "content": "Écris une grosse classe"}],
                model="test-model",
                agent_id="agent_coder",
                agent_name="Développeur Logiciel",
            )

            # Vérifier la concaténation fluide
            assert "generated_part_1" in full_code
            assert "generated_part_2" in full_code
            assert mock_gen.call_count == 2
            # Vérifier la consolidation de la métrique FinOps
            assert final_metric.total_tokens == 550
            assert final_metric.cost_usd == 0.0003

    asyncio.run(runner())
