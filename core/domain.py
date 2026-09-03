from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, ConfigDict


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ------------------------------------------------------------------------------
# 1. ÉNUMÉRATIONS DU DOMAINE v5
# ------------------------------------------------------------------------------

class ProjectStatus(str, Enum):
    DRAFT = "draft"
    CADRAGE = "cadrage"
    ARCHITECTURE_APPROVED = "architecture_approved"
    GENERATING = "generating"
    COMPLETED = "completed"
    MAINTENANCE = "maintenance"
    ERROR = "error"


class MessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    AGENT = "agent"


class AgentType(str, Enum):
    ARCHITECT = "architect"
    CODER = "coder"
    QUALITY_JUDGE = "quality_judge"
    FINOPS_GUARDIAN = "finops_guardian"
    COPILOT = "copilot"
    MODEL_MATCHER = "model_matcher"
    CUSTOM = "custom"


class FinOpsBadge(str, Enum):
    TOP_PERFORMANCE = "top_performance"
    SWEET_SPOT = "sweet_spot"
    ULTRA_ECO = "ultra_eco"


class TopologyMode(str, Enum):
    SEQUENTIAL = "sequential"
    HIERARCHICAL = "hierarchical"
    CONSENSUS_DEBATE = "consensus_debate"
    SWARM = "swarm"
    PARALLEL = "parallel"
    CUSTOM_DAG = "custom_dag"


class LinkType(str, Enum):
    DIRECT = "direct"                       # Flux séquentiel direct ➔
    DEBATE = "debate"                       # Débat contradictoire / Actor-Critic ⇄
    SUPERVISION = "supervision"             # Ordres & Supervision Hiérarchique ⇣
    PARALLEL = "parallel"                   # Synchronisation & Parallèle ⇉
    # Aliases de rétrocompatibilité
    SPEC_TO_CODE = "spec_to_code"
    CODE_TO_AUDIT = "code_to_audit"
    AUDIT_TO_FINOPS = "audit_to_finops"
    FEEDBACK_REVIEW = "feedback_review"
    DATA_FLOW = "data_flow"


