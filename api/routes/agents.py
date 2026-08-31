from __future__ import annotations

from typing import Any
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from core.domain import AgentDefinition, AgentLink, AgentType, LinkType, TopologyMode
from storage.repository import agent_links_repo, agent_repo
from services.orchestrator import orchestrator

router = APIRouter(prefix="/api/v1/agents", tags=["Agents & Topologie Canvas"])


class CreateAgentRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(min_length=3, max_length=50)
    name: str = Field(min_length=3, max_length=100)
    project_id: str | None = None
    role_description: str = ""
    role: str = ""
    goal: str = ""
    backstory: str = ""
    agent_type: AgentType = AgentType.CUSTOM
    parent_id: str | None = None
    model: str = "moonshotai/kimi-k3"
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, ge=256, le=32768)
    budget_limit_usd: float = Field(default=5.0, ge=0.1, le=1000.0)
    system_prompt: str = ""
    tools: list[str] = Field(default_factory=list)
    canvas_x: float = 0.0
    canvas_y: float = 0.0
    icon: str = "bot"
    is_active: bool = True


class UpdateAgentRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str | None = None
    project_id: str | None = None
    role_description: str | None = None
    role: str | None = None
    goal: str | None = None
    backstory: str | None = None
    parent_id: str | None = None
    model: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    timeout_seconds: float | None = None
    reasoning_effort: str | None = None
    max_iter: int | None = None
    budget_limit_usd: float | None = None
    system_prompt: str | None = None
    allow_delegation: bool | None = None
    tools: list[str] | None = None
    skills: list[str] | None = None
    rules: list[str] | None = None
    is_active: bool | None = None
    canvas_x: float | None = None
    canvas_y: float | None = None
    icon: str | None = None


class SwitchTopologyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topology: TopologyMode


@router.get("", response_model=list[dict[str, Any]])
def list_agents(
    project_id: str | None = None,
    is_core_only: bool = False,
    include_core: bool = False,
):
    """Liste tous les agents configurés filtrés par projet ou pour le Studio Méta-Agent."""
    if is_core_only or project_id == "studio":
        agents = agent_repo.get_core_meta_agents()
    elif project_id is not None:
        agents = agent_repo.list_all(
            project_id=project_id,
            is_core_only=False,
            include_core=include_core,
        )
    else:
        agents = agent_repo.list_all()

    from storage.repository import finops_repo
    metrics = finops_repo.list_all()
    results = []
    for a in agents:
        d = a.model_dump(mode="json")
        a_metrics = [m for m in metrics if m.agent_id == a.id]
        d["cost_usd"] = sum(m.cost_usd for m in a_metrics)
        d["total_tokens"] = sum(m.prompt_tokens + m.completion_tokens for m in a_metrics)
        results.append(d)
    return results


@router.get("/topology", response_model=dict[str, str])
def get_current_topology():
    """Retourne le mode de topologie active."""
    return {"topology": orchestrator.active_topology.value}


@router.post("/topology", response_model=dict[str, str])
def switch_topology(payload: SwitchTopologyRequest):
    """Bascule la topologie multi-agents en 1 clic."""
    orchestrator.set_topology(payload.topology)
    return {"status": "success", "topology": payload.topology.value}


# ==============================================================================
# LIAISONS DU GRAPHE CANVAS 2D (DAG LINKS)
# ==============================================================================

class CreateAgentLinkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_agent_id: str
    target_agent_id: str
    project_id: str | None = None
    link_type: LinkType = LinkType.DATA_FLOW
    label: str = ""


class UpdateAgentLinkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    link_type: LinkType | None = None
    label: str | None = None
    is_active: bool | None = None


class ApplyTemplateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    template_name: str
    project_id: str | None = None


class UpdateAgentPositionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    canvas_x: float
    canvas_y: float


@router.get("/links/all", response_model=list[dict[str, Any]])
@router.get("/links", response_model=list[dict[str, Any]])
def list_agent_links(project_id: str | None = None):
    """Retourne la liste des câbles / liaisons réelles du graphe filtrés hermétiquement par projet."""
    if project_id in ("studio", None, ""):
        links = agent_links_repo.list_all(is_core_only=True)
    elif project_id == "all":
        links = agent_links_repo.list_all()
    else:
        links = agent_links_repo.list_all(project_id=project_id)
    return [l.model_dump(mode="json") for l in links]


@router.post("/links", status_code=status.HTTP_201_CREATED, response_model=dict[str, Any])
def create_agent_link(payload: CreateAgentLinkRequest):
    """Crée une nouvelle liaison entre deux nœuds du Canvas et la persiste."""
    src = agent_repo.get(payload.source_agent_id)
    tgt = agent_repo.get(payload.target_agent_id)

    src_name = src.name if src else payload.source_agent_id
    tgt_name = tgt.name if tgt else payload.target_agent_id
    src_short = src_name.split(":")[0].strip()
    tgt_short = tgt_name.split(":")[0].strip()

    label = payload.label
    if not label:
        if payload.link_type == LinkType.DIRECT:
            label = f"{src_short} -> {tgt_short}"
        elif payload.link_type == LinkType.DEBATE:
            label = f"{src_short} <-> {tgt_short}"
        elif payload.link_type == LinkType.SUPERVISION:
            label = f"{src_short} v {tgt_short}"
        elif payload.link_type == LinkType.PARALLEL:
            label = f"{src_short} // {tgt_short}"
        else:
            label = f"{src_short} -> {tgt_short}"

    link = AgentLink(
        source_agent_id=payload.source_agent_id,
        target_agent_id=payload.target_agent_id,
        project_id=payload.project_id,
        link_type=payload.link_type,
        label=label,
        is_active=True,
    )
    saved = agent_links_repo.create(link)
    return saved.model_dump(mode="json")


