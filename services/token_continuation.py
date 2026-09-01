from __future__ import annotations

import logging
from core.domain import FinOpsMetric
from services.openrouter_client import openrouter_client

logger = logging.getLogger(__name__)


class TokenContinuationMiddleware:
    """Middleware universel anti-coupure de tokens (finish_reason == 'length')."""

    def __init__(self, max_continuations: int = 5) -> None:
        self.max_continuations = max_continuations

    async def execute_with_auto_continuation(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        reasoning_effort: str | None = None,
        agent_id: str = "agent_coder",
        agent_name: str = "Développeur Logiciel",
        project_id: str | None = None,
        project_name: str = "Global",
        task_name: str = "Génération",
    ) -> tuple[str, FinOpsMetric]:
        """Génère la réponse et recolle automatiquement les morceaux si finish_reason == 'length'."""
        current_messages = list(messages)
        full_content = ""
        total_prompt_tokens = 0
        total_completion_tokens = 0
        total_reasoning_tokens = 0
        total_cost_usd = 0.0
        total_latency_ms = 0

        continuation_count = 0
        last_finish_reason = "length"

        while last_finish_reason == "length" and continuation_count < self.max_continuations:
            content, metric, finish_reason = await openrouter_client.generate_chat_completion(
                messages=current_messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                reasoning_effort=reasoning_effort,
                agent_id=agent_id,
                agent_name=agent_name,
                project_id=project_id,
                project_name=project_name,
                task_name=f"{task_name} (Partie {continuation_count + 1})",
            )

            full_content += content
            total_prompt_tokens += metric.prompt_tokens
            total_completion_tokens += metric.completion_tokens
            total_reasoning_tokens += metric.reasoning_tokens
            total_cost_usd += metric.cost_usd
            total_latency_ms += metric.latency_ms
            last_finish_reason = finish_reason

            if finish_reason == "length":
                continuation_count += 1
                logger.info("Signal finish_reason == 'length' détecté. Auto-continuation #%d...", continuation_count)
                # Ajouter la réponse partielle de l'assistant et le prompt de reprise
                current_messages.append({"role": "assistant", "content": content})
                current_messages.append({
                    "role": "user",
                    "content": "Continue ta génération exactement là où tu t'es arrêté sans répéter le début.",
                })
            else:
                break

        consolidated_metric = FinOpsMetric(
            agent_id=agent_id,
            agent_name=agent_name,
            project_id=project_id,
            project_name=project_name,
            model=model or "default",
            task_name=task_name,
            prompt_tokens=total_prompt_tokens,
            completion_tokens=total_completion_tokens,
            reasoning_tokens=total_reasoning_tokens,
            total_tokens=total_prompt_tokens + total_completion_tokens,
            cost_usd=round(total_cost_usd, 6),
            latency_ms=total_latency_ms,
            ttft_ms=int(total_latency_ms * 0.2),
            status="success",
        )

        return full_content, consolidated_metric


token_continuation = TokenContinuationMiddleware()
