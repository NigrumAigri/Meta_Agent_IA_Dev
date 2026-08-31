from __future__ import annotations

import logging
from typing import Any

from core.domain import HitlRequest, HitlRequestStatus
from storage.repository import hitl_repo, mcp_repo, project_repo

logger = logging.getLogger(__name__)


class HitlQueueManager:
    """Gestionnaire de la File d'Attente de Validation Humaine (HITL FIFO)."""

    def get_pending_requests(self, limit: int = 1000, project_id: str | None = None) -> list[HitlRequest]:
        """Retourne les requêtes en attente (FIFO)."""
        return hitl_repo.list_requests(status=HitlRequestStatus.PENDING, limit=limit, project_id=project_id)

    def submit_request(
        self,
        request_type: str,
        title: str,
        description: str,
        payload: dict[str, Any],
        project_id: str | None = None,
        agent_id: str | None = None,
        plain_reason: str = "",
        project_impact: str = "",
        is_urgent: bool = False,
    ) -> HitlRequest:
        """Soumet une nouvelle demande de validation humaine."""
        req = HitlRequest(
            project_id=project_id,
            agent_id=agent_id,
            request_type=request_type,
            title=title,
            description=description,
            payload=payload,
            plain_reason=plain_reason,
            project_impact=project_impact,
            is_urgent=is_urgent,
            status=HitlRequestStatus.PENDING,
        )
        return hitl_repo.save_request(req)

    def approve_request(self, request_id: str) -> HitlRequest | None:
        """Approuve la requête et applique l'action correspondante."""
        resolved = hitl_repo.resolve_request(request_id, status=HitlRequestStatus.APPROVED)
        if not resolved:
            return None

        # Exécuter les actions selon le type de requête
        if resolved.request_type == "new_tool":
            tool_id = resolved.payload.get("tool_id")
            if tool_id:
                tools = mcp_repo.list_tools()
                target_tool = next((t for t in tools if t.id == tool_id), None)
                if target_tool:
                    target_tool.is_active = True
                    mcp_repo.save_tool(target_tool)
                    logger.info("Outil MCP '%s' activé suite à validation HITL.", tool_id)

        elif resolved.request_type == "budget_increase":
            project_id = resolved.project_id
            new_limit = float(resolved.payload.get("new_budget_limit_usd", 20.0))
            if project_id:
                project = project_repo.get(project_id)
                if project:
                    project.budget_limit_usd = new_limit
                    project_repo.save(project)
                    logger.info("Plafond budgétaire du projet '%s' rehaussé à $%f.", project.name, new_limit)

        return resolved

    def approve_all_pending(self, project_id: str | None = None) -> list[HitlRequest]:
        """Approuve toutes les demandes en attente d'un coup."""
        pending = self.get_pending_requests(limit=100, project_id=project_id)
        approved = []
        for req in pending:
            res = self.approve_request(req.id)
            if res:
                approved.append(res)
        return approved

    def reject_request(self, request_id: str, reason: str = "Refusé par l'opérateur") -> HitlRequest | None:
        """Rejette la requête avec motif explicite."""
        return hitl_repo.resolve_request(
            request_id, status=HitlRequestStatus.REJECTED, rejection_reason=reason
        )


hitl_queue = HitlQueueManager()