@router.patch("/links/{link_id}", response_model=dict[str, Any])
def update_agent_link(link_id: str, payload: UpdateAgentLinkRequest):
    """Met à jour le type sémantique d'une liaison (Séquentiel, Débat, Supervision, Parallèle) et son libellé."""
    link = agent_links_repo.get(link_id)
    if not link:
        raise HTTPException(status_code=404, detail="Liaison introuvable.")

    src = agent_repo.get(link.source_agent_id)
    tgt = agent_repo.get(link.target_agent_id)
    src_short = src.name.split(":")[0].strip() if src else link.source_agent_id
    tgt_short = tgt.name.split(":")[0].strip() if tgt else link.target_agent_id

    if payload.link_type is not None:
        link.link_type = payload.link_type

    if payload.label is not None and payload.label.strip():
        link.label = payload.label.strip()
    elif payload.link_type is not None:
        if link.link_type == LinkType.DIRECT:
            link.label = f"{src_short} -> {tgt_short}"
        elif link.link_type == LinkType.DEBATE:
            link.label = f"{src_short} <-> {tgt_short}"
        elif link.link_type == LinkType.SUPERVISION:
            link.label = f"{src_short} v {tgt_short}"
        elif link.link_type == LinkType.PARALLEL:
            link.label = f"{src_short} // {tgt_short}"

    if payload.is_active is not None:
        link.is_active = payload.is_active

    saved = agent_links_repo.save(link)
    return saved.model_dump(mode="json")


@router.delete("/links/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_agent_link(link_id: str):
    """Supprime une liaison / débranche un câble de manière idempotente."""
    agent_links_repo.delete(link_id)


@router.post("/links/template", response_model=list[dict[str, Any]])
def apply_links_template(payload: ApplyTemplateRequest):
    """Applique un patron de câblage prédéfini (standard, debate, supervision, parallel)."""
    links = agent_links_repo.apply_template(payload.template_name, project_id=payload.project_id)
    return [l.model_dump(mode="json") for l in links]


@router.patch("/{agent_id}/position", response_model=dict[str, Any])
def update_agent_position(agent_id: str, payload: UpdateAgentPositionRequest):
    """Met à jour instantanément la position Canvas d'un agent après Drag & Drop."""
    agent = agent_repo.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent introuvable.")
    agent.canvas_x = payload.canvas_x
    agent.canvas_y = payload.canvas_y
    saved = agent_repo.save(agent)
    return saved.model_dump(mode="json")


@router.get("/{agent_id}", response_model=dict[str, Any])
def get_agent(agent_id: str):
    """Récupère la configuration détaillée d'un agent."""
    agent = agent_repo.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent introuvable.")
    return agent.model_dump(mode="json")


@router.post("", status_code=status.HTTP_201_CREATED, response_model=dict[str, Any])
def create_agent(payload: CreateAgentRequest):
    """Crée un nouvel agent personnalisé et l'enregistre en BDD."""
    agent_id = payload.id
    if agent_repo.get(agent_id):
        from uuid import uuid4
        agent_id = f"{payload.id}_{str(uuid4())[:6]}"

    agent = AgentDefinition(
        id=agent_id,
        name=payload.name,
        project_id=payload.project_id,
        role_description=payload.role_description,
        role=payload.role,
        goal=payload.goal,
        backstory=payload.backstory,
        agent_type=payload.agent_type,
        parent_id=payload.parent_id,
        model=payload.model,
        temperature=payload.temperature,
        max_tokens=payload.max_tokens,
        budget_limit_usd=payload.budget_limit_usd,
        system_prompt=payload.system_prompt,
        tools=payload.tools,
        canvas_x=payload.canvas_x,
        canvas_y=payload.canvas_y,
        icon=payload.icon,
        is_active=payload.is_active,
        is_core_meta_agent=False,
    )
    saved = agent_repo.save(agent)
    return saved.model_dump(mode="json")


@router.put("/{agent_id}", response_model=dict[str, Any])
@router.patch("/{agent_id}", response_model=dict[str, Any])
def update_agent(agent_id: str, payload: UpdateAgentRequest):
    """Met à jour les hyperparamètres ou la position Canvas d'un agent."""
    agent = agent_repo.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent introuvable.")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(agent, field, value)

    saved = agent_repo.save(agent)
    return saved.model_dump(mode="json")


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_agent(agent_id: str):
    """Supprime un agent (interdit pour les 5 Meta-Agents officiels)."""
    deleted = agent_repo.delete(agent_id)
    if not deleted:
        raise HTTPException(
            status_code=400,
            detail="Impossible de supprimer cet agent (agent introuvable ou protégé par le cœur système).",
        )
