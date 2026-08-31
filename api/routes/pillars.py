from __future__ import annotations

from pathlib import Path
from typing import Any
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from core.domain import CommandDefinition, HookDefinition, HookEventType, RuleScope, SkillScope
from storage.repository import commands_repo, hooks_repo, rules_repo, skills_repo
from services.commands_registry import commands_registry
from services.rules_registry import rules_registry
from services.skills_registry import parse_skill_md, skills_registry

router = APIRouter(prefix="/api/v1/pillars", tags=["Les 7 Piliers Agentiques (Skills, Rules, Hooks, Commands)"])
alias_router = APIRouter(prefix="/api/v1", tags=["Pillars Direct Aliases"])


class CreateSkillRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=2, max_length=50)
    description: str = Field(min_length=5)
    instructions_md: str = Field(min_length=10)
    scope: SkillScope = SkillScope.GLOBAL
    project_id: str | None = None
    tags: list[str] = Field(default_factory=list)


class CreateRuleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=2, max_length=50)
    category: str = "Sécurité"
    content: str = Field(min_length=10)
    scope: RuleScope = RuleScope.GLOBAL
    project_id: str | None = None


class CreateHookRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=2, max_length=100)
    description: str = ""
    event_type: HookEventType
    action_type: str = "validator"
    target: str = ""
    config: dict[str, Any] = Field(default_factory=dict)
    scope: RuleScope = RuleScope.GLOBAL
    project_id: str | None = None


class TestHookRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    test_payload: dict[str, Any] = Field(default_factory=dict)


class CreateCommandRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    command: str = Field(min_length=2, max_length=30)
    name: str = Field(min_length=2, max_length=100)
    description: str = Field(min_length=5)
    usage: str = ""
    category: str = "Système"
    target: str = ""
    scope: RuleScope = RuleScope.GLOBAL
    project_id: str | None = None


# ------------------------------------------------------------------------------
# 1. SKILLS JIT
# ------------------------------------------------------------------------------

@router.get("/skills", response_model=list[dict[str, Any]])
@alias_router.get("/skills", response_model=list[dict[str, Any]])
def list_skills():
    """Liste tous les playbooks de compétences indexés."""
    skills = skills_repo.list_skills()
    results = []
    for s in skills:
        d = s.model_dump(mode="json")
        path = Path(s.file_path) if s.file_path else None
        if path and path.exists():
            meta = parse_skill_md(path)
            d["instructions_md"] = meta.get("body", path.read_text(encoding="utf-8"))
        else:
            d["instructions_md"] = ""
        results.append(d)
    return results


@router.post("/skills", status_code=status.HTTP_201_CREATED, response_model=dict[str, Any])
@alias_router.post("/skills", status_code=status.HTTP_201_CREATED, response_model=dict[str, Any])
def create_skill(payload: CreateSkillRequest):
    """Crée un nouveau playbook physique SKILL.md avec frontmatter YAML."""
    skill = skills_registry.create_skill(
        name=payload.name,
        description=payload.description,
        instructions_md=payload.instructions_md,
        scope=payload.scope,
        project_id=payload.project_id,
        tags=payload.tags,
    )
    d = skill.model_dump(mode="json")
    d["instructions_md"] = payload.instructions_md
    return d


@router.get("/skills/search", response_model=list[dict[str, Any]])
@alias_router.get("/skills/search", response_model=list[dict[str, Any]])
def search_skills(q: str = "", limit: int = 4, project_id: str | None = None):
    """Recherche dynamique de compétences via Skill RAG (Intent + FTS5)."""
    from services.skill_rag import skill_rag
    skills = skill_rag.search_relevant_skills(query=q, project_id=project_id, limit=limit)
    return [s.model_dump(mode="json") for s in skills]


