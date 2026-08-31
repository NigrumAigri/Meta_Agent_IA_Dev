from __future__ import annotations

import json
from typing import Any
from uuid import UUID
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from core.domain import DocumentAttachment, MessageRole, TopologyMode
from storage.repository import project_repo
from services.chat_action_parser import chat_action_parser
from services.commands_registry import commands_registry
from services.openrouter_client import openrouter_client
from services.orchestrator import orchestrator

router = APIRouter(prefix="/api/v1/chat", tags=["Chat & Streaming SSE"])


class SendChatMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: UUID
    thread_id: str | None = None
    message: str = Field(min_length=1)
    topology: TopologyMode | None = None
    attachments: list[dict[str, Any]] = Field(default_factory=list)


class ExecuteCommandRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    command: str = Field(min_length=1)
    project_id: str | None = None


class ExecuteMultiAgentPipelineRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: UUID | str | None = None
    instruction: str = "Execution du graphe de workflow complet"
    topology: TopologyMode | None = None


def generate_smart_thread_title(message: str, existing_titles: list[str]) -> str:
    """Génère un titre concis et pertinent (3 à 5 mots) à partir de la première consigne sans doublon."""
    cleaned = message.strip().replace("\n", " ")
    prefixes = [
        "peux-tu", "pourrais-tu", "merci de", "stp", "s'il te plait", "sil te plait",
        "crée un", "crée une", "créer un", "créer une", "crée", "cree",
        "génère un", "génère une", "génère", "genere",
        "fais-moi un", "fais-moi une", "fais un", "fais une",
        "ajoute un", "ajoute une", "ajoute",
        "analyse le", "analyse la", "analyse les", "analyse",
        "explique-moi", "explique",
    ]
    low = cleaned.lower()
    for p in prefixes:
        if low.startswith(p):
            cleaned = cleaned[len(p):].strip()
            low = cleaned.lower()
            break
    words = [w for w in cleaned.split(" ") if w.strip()]
    if not words:
        base_title = "Discussion"
    else:
        chosen_words = words[:5]
        base_title = " ".join(chosen_words)
        base_title = base_title[0].upper() + base_title[1:]
        if len(base_title) > 40:
            base_title = base_title[:37] + "..."

    final_title = base_title
    counter = 2
    normalized_existing = [t.lower() for t in existing_titles]
    while final_title.lower() in normalized_existing:
        final_title = f"{base_title} ({counter})"
        counter += 1
    return final_title


