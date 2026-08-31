from __future__ import annotations

import asyncio
import pytest
from unittest.mock import patch, PropertyMock

from services.openrouter_client import OpenRouterClient, openrouter_client
from storage.repository import finops_repo


def test_openrouter_offline_deterministic_fallback():
    """Vérifie le fonctionnement hors-ligne déterministe quand aucune clé n'est fournie."""
    async def runner():
        with patch.object(OpenRouterClient, "is_configured", new_callable=PropertyMock, return_value=False):
            content, metric, finish_reason = await openrouter_client.generate_chat_completion(
                messages=[{"role": "user", "content": "Bonjour Architecte"}],
                agent_id="agent_architect",
                agent_name="Architecte & Cadrage",
                project_name="Test Inférence",
            )
            assert "Mode Local" in content
            assert finish_reason == "stop"
            assert metric.agent_id == "agent_architect"

            # Vérifier l'enregistrement dans SQLite
            ledger = finops_repo.list_all()
            assert len(ledger) > 0
            assert any(m.task_name == "Inférence" for m in ledger)

    asyncio.run(runner())


def test_openrouter_streaming_offline_and_mock():
    """Vérifie que le générateur SSE émet les chunks de contenu et termine proprement."""
    async def runner():
        # Test streaming hors-ligne
        with patch.object(OpenRouterClient, "is_configured", new_callable=PropertyMock, return_value=False):
            chunks = []
            async for chunk in openrouter_client.stream_chat_completion(
                messages=[{"role": "user", "content": "Test Stream"}]
            ):
                chunks.append(chunk)

            assert len(chunks) >= 1
            assert any("Mode Local" in c.get("delta", "") for c in chunks)
            assert any(c.get("type") == "finish" for c in chunks)

    asyncio.run(runner())