@router.get("/skills/{skill_name}/body", response_model=dict[str, Any])
@alias_router.get("/skills/{skill_name}/body", response_model=dict[str, Any])
def get_skill_body(skill_name: str, project_id: str | None = None):
    """Charge le contenu complet et les ressources associées d'un skill."""
    details = skills_registry.get_skill_details(skill_name, project_id=project_id)
    if not details:
        raise HTTPException(status_code=404, detail=f"Compétence '{skill_name}' introuvable.")
    return details


@router.patch("/skills/{skill_id}/toggle", response_model=dict[str, Any])
@alias_router.patch("/skills/{skill_id}/toggle", response_model=dict[str, Any])
def toggle_skill(skill_id: str):
    """Active ou désactive un skill JIT."""
    skills = skills_repo.list_skills()
    skill = next((s for s in skills if s.id == skill_id or s.name == skill_id), None)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill introuvable.")
    skill.is_active = not skill.is_active
    skills_repo.save_skill(skill)
    return {
        "id": skill.id,
        "name": skill.name,
        "is_active": skill.is_active,
        "status": "success",
    }


@router.delete("/skills/{skill_id}", response_model=dict[str, Any])
@alias_router.delete("/skills/{skill_id}", response_model=dict[str, Any])
def delete_skill(skill_id: str):
    """Supprime un skill personnalisé."""
    skills = skills_repo.list_skills()
    skill = next((s for s in skills if s.id == skill_id or s.name == skill_id), None)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill introuvable.")
    if skill.name in ["fastapi_enterprise", "sqlite_wal_persistence"]:
        raise HTTPException(
            status_code=400,
            detail="Impossible de supprimer un playbook natif du système. Utilisez l'interrupteur pour le désactiver."
        )
    skills_repo.delete_skill(skill.id)
    return {"status": "success", "message": f"Skill {skill.name} supprimé avec succès."}


# ------------------------------------------------------------------------------
# 2. RULES
# ------------------------------------------------------------------------------

@router.get("/rules", response_model=list[dict[str, Any]])
@alias_router.get("/rules", response_model=list[dict[str, Any]])
def list_rules():
    """Liste toutes les règles modulaires actives."""
    rules = rules_repo.list_rules(active_only=False)
    return [r.model_dump(mode="json") for r in rules]


@router.get("/rules/{rule_name}/body", response_model=dict[str, Any])
@alias_router.get("/rules/{rule_name}/body", response_model=dict[str, Any])
def get_rule_body(rule_name: str, project_id: str | None = None):
    """Charge le contenu complet d'une règle modulaire."""
    rules = rules_repo.list_rules(active_only=False)
    rule = next((r for r in rules if r.id == rule_name or r.name == rule_name), None)
    if not rule:
        raise HTTPException(status_code=404, detail=f"Règle '{rule_name}' introuvable.")
    return rule.model_dump(mode="json")


@router.post("/rules", status_code=status.HTTP_201_CREATED, response_model=dict[str, Any])
@alias_router.post("/rules", status_code=status.HTTP_201_CREATED, response_model=dict[str, Any])
def create_rule(payload: CreateRuleRequest):
    """Crée une nouvelle règle modulaire physique (.md)."""
    rule = rules_registry.create_rule(
        name=payload.name,
        category=payload.category,
        content=payload.content,
        scope=payload.scope,
        project_id=payload.project_id,
    )
    return rule.model_dump(mode="json")


@router.patch("/rules/{rule_id}/toggle", response_model=dict[str, Any])
@alias_router.patch("/rules/{rule_id}/toggle", response_model=dict[str, Any])
def toggle_rule(rule_id: str):
    """Active ou désactive une règle."""
    rules = rules_repo.list_rules(active_only=False)
    rule = next((r for r in rules if r.id == rule_id or r.name == rule_id), None)
    if not rule:
        raise HTTPException(status_code=404, detail="Règle introuvable.")
    rule.is_active = not rule.is_active
    rules_repo.save_rule(rule)
    return {
        "id": rule.id,
        "name": rule.name,
        "is_active": rule.is_active,
        "status": "success",
    }