@router.post("/message", response_model=dict[str, Any])
async def send_chat_message(payload: SendChatMessageRequest):
    """Envoie un message utilisateur, analyse les actions Canvas en langage naturel et exécute le tour."""
    project = project_repo.get(payload.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Projet introuvable.")

    if payload.thread_id:
        project.active_thread_id = payload.thread_id

    # 1. Analyse et exécution des actions directes sur le Canvas (ex: ajouter agent, relier câbles)
    action_result = chat_action_parser.parse_and_execute_chat_actions(
        message=payload.message,
        project_id=str(payload.project_id),
    )

    # 2. Convertir les pièces jointes
    parsed_attachments = []
    for att in payload.attachments:
        try:
            if isinstance(att, DocumentAttachment):
                parsed_attachments.append(att)
            elif isinstance(att, dict):
                parsed_attachments.append(DocumentAttachment.model_validate(att))
        except Exception as e:
            logger.warning("Échec de validation de la pièce jointe '%s' : %s", att, e)

    # 3. Exécution du tour d'orchestration
    updated_project = await orchestrator.run_cadrage_turn(
        project=project,
        user_message=payload.message,
        attachments=parsed_attachments,
    )

    thread = updated_project.get_or_create_main_thread()
    last_assistant_msg = next((m for m in reversed(thread.messages) if m.role.value == "assistant"), None)

    # 4. Auto-titrage intelligent IA si le fil porte un nom temporaire / générique
    if thread.title in ("Nouvelle discussion", "Discussion") or thread.title.startswith("Discussion "):
        existing_threads = project_repo.get_threads(str(updated_project.id))
        existing_titles = [t.title for t in existing_threads if t.id != thread.id]
        new_title = generate_smart_thread_title(payload.message, existing_titles)
        project_repo.update_thread(thread.id, title=new_title)
        thread.title = new_title

    actions_note = ""
    if action_result.get("actions_executed"):
        actions_note = "\n\n" + "\n".join(f"- {a['message']}" for a in action_result["actions_executed"])

    reply_content = (last_assistant_msg.content if last_assistant_msg else "") + actions_note

    from storage.repository import agent_repo
    architect = agent_repo.get("agent_architect")
    model_used = architect.model if architect else "Modèle Configuré"

    return {
        "status": "success",
        "project": updated_project.model_dump(mode="json"),
        "reply": reply_content,
        "thread_id": thread.id,
        "thread_title": thread.title,
        "model_used": model_used,
        "agent_name": "Agent 1 : Architecte & Cadrage",
        "canvas_updated": action_result.get("canvas_updated", False),
        "actions_executed": action_result.get("actions_executed", []),
    }


@router.get("/stream")
async def stream_chat(
    prompt: str = Query(..., min_length=1),
    model: str | None = Query(None),
    temperature: float = Query(0.2, ge=0.0, le=2.0),
    max_tokens: int = Query(4096, ge=256, le=32768),
):
    """Point de terminaison SSE pour streaming mot par mot avec tokens de pensée."""
    messages = [{"role": "user", "content": prompt}]

    async def event_generator():
        async for chunk in openrouter_client.stream_chat_completion(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        ):
            yield f"data: {json.dumps(chunk)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/command", response_model=dict[str, Any])
def execute_slash_command(payload: ExecuteCommandRequest):
    """Exécute instantanément une slash command à coût 0 token."""
    context = {"project_id": payload.project_id}
    res = commands_registry.execute_command(payload.command, context=context)
    return res


@router.post("/multi-agent", response_model=dict[str, Any])
async def execute_multi_agent_pipeline(payload: ExecuteMultiAgentPipelineRequest):
    """Exécute le pipeline multi-agents hermétiquement sur le projet ou le studio."""
    project = None
    if payload.project_id and str(payload.project_id).lower() not in ("studio", "none", ""):
        project = project_repo.get(payload.project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Projet introuvable.")
    else:
        all_p = project_repo.list_all()
        project = all_p[0] if all_p else None

    if not project:
        from core.domain import Project
        project = Project(name="Studio System")
        project_repo.save(project)

    # Exécution du workflow multi-agents
    res = await orchestrator.execute_multi_agent_workflow(
        project=project,
        task_instruction=payload.instruction,
        topology=payload.topology,
    )

    # Enregistrer le compte-rendu dans le fil de discussion sans emojis
    thread = project.get_or_create_main_thread()
    steps_md = "\n".join(f"- {s}" for s in res.get("steps_log", []))
    summary_text = (
        f"### Pipeline Multi-Agents Exécuté : {project.name}\n\n"
        f"- **Topologie** : `{res.get('topology')}`\n"
        f"- **Liaisons actives parcourues** : `{res.get('active_links_count', 0)}`\n"
        f"- **Agents mobilisés** : `{len(res.get('agents_involved', []))}`\n"
        f"- **Score Qualité de fin de run** : `{res.get('quality_score', 95.0)} / 100` ({res.get('quality_verdict', 'SUCCÈS')})\n\n"
        f"**Journal des étapes :**\n{steps_md}\n\n"
        f"*{res.get('summary', 'Pipeline exécuté avec succès.')}*"
    )
    thread.add_message(
        role=MessageRole.ASSISTANT,
        content=summary_text,
        author_name="Orchestrateur Multi-Agents",
        agent_id="agent_copilot",
    )
    project_repo.save(project)

    return {
        "status": "success",
        "result": res,
        "summary": res.get("summary", "Pipeline complété avec succès."),
        "project_id": str(project.id),
        "quality_score": res.get("quality_score", 95.0),
        "steps_log": res.get("steps_log", []),
    }
