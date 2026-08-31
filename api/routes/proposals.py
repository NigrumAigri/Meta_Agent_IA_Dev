from __future__ import annotations

from typing import Any
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from core.domain import (
    ActionProposal,
    AgentDefinition,
    AgentLink,
    AgentType,
    LinkType,
    ProposalStatus,
    ProposalType,
    RuleDefinition,
    RuleScope,
    TopologyMode,
)
from storage.repository import (
    agent_links_repo,
    agent_repo,
    proposals_repo,
    rules_repo,
)
from services.orchestrator import orchestrator
from services.rules_registry import rules_registry

router = APIRouter(prefix="/api/v1/proposals", tags=["Propositions Proactives"])


class CreateProposalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: str | None = None
    proposal_type: ProposalType
    title: str = Field(min_length=3, max_length=120)
    description: str = Field(min_length=5, max_length=500)
    benefit: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)


@router.get("", response_model=list[dict[str, Any]])
def list_proposals(
    project_id: str | None = None,
    status: ProposalStatus | None = None,
):
    """Liste les propositions et recommandations proactives de l'IA."""
    proposals = proposals_repo.list_by_project(
        project_id=project_id,
        status=status.value if status else None,
    )
    return [p.model_dump(mode="json") for p in proposals]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=dict[str, Any])
def create_proposal(payload: CreateProposalRequest):
    """Crée une nouvelle recommandation proactive émise par l'IA."""
    proposal = ActionProposal(
        project_id=payload.project_id,
        proposal_type=payload.proposal_type,
        title=payload.title,
        description=payload.description,
        benefit=payload.benefit,
        payload=payload.payload,
        status=ProposalStatus.PENDING,
    )
    saved = proposals_repo.create(proposal)
    return saved.model_dump(mode="json")


@router.get("/{proposal_id}", response_model=dict[str, Any])
def get_proposal(proposal_id: str):
    """Récupère le détail d'une proposition."""
    proposal = proposals_repo.get(proposal_id)
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposition introuvable.")
    return proposal.model_dump(mode="json")


@router.post("/{proposal_id}/accept", response_model=dict[str, Any])
def accept_proposal(proposal_id: str):
    """Applique immédiatement la recommandation en 1 clic (agent, outil, règle, topologie)."""
    proposal = proposals_repo.get(proposal_id)
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposition introuvable.")

    applied_result: dict[str, Any] = {"status": "applied", "type": proposal.proposal_type.value}
    payload = proposal.payload

    # 1. Application d'un nouvel Agent
    if proposal.proposal_type == ProposalType.AGENT:
        agent_id = payload.get("id") or f"agent_{proposal.id[:8]}"
        existing = agent_repo.get(agent_id)
        if existing:
            from uuid import uuid4
            agent_id = f"{agent_id}_{str(uuid4())[:4]}"

        new_agent = AgentDefinition(
            id=agent_id,
            name=payload.get("name", "Nouvel Agent"),
            project_id=proposal.project_id,
            role_description=payload.get("role_description", ""),
            role=payload.get("role", ""),
            goal=payload.get("goal", ""),
            backstory=payload.get("backstory", ""),
            agent_type=AgentType(payload.get("agent_type", "custom")),
            model=payload.get("model", "moonshotai/kimi-k3"),
            temperature=float(payload.get("temperature", 0.2)),
            max_tokens=int(payload.get("max_tokens", 4096)),
            budget_limit_usd=float(payload.get("budget_limit_usd", 5.0)),
            system_prompt=payload.get("system_prompt", ""),
            tools=list(payload.get("tools", [])),
            canvas_x=float(payload.get("canvas_x", 480.0)),
            canvas_y=float(payload.get("canvas_y", 260.0)),
            icon=payload.get("icon", "bot"),
            is_active=True,
            is_core_meta_agent=False,
        )
        saved_agent = agent_repo.save(new_agent)
        applied_result["agent"] = saved_agent.model_dump(mode="json")

        # Câblage automatique si spécifié dans le payload
        link_target = payload.get("connect_to_agent_id")
        if link_target and agent_repo.get(link_target):
            link = AgentLink(
                source_agent_id=saved_agent.id,
                target_agent_id=link_target,
                project_id=proposal.project_id,
                link_type=LinkType(payload.get("link_type", "direct")),
                label=payload.get("link_label", f"{saved_agent.name} ➔ {link_target}"),
                is_active=True,
            )
            agent_links_repo.create(link)

    # 2. Application d'une Règle Permanente
    elif proposal.proposal_type == ProposalType.RULE:
        rule_name = payload.get("name", proposal.title).lower().replace(" ", "_")
        category = payload.get("category", "Architecture & Standards")
        content = payload.get("content", proposal.description)
        scope = RuleScope.LOCAL if proposal.project_id else RuleScope.GLOBAL
        saved_rule = rules_registry.create_rule(
            name=rule_name,
            category=category,
            content=content,
            scope=scope,
            project_id=proposal.project_id,
        )
        applied_result["rule"] = saved_rule.model_dump(mode="json")

    # 3. Application d'une Topologie
    elif proposal.proposal_type == ProposalType.TOPOLOGY:
        topo_val = payload.get("topology", "sequential")
        orchestrator.set_topology(TopologyMode(topo_val))
        applied_result["topology"] = topo_val

    updated = proposals_repo.update_status(proposal_id, ProposalStatus.ACCEPTED)
    applied_result["proposal"] = updated.model_dump(mode="json") if updated else None
    return applied_result


@router.post("/{proposal_id}/reject", response_model=dict[str, Any])
def reject_proposal(proposal_id: str):
    """Rejette une proposition proactive."""
    proposal = proposals_repo.get(proposal_id)
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposition introuvable.")

    updated = proposals_repo.update_status(proposal_id, ProposalStatus.REJECTED)
    return {"status": "rejected", "proposal": updated.model_dump(mode="json") if updated else None}
