import asyncio
from typing import Any
import logging
from config.config import Config
from tools.mcp.client import MCPClient, MCPServerStatus
from tools.mcp.mcp_tool import MCPTool
from tools.registry import ToolRegistry


logger = logging.getLogger(__name__)

# Manages the 'n' MCP Clients
class MCPManager:
    def __init__(self, config: Config):
        self.config = config
        self._clients: dict[str, MCPClient] = {}
        self._initialized = False

    async def initialize(self) -> None:
        if self._initialized:
            return

        mcp_configs = self.config.mcp_servers

        if not mcp_configs:
            return

        for name, server_config in mcp_configs.items():
            if not server_config.enabled:
                continue

            self._clients[name] = MCPClient(
                name=name,
                config=server_config,
                cwd=self.config.cwd,
            )

        # Keep server names aligned with gather results for per-server diagnostics.
        connection_jobs = [
            (
                name,
                client,
                asyncio.wait_for(
                    client.connect(),
                    timeout=client.config.startup_timeout_sec,
                ),
            )
            for name, client in self._clients.items()
        ]

        results = await asyncio.gather(
            *(job[2] for job in connection_jobs),
            return_exceptions=True,
        )

        for (name, client, _), result in zip(connection_jobs, results):
            if isinstance(result, Exception):
                if isinstance(result, asyncio.TimeoutError):
                    client.status = MCPServerStatus.ERROR
                    logger.warning(
                        "MCP server '%s' startup timed out after %.1fs",
                        name,
                        client.config.startup_timeout_sec,
                    )
                else:
                    if client.status != MCPServerStatus.ERROR:
                        client.status = MCPServerStatus.ERROR
                    logger.warning(
                        "MCP server '%s' failed to connect: %s: %s",
                        name,
                        type(result).__name__,
                        result,
                    )

        self._initialized = True

    def register_tools(self, registry: ToolRegistry) -> int:
        count = 0

        for client in self._clients.values():
            if client.status != MCPServerStatus.CONNECTED:
                continue

            for tool_info in client.tools:
                mcp_tool = MCPTool(
                    tool_info=tool_info,
                    client=client,
                    config=self.config,
                    name=f"{client.name}__{tool_info.name}",
                )
                registry.register_mcp_tool(mcp_tool)
                count += 1

        return count

    async def shutdown(self) -> None:
        disconnection_tasks = [client.disconnect() for client in self._clients.values()]

        await asyncio.gather(*disconnection_tasks, return_exceptions=True)

        self._clients.clear()
        self._initialized = False

    def get_all_servers(self) -> list[dict[str, Any]]:
        servers = []
        for name, client in self._clients.items():
            server_info = {
                "name": name,
                "status": client.status.value,
                "tools": len(client.tools),
            }
            servers.append(server_info)

        return servers