class AgentLink(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str | None = None
    source_agent_id: str
    target_agent_id: str
    link_type: LinkType = LinkType.DATA_FLOW
    label: str = ""
    is_active: bool = True
    created_at: datetime = Field(default_factory=utc_now)


class McpTransport(str, Enum):
    STDIO = "stdio"
    SSE = "sse"
    BUILTIN = "builtin"


class SkillScope(str, Enum):
    GLOBAL = "global"
    LOCAL = "local"


class RuleScope(str, Enum):
    GLOBAL = "global"
    LOCAL = "local"


class HookEventType(str, Enum):
    PRE_TOOL_CALL = "pre_tool_call"
    POST_TOOL_CALL = "post_tool_call"
    PRE_LLM_CALL = "pre_llm_call"
    POST_LLM_CALL = "post_llm_call"
    ON_BUDGET_THRESHOLD = "on_budget_threshold"
    ON_ERROR = "on_error"
    POST_CHECKPOINT = "post_checkpoint"
    ON_SESSION_START = "on_session_start"
    ON_SESSION_END = "on_session_end"


class HitlRequestStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


# ------------------------------------------------------------------------------
# 2. DOCUMENTS & MESSAGES
# ------------------------------------------------------------------------------

class DocumentAttachment(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    id: str = Field(default_factory=lambda: str(uuid4()))
    filename: str
    content_type: str = "text/plain"
    size_bytes: int = 0
    raw_content: str = ""
    summary: str = ""
    created_at: datetime = Field(default_factory=utc_now)


class Message(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    id: str = Field(default_factory=lambda: str(uuid4()))
    role: MessageRole
    content: str
    author_name: str | None = None
    agent_id: str | None = None
    thread_id: str | None = None
    project_id: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    attachments: list[DocumentAttachment] = Field(default_factory=list)


class SystemCopilotMessage(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    id: str = Field(default_factory=lambda: str(uuid4()))
    role: MessageRole
    content: str
    author_name: str | None = None
    attachments: list[DocumentAttachment] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)


class Thread(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    title: str = "Discussion"
    is_pinned: bool = False
    is_archived: bool = False
    is_unread: bool = False
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    messages: list[Message] = Field(default_factory=list)

    def add_message(
        self,
        role: MessageRole,
        content: str,
        author_name: str | None = None,
        agent_id: str | None = None,
        attachments: list[DocumentAttachment] | None = None,
    ) -> Message:
        msg = Message(
            role=role,
            content=content,
            author_name=author_name,
            agent_id=agent_id,
            thread_id=self.id,
            project_id=self.project_id,
            attachments=attachments or [],
        )
        self.messages.append(msg)
        self.updated_at = utc_now()
        return msg


# ------------------------------------------------------------------------------
# 3. PROFIL FINOPS & CADRAGE INCEPTION
# ------------------------------------------------------------------------------

class FinOpsProfileOption(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    profile_type: FinOpsBadge
    name: str
    title: str
    description: str
    model_id: str
    quality_score: float
    coding_score: float
    reasoning_score: float
    speed_tok_s: float
    price_in_usd: float
    price_out_usd: float
    price_cache_usd: float = 0.0
    estimated_project_cost_usd: float


class CadrageSynthesis(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    project_title: str = ""
    summary: str = ""
    problem_statement: str = ""
    target_audience: str = ""
    functional_requirements: list[str] = Field(default_factory=list)
    technical_stack: list[str] = Field(default_factory=list)
    multi_agent_architecture: list[dict[str, Any]] = Field(default_factory=list)
    mcp_tools_required: list[str] = Field(default_factory=list)
    finops_options: list[FinOpsProfileOption] = Field(default_factory=list)
    selected_profile: FinOpsBadge = FinOpsBadge.SWEET_SPOT
    estimated_dev_time: str = "Immédiat (Auto-scaffolding)"
    created_at: datetime = Field(default_factory=utc_now)


# ------------------------------------------------------------------------------
# 4. PROJET CENTRAL v5
# ------------------------------------------------------------------------------

class Project(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    id: UUID = Field(default_factory=uuid4)
    name: str = "Nouveau Projet"
    status: ProjectStatus = ProjectStatus.DRAFT
    target_path: str = ""
    selected_finops_profile: FinOpsBadge = FinOpsBadge.SWEET_SPOT
    budget_limit_usd: float = 10.0
    active_thread_id: str | None = None
    is_archived: bool = False
    deleted_at: datetime | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    # Données enrichies en mémoire
    threads: list[Thread] = Field(default_factory=list)
    documents: list[DocumentAttachment] = Field(default_factory=list)
    synthesis: CadrageSynthesis | None = None
    generated_files: list[str] = Field(default_factory=list)

    def get_or_create_main_thread(self) -> Thread:
        if not self.threads:
            main_t = Thread(
                id=f"thread_{str(self.id)[:8]}_main",
                project_id=str(self.id),
                title="Cadrage & Spécifications Inception",
            )
            self.threads.append(main_t)
            self.active_thread_id = main_t.id
            return main_t
        if self.active_thread_id:
            for t in self.threads:
                if t.id == self.active_thread_id:
                    return t
        return self.threads[0]


# ------------------------------------------------------------------------------
# 5. LES 5 META-AGENTS & TOPOLOGIE CANVAS
# ------------------------------------------------------------------------------

class AgentDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    id: str
    name: str
    project_id: str | None = None
    role_description: str = ""
    role: str = ""
    goal: str = ""
    backstory: str = ""
    agent_type: AgentType = AgentType.CUSTOM
    parent_id: str | None = None
    model: str
    temperature: float = 0.2
    max_tokens: int = 4096
    timeout_seconds: float = 60.0
    reasoning_effort: str = "medium"
    max_iter: int = 5
    budget_limit_usd: float = 5.0
    system_prompt: str = ""
    allow_delegation: bool = True
    tools: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    rules: list[str] = Field(default_factory=list)
    is_active: bool = True
    is_core_meta_agent: bool = False
    canvas_x: float = 0.0
    canvas_y: float = 0.0
    icon: str = "layers"
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


# ------------------------------------------------------------------------------
# 6. FINOPS, ANALYTICS & BENCHMARKS
# ------------------------------------------------------------------------------

class FinOpsMetric(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = Field(default_factory=utc_now)
    session_id: str = "global"
    project_id: str | None = None
    project_name: str = "Global"
    agent_id: str = "agent_coder"
    agent_name: str = "Développeur Logiciel"
    model: str = "unknown"
    task_name: str = "Inférence"
    prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int = 0
    cached_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    ttft_ms: int = 0
    status: str = "success"


class BenchmarkRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    model_id: str
    name: str
    creator: str = "Independent"
    quality_index: float = 0.0
    coding_score: float = 0.0
    reasoning_score: float = 0.0
    speed_tok_s: float = 0.0
    price_in_usd: float = 0.0
    price_out_usd: float = 0.0
    price_cache_usd: float = 0.0
    context_length: int = 128000
    badge: FinOpsBadge = FinOpsBadge.SWEET_SPOT
    evaluations: dict[str, float | None] = Field(default_factory=dict)
    updated_at: datetime = Field(default_factory=utc_now)


# ------------------------------------------------------------------------------
# 7. LES 7 PILIERS AGENTIQUES : MCP, SKILLS, RULES, HOOKS, COMMANDS
# ------------------------------------------------------------------------------

class McpServerConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    transport: McpTransport = McpTransport.STDIO
    command_or_url: str
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    project_id: str | None = None
    is_active: bool = True
    status: str = "configured"  # configured, connected, error
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class McpToolDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    id: str
    server_id: str | None = None
    name: str
    description: str
    category: str = "Système"
    parameters_schema: dict[str, Any] = Field(default_factory=dict)
    project_id: str | None = None
    mcp_primitive: str = "tool"  # tool, resource, prompt
    is_idempotent: bool = False
    is_critical: bool = False
    is_active: bool = True
    is_core: bool = True
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class SkillDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    description: str
    version: str = "1.0.0"
    scope: SkillScope = SkillScope.GLOBAL
    project_id: str | None = None
    file_path: str
    tags: list[str] = Field(default_factory=list)
    invocations_count: int = 0
    success_count: int = 0
    is_active: bool = True
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class RuleDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    category: str = "Sécurité"
    scope: RuleScope = RuleScope.GLOBAL
    project_id: str | None = None
    file_path: str
    content: str
    is_active: bool = True
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class HookDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    description: str = ""
    event_type: HookEventType
    action_type: str = "validator"  # validator, logger, alert, circuit_breaker, retry_manager, snapshot_creator
    target: str = ""
    config: dict[str, Any] = Field(default_factory=dict)
    scope: RuleScope = RuleScope.GLOBAL
    project_id: str | None = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class HookAuditLog(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    id: str = Field(default_factory=lambda: str(uuid4()))
    hook_id: str
    hook_name: str
    event_type: HookEventType
    action_type: str
    status: str = "success"  # "success", "blocked", "error"
    duration_ms: float = 0.0
    payload_summary: str = ""
    result_summary: str = ""
    error: str | None = None
    project_id: str | None = None
    created_at: datetime = Field(default_factory=utc_now)


class CommandDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    id: str = Field(default_factory=lambda: str(uuid4()))
    command: str  # ex: /audit, /cadrage
    name: str
    description: str
    usage: str = ""  # ex: /budget [montant_usd] ou /match <role>
    category: str = "Système"  # ex: Inception & Cadrage, Qualité & Audit, FinOps & Budget, Modèles & Benchmarks
    handler_type: str = "native"  # native, script, custom_md
    target: str = ""
    scope: RuleScope = RuleScope.GLOBAL
    project_id: str | None = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


# ------------------------------------------------------------------------------
# 8. MATRICE SCORE QUALITÉ /100, TIME TRAVEL & HITL
# ------------------------------------------------------------------------------

class QualityScoreMatrix(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    technical_health: float = 35.0   # /35 (AST 15 + Pytest 20)
    robustness_security: float = 25.0  # /25 (Pydantic 15 + Error handling 10)
    functional_coverage: float = 30.0 # /30 (Cadrage match)
    documentation: float = 10.0       # /10 (README 5 + Cadrage 5)
    total_score: float = 100.0        # /100
    verdict: str = "SUCCÈS"          # SUCCÈS (>=85), AMÉLIORATION (70-84), REJET (<70)
    details: list[str] = Field(default_factory=list)
    evaluated_at: datetime = Field(default_factory=utc_now)


class CheckpointData(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    thread_id: str | None = None
    step_name: str
    state_payload: dict[str, Any] = Field(default_factory=dict)
    files_snapshot: dict[str, str] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class HitlRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str | None = None
    agent_id: str | None = None
    request_type: str  # tool_permission, file_write, shell_command, budget_exceeded, new_rule, new_skill
    title: str
    description: str
    plain_reason: str = ""  # Explication vulgarisée du pourquoi
    project_impact: str = ""  # Ce que cela apporte au projet
    is_urgent: bool = False
    payload: dict[str, Any] = Field(default_factory=dict)
    status: HitlRequestStatus = HitlRequestStatus.PENDING
    rejection_reason: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    resolved_at: datetime | None = None


class LessonLearned(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    id: str = Field(default_factory=lambda: str(uuid4()))
    scope: str = "global"  # global, project
    project_id: str | None = None
    topic: str
    problem_statement: str
    solution_applied: str
    prevention_rule: str = ""
    confidence_score: float = 0.95
    status: str = "approved"
    created_at: datetime = Field(default_factory=utc_now)


class ProposalType(str, Enum):
    AGENT = "agent"
    TOOL = "tool"
    RULE = "rule"
    SKILL = "skill"
    TOPOLOGY = "topology"
    OPTIMIZATION = "optimization"


class ProposalStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class ActionProposal(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str | None = None
    proposal_type: ProposalType
    title: str
    description: str
    benefit: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    status: ProposalStatus = ProposalStatus.PENDING
    created_at: datetime = Field(default_factory=utc_now)
    resolved_at: datetime | None = None


def extract_reasoning_metadata(raw_reasoning: Any = None) -> dict[str, Any]:
    """Extrait dynamiquement l'objet reasoning natif de l'API OpenRouter sans aucun fallback ni règle codée en dur.
    
    Retourne directement le dictionnaire des capacités de réflexion réelles du modèle :
    - supported_efforts: list[str] (ex: ['high', 'medium', 'low'])
    - default_effort: str (ex: 'medium')
    - mandatory: bool
    - default_enabled: bool
    - has_reasoning: bool
    """
    if not isinstance(raw_reasoning, dict):
        raw_reasoning = {}
    efforts = list(raw_reasoning.get("supported_efforts") or [])
    default_effort = raw_reasoning.get("default_effort") or (efforts[0] if efforts else "none")
    mandatory = bool(raw_reasoning.get("mandatory", False))
    default_enabled = bool(raw_reasoning.get("default_enabled", False))
    has_reasoning = bool(efforts or mandatory or default_enabled)

    return {
        "has_reasoning": has_reasoning,
        "supported_efforts": efforts,
        "default_effort": default_effort,
        "mandatory": mandatory,
        "default_enabled": default_enabled,
    }