@router.delete("/rules/{rule_id}", response_model=dict[str, Any])
@alias_router.delete("/rules/{rule_id}", response_model=dict[str, Any])
def delete_rule(rule_id: str):
    """Supprime une règle personnalisée."""
    rules = rules_repo.list_rules(active_only=False)
    rule = next((r for r in rules if r.id == rule_id or r.name == rule_id), None)
    if not rule:
        raise HTTPException(status_code=404, detail="Règle introuvable.")
    CORE_RULES = [
        "finops_limits", "no_emojis", "prevention_sqlite_concurrency_locks",
        "python_pep8_standards", "security_guardrails", "clean_architecture_strict",
        "zero_emoji_policy", "finops_budget_cap"
    ]
    if rule.name in CORE_RULES:
        raise HTTPException(
            status_code=400,
            detail="Impossible de supprimer une règle native du système. Utilisez l'interrupteur pour la désactiver."
        )
    rules_repo.delete_rule(rule.id)
    return {"status": "success", "message": f"Règle {rule.name} supprimée avec succès."}


# ------------------------------------------------------------------------------
# 3. HOOKS
# ------------------------------------------------------------------------------

@router.get("/hooks", response_model=list[dict[str, Any]])
@alias_router.get("/hooks", response_model=list[dict[str, Any]])
def list_hooks():
    """Liste tous les écouteurs de cycle de vie configurés."""
    hooks = hooks_repo.list_hooks()
    return [h.model_dump(mode="json") for h in hooks]


@router.post("/hooks", status_code=status.HTTP_201_CREATED, response_model=dict[str, Any])
@alias_router.post("/hooks", status_code=status.HTTP_201_CREATED, response_model=dict[str, Any])
def create_hook(payload: CreateHookRequest):
    """Crée un nouvel écouteur de cycle de vie."""
    hook = HookDefinition(
        name=payload.name,
        event_type=payload.event_type,
        action_type=payload.action_type,
        target=payload.target,
        config=payload.config,
    )
    saved = hooks_repo.save_hook(hook)
    return saved.model_dump(mode="json")


@router.patch("/hooks/{hook_id}/toggle", response_model=dict[str, Any])
@alias_router.patch("/hooks/{hook_id}/toggle", response_model=dict[str, Any])
def toggle_hook(hook_id: str):
    """Active ou désactive un hook."""
    hooks = hooks_repo.list_hooks()
    hook = next((h for h in hooks if h.id == hook_id or h.name == hook_id), None)
    if not hook:
        raise HTTPException(status_code=404, detail="Hook introuvable.")
    hook.is_active = not hook.is_active
    hooks_repo.save_hook(hook)
    return {
        "id": hook.id,
        "name": hook.name,
        "is_active": hook.is_active,
        "status": "success",
    }


@router.delete("/hooks/{hook_id}", response_model=dict[str, Any])
@alias_router.delete("/hooks/{hook_id}", response_model=dict[str, Any])
def delete_hook(hook_id: str):
    """Supprime un hook personnalisé."""
    hooks = hooks_repo.list_hooks()
    hook = next((h for h in hooks if h.id == hook_id or h.name == hook_id), None)
    if not hook:
        raise HTTPException(status_code=404, detail="Hook introuvable.")
    CORE_HOOK_KEYWORDS = [
        "Sécurité", "AST", "Budgétaire", "Retries", "Snapshot",
        "security_validator", "ast_validator", "circuit_breaker", "retry_manager", "snapshot_creator"
    ]
    if any(kw in hook.name or kw == hook.action_type for kw in CORE_HOOK_KEYWORDS):
        raise HTTPException(
            status_code=400,
            detail="Impossible de supprimer une sentinelle native du système. Utilisez l'interrupteur pour la désactiver."
        )
    hooks_repo.delete_hook(hook.id)
    return {"status": "success", "message": f"Hook {hook.name} supprimé avec succès."}


