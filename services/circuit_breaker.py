from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Coroutine

from storage.repository import finops_repo, project_repo

logger = logging.getLogger(__name__)


class BudgetExceededError(RuntimeError):
    """Exception levée lorsque le plafond budgétaire est franchi."""
    pass


class MaxIterationsExceededError(RuntimeError):
    """Exception levée lorsque le nombre maximum d'itérations d'outils est dépassé."""
    pass


class CircuitBreaker:
    """Disjoncteur Budgétaire Hybride & Gestionnaire de Retries Déterministes."""

    def check_project_budget(self, project_id: str) -> dict[str, Any]:
        """Vérifie si le projet respecte son plafond budgétaire configuré."""
        from core.config import settings
        if not settings.circuit_breaker_enabled:
            return {"status": "disabled", "usage_ratio": 0.0, "is_enabled": False}

        project = project_repo.get(project_id)
        if not project:
            return {"status": "ok", "usage_ratio": 0.0}

        metrics = [m for m in finops_repo.list_all() if m.project_id == str(project.id)]
        total_cost = sum(m.cost_usd for m in metrics)
        budget_limit = project.budget_limit_usd

        ratio = (total_cost / budget_limit) if budget_limit > 0 else 0.0

        if ratio >= 1.0:
            raise BudgetExceededError(
                f"Disjoncteur FinOps Activé : Le budget plafond de ${budget_limit:.2f} est atteint (${total_cost:.4f} dépensés). "
                f"Augmentez le budget dans les paramètres du projet pour continuer."
            )

        is_warning = ratio >= 0.8
        return {
            "status": "warning" if is_warning else "ok",
            "total_cost_usd": round(total_cost, 4),
            "budget_limit_usd": budget_limit,
            "usage_ratio": round(ratio, 4),
            "warning_message": f"Attention : 80% du budget consommé (${total_cost:.4f} / ${budget_limit:.2f})" if is_warning else None,
        }

    async def execute_with_strict_retries(
        self,
        func: Callable[..., Coroutine[Any, Any, Any]],
        *args: Any,
        max_retries: int = 3,
        backoff_base: float = 1.0,
        **kwargs: Any,
    ) -> Any:
        """Exécute une fonction asynchrone avec 3 retries stricts sur le même modèle sans bascule silencieuse."""
        last_exception: Exception | None = None

        for attempt in range(1, max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                logger.warning("Échec tentative %d/%d : %s", attempt, max_retries, e)
                if attempt < max_retries:
                    await asyncio.sleep(backoff_base * (2 ** (attempt - 1)))

        raise RuntimeError(f"Échec définitif après {max_retries} tentatives sur le modèle configuré : {str(last_exception)}")


circuit_breaker = CircuitBreaker()
