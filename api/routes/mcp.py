from __future__ import annotations

from typing import Any
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field

from core.domain import McpServerConfig, McpTransport
from storage.repository import mcp_repo
from services.mcp_client import mcp_client
from services.mcp_hub import mcp_hub
from services.tool_rag import tool_rag
from services.docker_sandbox import docker_sandbox

router = APIRouter(prefix="/api/v1/mcp", tags=["Catalogue MCP & Serveurs Externes"])


class AddMcpServerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=2, max_length=100)
    transport: McpTransport = McpTransport.STDIO
    command_or_url: str = Field(min_length=2)
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    project_id: str | None = None


class ExecuteToolRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    arguments: dict[str, Any] = Field(default_factory=dict)
    project_id: str | None = None


@router.get("/tools", response_model=list[dict[str, Any]])
def list_mcp_tools(
    project_id: str | None = Query(default=None),
    active_only: bool = Query(default=False),
):
    """Liste tous les outils MCP enregistrés (globaux et scopés au projet)."""
    tools = mcp_hub.list_tools(project_id=project_id, active_only=active_only)
    return [t.model_dump(mode="json") for t in tools]


@router.get("/tools/search", response_model=list[dict[str, Any]])
def search_mcp_tools_rag(
    q: str = Query(..., min_length=1),
    project_id: str | None = Query(default=None),
    agent_type: str | None = Query(default=None),
    limit: int = Query(default=4, ge=1, le=10),
):
    """Recherche dynamique sémantique et FTS5 d'outils via le Tool RAG."""
    tools = tool_rag.search_relevant_tools(
        query=q,
        agent_type=agent_type,
        project_id=project_id,
        limit=limit,
    )
    return [t.model_dump(mode="json") for t in tools]


@router.get("/servers", response_model=list[dict[str, Any]])
def list_mcp_servers(project_id: str | None = Query(default=None)):
    """Liste tous les serveurs MCP externes configurés."""
    servers = mcp_repo.list_servers(project_id=project_id)
    return [s.model_dump(mode="json") for s in servers]


@router.post("/servers", status_code=status.HTTP_201_CREATED, response_model=dict[str, Any])
async def add_mcp_server(payload: AddMcpServerRequest):
    """Ajoute un serveur MCP externe (stdio ou SSE) et découvre ses outils."""
    server = McpServerConfig(
        name=payload.name,
        transport=payload.transport,
        command_or_url=payload.command_or_url,
        args=payload.args,
        env=payload.env,
        project_id=payload.project_id,
    )
    saved = mcp_repo.save_server(server)

    # Découverte dynamique des outils exposés
    discovered_tools = await mcp_client.connect_and_discover_tools(saved)

    return {
        "server": saved.model_dump(mode="json"),
        "tools_discovered_count": len(discovered_tools),
    }


@router.delete("/servers/{server_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_mcp_server(server_id: str):
    """Supprime un serveur MCP externe."""
    deleted = mcp_repo.delete_server(server_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Serveur MCP introuvable.")


@router.post("/tools/{tool_id}/execute", response_model=dict[str, Any])
def execute_tool(tool_id: str, payload: ExecuteToolRequest):
    """Exécute un outil MCP de manière déterministe avec isolation et troncature."""
    res = mcp_hub.execute_tool(tool_id, payload.arguments, project_id=payload.project_id)
    return res


@router.patch("/tools/{tool_id}/toggle", response_model=dict[str, Any])
def toggle_mcp_tool(tool_id: str):
    """Active ou désactive un outil MCP en temps réel."""
    tool = mcp_hub.get_tool(tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail="Outil MCP introuvable.")
    tool.is_active = not tool.is_active
    mcp_repo.save_tool(tool)
    return {
        "id": tool.id,
        "name": tool.name,
        "is_active": tool.is_active,
        "status": "success",
    }


@router.delete("/tools/{tool_id}", response_model=dict[str, Any])
def delete_mcp_tool(tool_id: str):
    """Supprime un outil MCP personnalisé non-natif."""
    tool = mcp_hub.get_tool(tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail="Outil MCP introuvable.")
    if tool.is_core:
        raise HTTPException(
            status_code=400,
            detail="Impossible de supprimer un outil natif du système. Utilisez l'interrupteur pour le désactiver."
        )
    mcp_repo.delete_tool(tool_id)
    return {"status": "success", "message": f"Outil {tool.name} supprimé avec succès."}


@router.get("/sandbox/status", response_model=dict[str, Any])
def get_sandbox_status():
    """Renvoie le statut en temps réel de la Sandbox Docker et de l'isolation."""
    installed = docker_sandbox.is_docker_installed()
    running = docker_sandbox.is_docker_daemon_running()
    return {
        "docker_installed": installed,
        "docker_daemon_running": running,
        "sandbox_mode": "docker_ephemeral_container" if running else "docker_standby",
        "isolation_level": "READ_ONLY_NO_NETWORK_512MB",
        "image": docker_sandbox.docker_image,
    }
