from __future__ import annotations

import threading
from typing import Any
from pydantic import BaseModel, Field, ConfigDict

from core.domain import CadrageSynthesis, QualityScoreMatrix, utc_now


class BlackboardState(BaseModel):
    """État partagé typé pour la mémoire collective de l'équipe d'agents."""
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    project_id: str
    project_name: str = "Global"
    cadrage_synthesis: dict[str, Any] = Field(default_factory=dict)
    technical_stack: list[str] = Field(default_factory=list)
    architecture_specs: dict[str, Any] = Field(default_factory=dict)
    generated_files: dict[str, str] = Field(default_factory=dict)
    test_results: dict[str, Any] = Field(default_factory=dict)
    quality_score: dict[str, Any] = Field(default_factory=dict)
    inter_agent_logs: list[dict[str, Any]] = Field(default_factory=list)
    updated_at: str = Field(default_factory=lambda: utc_now().isoformat())


class Blackboard:
    """Tableau Noir (Shared State) gérant la mémoire partagée et éliminant la dégradation d'information."""

    def __init__(self) -> None:
        self._states: dict[str, BlackboardState] = {}
        self._lock = threading.RLock()

    def get_or_create_state(self, project_id: str, project_name: str = "Global") -> BlackboardState:
        with self._lock:
            if project_id not in self._states:
                initial_files: dict[str, str] = {}
                initial_cadrage: dict[str, Any] = {}
                try:
                    from storage.repository import checkpoints_repo, project_repo
                    chk = checkpoints_repo.get_latest_checkpoint(project_id)
                    if chk:
                        initial_files = chk.files_snapshot or {}
                        initial_cadrage = chk.state_payload or {}
                    else:
                        p = project_repo.get(project_id)
                        if p:
                            project_name = p.name
                except Exception:
                    pass

                self._states[project_id] = BlackboardState(
                    project_id=project_id,
                    project_name=project_name,
                    generated_files=initial_files,
                    cadrage_synthesis=initial_cadrage,
                )
            return self._states[project_id]

    def update_cadrage(self, project_id: str, synthesis: CadrageSynthesis) -> None:
        with self._lock:
            state = self.get_or_create_state(project_id)
            state.cadrage_synthesis = synthesis.model_dump(mode="json")
            state.technical_stack = synthesis.technical_stack
            state.updated_at = utc_now().isoformat()

    def publish_file(self, project_id: str, file_path: str, content: str) -> None:
        with self._lock:
            state = self.get_or_create_state(project_id)
            state.generated_files[file_path] = content
            state.updated_at = utc_now().isoformat()

    def publish_test_results(self, project_id: str, results: dict[str, Any]) -> None:
        with self._lock:
            state = self.get_or_create_state(project_id)
            state.test_results = results
            state.updated_at = utc_now().isoformat()

    def publish_quality_score(self, project_id: str, score: QualityScoreMatrix) -> None:
        with self._lock:
            state = self.get_or_create_state(project_id)
            state.quality_score = score.model_dump(mode="json")
            state.updated_at = utc_now().isoformat()

    def log_inter_agent_message(self, project_id: str, from_agent: str, to_agent: str, message: str) -> None:
        with self._lock:
            state = self.get_or_create_state(project_id)
            state.inter_agent_logs.append({
                "timestamp": utc_now().isoformat(),
                "from_agent": from_agent,
                "to_agent": to_agent,
                "message": message,
            })
            state.updated_at = utc_now().isoformat()

    def export_context_for_agent(self, project_id: str) -> str:
        """Génère un résumé textuel clair du Tableau Noir pour injection dans le contexte d'un agent."""
        with self._lock:
            state = self.get_or_create_state(project_id)
            lines = [
                f"### Tableau Noir du Projet '{state.project_name}'",
                f"- **Fichiers générés ({len(state.generated_files)})** : {', '.join(state.generated_files.keys()) if state.generated_files else 'Aucun pour le moment'}",
                f"- **Stack Technique** : {', '.join(state.technical_stack) if state.technical_stack else 'En cours de sélection'}",
            ]
            if state.test_results:
                lines.append(f"- **Derniers Tests** : Statut {state.test_results.get('status', 'inconnu')}")
            if state.quality_score:
                lines.append(f"- **Score Qualité** : {state.quality_score.get('total_score', 0)}/100 ({state.quality_score.get('verdict', 'N/A')})")
            return "\n".join(lines)


blackboard = Blackboard()
