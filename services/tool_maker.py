from __future__ import annotations

import logging
from typing import Any

from core.domain import HitlRequest, HitlRequestStatus, McpToolDefinition
from storage.repository import hitl_repo, mcp_repo

logger = logging.getLogger(__name__)


class ToolMakerEngine:
    """Moteur de Conception Autonome d'Outils (Tool-Maker) supervisé par HITL."""

    def synthesize_new_tool(
        self,
        tool_name: str,
        description: str,
        category: str,
        parameters_schema: dict[str, Any],
        requires_hitl: bool = True,
        project_id: str | None = None,
    ) -> tuple[McpToolDefinition, HitlRequest | None]:
        """Génère un nouvel outil MCP et déclenche une demande de validation humaine si sensible."""
        clean_id = tool_name.lower().replace(" ", "_").replace("-", "_")
        from core.config import settings
        effective_hitl = requires_hitl and settings.hitl_validation_enabled

        tool_def = McpToolDefinition(
            id=clean_id,
            name=tool_name,
            description=description,
            category=category,
            parameters_schema=parameters_schema,
            is_active=not effective_hitl,  # Actif immédiatement si HITL désactivé
            is_core=False,
        )
        mcp_repo.save_tool(tool_def)

        hitl_req = None
        if effective_hitl:
            hitl_req = HitlRequest(
                project_id=project_id,
                agent_id="agent_quality_judge",
                request_type="new_tool",
                title=f"Nouvel Outil MCP : {tool_name}",
                description=f"Le Contrôleur Qualité propose d'activer l'outil '{tool_name}' ({category}) : {description}",
                payload={
                    "tool_id": tool_def.id,
                    "parameters_schema": parameters_schema,
                },
                status=HitlRequestStatus.PENDING,
            )
            hitl_repo.save_request(hitl_req)

        return tool_def, hitl_req


tool_maker = ToolMakerEngine()
