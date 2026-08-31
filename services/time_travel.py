from __future__ import annotations

import logging
from typing import Any

from core.domain import CheckpointData
from storage.repository import checkpoints_repo
from services.blackboard import blackboard
from services.mcp_hub import mcp_hub

logger = logging.getLogger(__name__)


class TimeTravelEngine:
    """Moteur de Snapshots & Restauration Instantanée (Time Travel)."""

    def create_checkpoint(
        self,
        project_id: str,
        step_name: str,
        state_payload: dict[str, Any] | None = None,
        files_snapshot: dict[str, str] | None = None,
    ) -> CheckpointData:
        """Capture un instantané atomique du projet (état + fichiers)."""
        current_state = blackboard.get_or_create_state(project_id)
        payload = state_payload or current_state.cadrage_synthesis
        files = files_snapshot or current_state.generated_files

        checkpoint = CheckpointData(
            project_id=project_id,
            step_name=step_name,
            state_payload=payload,
            files_snapshot=files,
        )
        return checkpoints_repo.save_checkpoint(checkpoint)

    def rollback_to_latest(self, project_id: str) -> CheckpointData | None:
        """Restaure instantanément le projet à son dernier checkpoint stable."""
        latest = checkpoints_repo.get_latest_checkpoint(project_id)
        if not latest:
            logger.warning("Aucun checkpoint disponible pour le projet %s.", project_id)
            return None

        # 1. Restaurer dans le Tableau Noir
        state = blackboard.get_or_create_state(project_id)
        state.generated_files = dict(latest.files_snapshot)
        state.cadrage_synthesis = dict(latest.state_payload)

        # 2. Restaurer physiquement les fichiers sur disque via écriture atomique
        for fpath, content in latest.files_snapshot.items():
            mcp_hub.execute_tool("file_writer_atomic", {"file_path": fpath, "content": content})

        logger.info("Projet %s restauré avec succès au checkpoint '%s'.", project_id, latest.step_name)
        return latest

    def get_history(self, project_id: str) -> list[CheckpointData]:
        """Retourne l'historique chronologique des checkpoints du projet."""
        return checkpoints_repo.list_checkpoints(project_id)


time_travel = TimeTravelEngine()