@router.get("/hooks/history", response_model=list[dict[str, Any]])
@alias_router.get("/hooks/history", response_model=list[dict[str, Any]])
def get_hooks_history(limit: int = 50, project_id: str | None = None):
    """Récupère l'historique d'audit des sentinelles exécutées."""
    logs = hooks_repo.list_audit_logs(limit=limit, project_id=project_id)
    return [l.model_dump(mode="json") for l in logs]


@router.post("/hooks/{hook_id}/test", response_model=dict[str, Any])
@alias_router.post("/hooks/{hook_id}/test", response_model=dict[str, Any])
def test_hook_endpoint(hook_id: str, payload: TestHookRequest):
    """Exécute unitairement une sentinelle pour validation interactive."""
    from services.hooks_engine import hooks_engine
    try:
        return hooks_engine.test_hook(hook_id, payload.test_payload)
    except Exception as err:
        raise HTTPException(status_code=400, detail=str(err))


# ------------------------------------------------------------------------------
# 4. COMMANDS
# ------------------------------------------------------------------------------

@router.get("/commands", response_model=list[dict[str, Any]])
@alias_router.get("/commands", response_model=list[dict[str, Any]])
def list_commands():
    """Liste toutes les slash commands disponibles."""
    commands = commands_registry.list_commands()
    return [c.model_dump(mode="json") for c in commands]


@router.post("/commands", status_code=status.HTTP_201_CREATED, response_model=dict[str, Any])
@alias_router.post("/commands", status_code=status.HTTP_201_CREATED, response_model=dict[str, Any])
def create_command(payload: CreateCommandRequest):
    """Crée une nouvelle slash command."""
    cmd = CommandDefinition(
        command=payload.command if payload.command.startswith("/") else f"/{payload.command}",
        name=payload.name,
        description=payload.description,
        usage=payload.usage,
        category=payload.category,
        target=payload.target,
        scope=payload.scope,
        project_id=payload.project_id,
    )
    saved = commands_repo.save_command(cmd)
    return saved.model_dump(mode="json")


@router.patch("/commands/{command_id:path}/toggle", response_model=dict[str, Any])
@alias_router.patch("/commands/{command_id:path}/toggle", response_model=dict[str, Any])
def toggle_command(command_id: str):
    """Active ou désactive une slash command."""
    cmd = commands_repo.get_command(command_id)
    if not cmd:
        all_cmds = commands_repo.list_commands(active_only=False)
        cmd = next((c for c in all_cmds if c.id == command_id or c.command == command_id or c.command == f"/{command_id}"), None)
    if not cmd:
        raise HTTPException(status_code=404, detail="Commande introuvable.")
    cmd.is_active = not cmd.is_active
    commands_repo.save_command(cmd)
    return {
        "command": cmd.command,
        "name": cmd.name,
        "is_active": cmd.is_active,
        "status": "success",
    }


@router.delete("/commands/{command_id:path}", response_model=dict[str, Any])
@alias_router.delete("/commands/{command_id:path}", response_model=dict[str, Any])
def delete_command(command_id: str):
    """Supprime une slash command personnalisée."""
    cmd = commands_repo.get_command(command_id)
    if not cmd:
        all_cmds = commands_repo.list_commands(active_only=False)
        cmd = next((c for c in all_cmds if c.id == command_id or c.command == command_id or c.command == f"/{command_id}"), None)
    if not cmd:
        raise HTTPException(status_code=404, detail="Commande introuvable.")
    if cmd.scope == RuleScope.GLOBAL:
        raise HTTPException(
            status_code=400,
            detail="Impossible de supprimer une commande native globale de la plateforme. Utilisez l'interrupteur pour la désactiver."
        )
    commands_repo.delete_command(cmd.command)
    return {"status": "success", "message": f"Commande {cmd.command} supprimée avec succès."}
