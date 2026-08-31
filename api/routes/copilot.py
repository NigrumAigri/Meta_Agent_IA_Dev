from __future__ import annotations

from typing import Any
from fastapi import APIRouter, status
from pydantic import BaseModel, ConfigDict, Field

from core.domain import MessageRole, SystemCopilotMessage
from storage.repository import agent_repo, project_repo
from services.openrouter_client import openrouter_client
from services.prompt_compiler import prompt_compiler

router = APIRouter(prefix="/api/v1/copilot", tags=["Méta-Agent Copilote Système"])


class CopilotChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=1)


@router.get("/messages", response_model=list[dict[str, Any]])
def list_copilot_messages():
    """Récupère l'historique étanche des discussions avec le Copilote Système."""
    messages = project_repo.list_system_copilot_messages()
    return [m.model_dump(mode="json") for m in messages]


@router.post("/chat", response_model=dict[str, Any])
async def chat_with_copilot(payload: CopilotChatRequest):
    """Dialogue en direct avec l'Agent 5 Copilote Système permanent."""
    # 1. Enregistrer le message utilisateur
    user_msg = SystemCopilotMessage(
        role=MessageRole.USER,
        content=payload.message,
        author_name="Administrateur",
    )
    project_repo.add_system_copilot_message(user_msg)

    # 2. Récupérer l'agent Copilote
    copilot_agent = agent_repo.get("agent_copilot")
    system_prompt = (
        prompt_compiler.compile_agent_system_prompt(copilot_agent)
        if copilot_agent
        else "Tu es le Méta-Agent Copilote Système transverse."
    )

    # 3. Préparer l'historique
    history = project_repo.list_system_copilot_messages(limit=10)
    messages_payload = [{"role": "system", "content": system_prompt}]
    for m in history:
        messages_payload.append({
            "role": "user" if m.role == MessageRole.USER else "assistant",
            "content": m.content,
        })

    # 4. Inférence
    reply_text, metric, _ = await openrouter_client.generate_chat_completion(
        messages=messages_payload,
        model=copilot_agent.model if copilot_agent else None,
        temperature=0.1,
        agent_id="agent_copilot",
        agent_name="Méta-Agent Copilote Système",
        project_name="Copilote Global",
        task_name="Assistance Système",
    )

    # 5. Enregistrer la réponse
    assistant_msg = SystemCopilotMessage(
        role=MessageRole.ASSISTANT,
        content=reply_text,
        author_name="Méta-Agent Copilote",
    )
    project_repo.add_system_copilot_message(assistant_msg)

    return {
        "status": "success",
        "reply": reply_text,
        "metric": metric.model_dump(mode="json"),
    }


@router.delete("/messages", status_code=status.HTTP_204_NO_CONTENT)
def clear_copilot_messages():
    """Réinitialise l'historique de discussion du Copilote Système."""
    project_repo.clear_system_copilot_messages()
