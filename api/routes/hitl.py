from __future__ import annotations

from typing import Any
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from services.hitl_queue import hitl_queue
from storage.repository import project_repo, agent_repo

router = APIRouter(prefix="/api/v1/hitl", tags=["Validation Humaine (HITL)"])


class RejectRequestPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(default="Refusé par l'opérateur", min_length=3)


@router.get("/requests", response_model=list[dict[str, Any]])
@router.get("/queue", response_model=list[dict[str, Any]])
def get_pending_hitl_requests(
    limit: int = Query(1000, ge=1, le=5000),
    project_id: str | None = Query(None, description="Filtrer par projet actif"),
):
    """Récupère les demandes de validation humaine enrichies d'explications claires (FIFO)."""
    requests = hitl_queue.get_pending_requests(limit=limit, project_id=project_id)
    out = []
    for r in requests:
        d = r.model_dump(mode="json")
        # 1. Nom lisible du Projet
        if r.project_id:
            p = project_repo.get(r.project_id)
            d["project_name"] = p.name if p else "Projet Spécifique"
        else:
            d["project_name"] = "Studio Méta-Agents"

        # 2. Nom lisible de l'Agent
        if r.agent_id:
            a = agent_repo.get(r.agent_id)
            d["agent_name"] = a.name if a else (
                "Agent Développeur" if "coder" in r.agent_id else "Agent Spécialisé"
            )
        else:
            d["agent_name"] = "Méta-Agent Système"

        # 3. Explications vulgarisées : Pourquoi cette demande + Ce que cela apporte au projet
        if not d.get("plain_reason"):
            if r.request_type in ("file_write", "new_file"):
                fn = r.payload.get("filename", r.title)
                d["plain_reason"] = f"L'agent souhaite générer ou mettre à jour le fichier '{fn}'."
                d["project_impact"] = "Ajoute les fonctionnalités nécessaires et permet au code de s'exécuter sans erreur."
            elif r.request_type in ("budget_increase", "budget_exceeded"):
                budget_str = f"${r.payload.get('current_budget'):.2f}" if isinstance(r.payload.get("current_budget"), (int, float)) else str(r.payload.get("current_budget") or "configuré")
                d["plain_reason"] = f"Le plafond budgétaire alloué ({budget_str}) est atteint pour cette étape."
                d["project_impact"] = "Permet aux agents de continuer les générations de code et les tests sans bloquer votre flux de travail."
                d["is_urgent"] = True
            elif r.request_type in ("new_tool", "tool_permission"):
                tn = r.payload.get("tool_name", r.title)
                d["plain_reason"] = f"L'agent demande l'autorisation d'activer l'outil d'action '{tn}'."
                d["project_impact"] = "Donne à l'agent une nouvelle capacité concrète pour accomplir sa mission avec précision."
            elif r.request_type == "shell_command":
                cmd = r.payload.get("command", r.title)
                d["plain_reason"] = f"Exécution d'une commande système sécurisée : '{cmd}'."
                d["project_impact"] = "Installe les librairies requises ou valide les tests de robustesse."
            else:
                d["plain_reason"] = r.description or "Validation de sécurité requise avant exécution autonome."
                d["project_impact"] = "Garantit la conformité et la sécurité de l'application."

        if r.request_type in ("budget_increase", "budget_exceeded", "circuit_breaker", "security_override"):
            d["is_urgent"] = True

        out.append(d)
    return out


@router.post("/approve-all", response_model=list[dict[str, Any]])
def approve_all_hitl_requests(project_id: str | None = Query(None)):
    """Approuve toutes les demandes de validation en attente d'un coup."""
    resolved = hitl_queue.approve_all_pending(project_id=project_id)
    return [r.model_dump(mode="json") for r in resolved]


@router.post("/requests/{request_id}/approve", response_model=dict[str, Any])
@router.post("/{request_id}/approve", response_model=dict[str, Any])
def approve_hitl_request(request_id: str):
    """Approuve une demande HITL et exécute l'action associée."""
    resolved = hitl_queue.approve_request(request_id)
    if not resolved:
        raise HTTPException(status_code=404, detail="Demande introuvable.")
    return resolved.model_dump(mode="json")


@router.post("/requests/{request_id}/reject", response_model=dict[str, Any])
@router.post("/{request_id}/reject", response_model=dict[str, Any])
def reject_hitl_request(request_id: str, payload: RejectRequestPayload | None = None):
    """Rejette une demande HITL avec un motif explicite."""
    reason = payload.reason if payload else "Refusé par l'opérateur"
    resolved = hitl_queue.reject_request(request_id, reason=reason)
    if not resolved:
        raise HTTPException(status_code=404, detail="Demande introuvable.")
    return resolved.model_dump(mode="json")
