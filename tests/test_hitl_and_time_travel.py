from __future__ import annotations

import pytest
from core.domain import HitlRequestStatus, Project
from storage.repository import mcp_repo, project_repo
from services.hitl_queue import hitl_queue
from services.time_travel import time_travel
from services.tool_maker import tool_maker


def test_hitl_queue_approval_and_rejection_flow():
    """Vérifie le cycle complet de soumission, approbation et rejet dans la file HITL."""
    # 1. Créer un outil via ToolMaker
    tool_def, hitl_req = tool_maker.synthesize_new_tool(
        tool_name="docker_container_runner",
        description="Lance un container Docker",
        category="DevOps",
        parameters_schema={"type": "object"},
        requires_hitl=True,
    )
    assert hitl_req is not None

    # 2. Vérifier présence dans les requêtes en attente
    pending = hitl_queue.get_pending_requests()
    assert any(r.id == hitl_req.id for r in pending)

    # 3. Approuver la requête
    approved = hitl_queue.approve_request(hitl_req.id)
    assert approved is not None
    assert approved.status == HitlRequestStatus.APPROVED

    # Vérifier que l'outil est devenu actif
    tools = mcp_repo.list_tools()
    active_tool = next((t for t in tools if t.id == tool_def.id), None)
    assert active_tool is not None
    assert active_tool.is_active is True

    # 4. Rejeter une requête
    req_to_reject = hitl_queue.submit_request(
        request_type="file_write",
        title="Écriture Fichier Sensible",
        description="Modification du système hôte",
        payload={"target": "/etc/hosts"},
    )
    rejected = hitl_queue.reject_request(req_to_reject.id, reason="Accès non autorisé au système hôte")
    assert rejected is not None
    assert rejected.status == HitlRequestStatus.REJECTED
    assert rejected.rejection_reason == "Accès non autorisé au système hôte"


def test_time_travel_snapshot_and_rollback():
    """Vérifie la capture atomique de checkpoint et la restauration instantanée."""
    project = Project(name="Time Travel App")
    project_repo.save(project)

    # 1. Créer un snapshot initial
    initial_files = {"src/app.py": "VERSION = '1.0.0'"}
    ckpt1 = time_travel.create_checkpoint(
        project_id=str(project.id),
        step_name="v1_stable",
        files_snapshot=initial_files,
    )
    assert ckpt1.id is not None

    # 2. Simuler une modification corrompue
    time_travel.create_checkpoint(
        project_id=str(project.id),
        step_name="v2_corrupted",
        files_snapshot={"src/app.py": "VERSION = '2.0.0_CORRUPTED'"},
    )

    # 3. Vérifier l'historique
    history = time_travel.get_history(str(project.id))
    assert len(history) >= 2

    # 4. Rollback
    restored = time_travel.rollback_to_latest(str(project.id))
    assert restored is not None
    assert restored.step_name == "v2_corrupted"
