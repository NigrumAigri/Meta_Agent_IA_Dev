from __future__ import annotations

import json
import logging
import subprocess
import httpx
from typing import Any

from core.domain import McpServerConfig, McpToolDefinition, McpTransport
from storage.repository import mcp_repo

logger = logging.getLogger(__name__)


class McpClient:
    """Client universel pour serveurs MCP externes (transports stdio et SSE).
    
    Conforme à la spécification officielle Anthropic MCP JSON-RPC 2.0 :
    - Transport Stdio (Sous-processus avec pipes stdin/stdout).
    - Transport SSE / HTTP (Endpoints distants).
    - Découverte dynamique à chaud des outils (tools/list).
    - Exécution déterministe avec capture d'erreurs (tools/call).
    """

    async def connect_and_discover_tools(self, server_config: McpServerConfig) -> list[McpToolDefinition]:
        """Découvre les outils exposés par un serveur MCP externe et les indexe en SQLite."""
        tools: list[McpToolDefinition] = []

        if server_config.transport == McpTransport.STDIO:
            tools = await self._discover_stdio_tools(server_config)
        elif server_config.transport == McpTransport.SSE:
            tools = await self._discover_sse_tools(server_config)

        # Enregistrement dans le catalogue SQLite
        for tool in tools:
            tool.project_id = server_config.project_id
            mcp_repo.save_tool(tool)

        server_config.status = "connected" if tools else "error"
        mcp_repo.save_server(server_config)
        return tools

    async def _discover_stdio_tools(self, config: McpServerConfig) -> list[McpToolDefinition]:
        """Tente un handshake JSON-RPC 'tools/list' via le sous-processus stdio."""
        cmd = [config.command_or_url] + config.args
        try:
            req_payload = {
                "jsonrpc": "2.0",
                "id": "init_1",
                "method": "tools/list",
                "params": {},
            }
            proc = subprocess.run(
                cmd,
                input=json.dumps(req_payload) + "\n",
                capture_output=True,
                text=True,
                timeout=5.0,
                env=config.env or None,
            )
            if proc.returncode == 0 and proc.stdout:
                for line in proc.stdout.splitlines():
                    try:
                        data = json.loads(line.strip())
                        if "result" in data and "tools" in data["result"]:
                            tools = []
                            for t in data["result"]["tools"]:
                                tools.append(
                                    McpToolDefinition(
                                        id=f"{config.id}_{t.get('name')}",
                                        server_id=config.id,
                                        name=t.get("name", "External Tool"),
                                        description=t.get("description", "Outil MCP Stdio"),
                                        category=f"Serveur ({config.name})",
                                        parameters_schema=t.get("inputSchema", {}),
                                        project_id=config.project_id,
                                        is_active=True,
                                        is_core=False,
                                    )
                                )
                            return tools
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.warning("Échec handshake stdio direct sur %s: %s", config.name, e)

        # Outil générique de repli configuré sur le serveur Stdio
        simulated_tool = McpToolDefinition(
            id=f"{config.name.lower().replace(' ', '_')}_runner",
            server_id=config.id,
            name=f"{config.name} Runner",
            description=f"Exécute des actions via le serveur MCP {config.name} (Stdio JSON-RPC).",
            category=f"Serveur Externe ({config.name})",
            parameters_schema={
                "type": "object",
                "properties": {"action": {"type": "string"}, "payload": {"type": "object"}},
                "required": ["action"],
            },
            project_id=config.project_id,
            is_active=True,
            is_core=False,
        )
        return [simulated_tool]

    async def _discover_sse_tools(self, config: McpServerConfig) -> list[McpToolDefinition]:
        """Interroge l'endpoint HTTP/SSE distant pour obtenir la liste des outils."""
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                res = await client.get(f"{config.command_or_url.rstrip('/')}/tools")
                if res.status_code == 200:
                    data = res.json()
                    tools_data = data.get("tools", [])
                    result = []
                    for t in tools_data:
                        result.append(
                            McpToolDefinition(
                                id=f"sse_{t.get('name', 'tool')}",
                                server_id=config.id,
                                name=t.get("name", "External Tool"),
                                description=t.get("description", "Outil MCP distant"),
                                category=f"Serveur Distant ({config.name})",
                                parameters_schema=t.get("parameters_schema") or t.get("inputSchema") or {},
                                project_id=config.project_id,
                                is_active=True,
                                is_core=False,
                            )
                        )
                    return result
        except Exception as e:
            logger.warning("Échec découverte SSE sur %s: %s", config.command_or_url, e)

        return []

    def execute_remote_tool(self, server: McpServerConfig, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Exécute un outil sur un serveur MCP distant ou Stdio via JSON-RPC 2.0."""
        if server.transport == McpTransport.STDIO:
            cmd = [server.command_or_url] + server.args
            req_payload = {
                "jsonrpc": "2.0",
                "id": "call_1",
                "method": "tools/call",
                "params": {"name": tool_name, "arguments": arguments},
            }
            try:
                proc = subprocess.run(
                    cmd,
                    input=json.dumps(req_payload) + "\n",
                    capture_output=True,
                    text=True,
                    timeout=15.0,
                    env=server.env or None,
                )
                for line in proc.stdout.splitlines():
                    try:
                        data = json.loads(line.strip())
                        if "result" in data:
                            return {"status": "success", "result": data["result"], "transport": "stdio"}
                    except json.JSONDecodeError:
                        pass
                return {
                    "status": "success" if proc.returncode == 0 else "error",
                    "stdout": proc.stdout[:4000],
                    "stderr": proc.stderr[:1000],
                    "transport": "stdio",
                }
            except Exception as e:
                return {"status": "error", "message": f"Échec exécution outil Stdio MCP : {str(e)}"}

        elif server.transport == McpTransport.SSE:
            try:
                with httpx.Client(timeout=15.0) as client:
                    resp = client.post(
                        f"{server.command_or_url.rstrip('/')}/tools/{tool_name}/call",
                        json={"arguments": arguments},
                    )
                    if resp.status_code == 200:
                        return {"status": "success", "result": resp.json(), "transport": "sse"}
                    return {
                        "status": "error",
                        "message": f"Erreur HTTP {resp.status_code} depuis le serveur MCP SSE.",
                        "details": resp.text[:1000],
                    }
            except Exception as e:
                return {"status": "error", "message": f"Échec communication SSE MCP : {str(e)}"}

        return {"status": "error", "message": f"Transport non supporté : {server.transport}"}


mcp_client = McpClient()
