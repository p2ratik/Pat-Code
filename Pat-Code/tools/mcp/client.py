from dataclasses import dataclass, field
from enum import Enum
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from config.config import MCPServerConfig
from fastmcp import Client
from fastmcp.client.auth import BearerAuth, OAuth
from fastmcp.client.transports import (
    SSETransport,
    StdioTransport,
    StreamableHttpTransport,
)


class MCPServerStatus(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


@dataclass
class MCPToolInfo:

    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)
    server_name: str = ""


class MCPClient:
    def __init__(
        self,
        name: str,
        config: MCPServerConfig,
        cwd: Path,
    ) -> None:
        self.name = name
        self.config = config
        self.cwd = cwd
        self.status = MCPServerStatus.DISCONNECTED
        self._client: Client | None = None

        self._tools: dict[str, MCPToolInfo] = dict()

    @property
    def tools(self) -> list[MCPToolInfo]:
        return list(self._tools.values())

    def _build_auth(
        self,
    ) -> httpx.Auth | None:
        """Resolve the authentication handler for URL-based transports.

        Priority order:
        1. ``oauth`` config — uses fastmcp's ``OAuth`` helper, which supports
           both the MCP OAuth discovery flow (interactive / headless) and the
           OAuth2 client-credentials grant when ``client_id`` + ``client_secret``
           are provided.
        2. ``auth_token`` shorthand — wraps the pre-obtained token in a
           ``BearerAuth`` handler (i.e. ``Authorization: Bearer <token>``).
        3. ``None`` — no authentication; raw ``headers`` are still forwarded
           by the transport layer.
        """
        if self.config.oauth:
            oauth_cfg = self.config.oauth
            return OAuth(
                mcp_url=str(self.config.url),
                client_id=oauth_cfg.client_id,
                client_secret=oauth_cfg.client_secret,
                scopes=oauth_cfg.scopes or None,
            )

        if self.config.auth_token:
            return BearerAuth(token=self.config.auth_token)

        return None

    def _resolve_url_transport(
        self,
        url: str,
    ) -> SSETransport | StreamableHttpTransport:
        """Pick the correct HTTP transport for a URL-based MCP server.

        Resolution order:
        1. Explicit ``transport`` field in config (highest priority).
        2. URL *path* heuristic: path component ends with ``/sse`` — uses
           ``SSETransport``.  The check uses :func:`urllib.parse.urlparse` so
           query-strings never interfere with the match.
        3. Default: ``StreamableHttpTransport``.
        """
        # Merge explicit headers and inject Bearer token header if needed.
        # Note: auth takes priority for token injection; headers are additive.
        headers: dict[str, str] = dict(self.config.headers)

        auth = self._build_auth()

        transport_kwargs: dict[str, Any] = {
            "url": url,
            "headers": headers or None,
            "auth": auth,
        }

        # Explicit declaration wins — no heuristic needed.
        if self.config.transport == "sse":
            return SSETransport(**transport_kwargs)
        if self.config.transport == "streamable-http":
            return StreamableHttpTransport(**transport_kwargs)

        # Heuristic fallback: inspect only the URL *path* component so that
        # query-strings (e.g. ?token=...) do not break the suffix check.
        parsed_path = urlparse(url).path.rstrip("/")
        if parsed_path.endswith("/sse"):
            return SSETransport(**transport_kwargs)

        return StreamableHttpTransport(**transport_kwargs)

    def _create_transport(
        self,
    ) -> StdioTransport | SSETransport | StreamableHttpTransport:
        if self.config.command:
            env = os.environ.copy()
            env.update(self.config.env)

            return StdioTransport(
                command=self.config.command,
                args=list(self.config.args),
                env=env,
                cwd=str(self.config.cwd or self.cwd),
                log_file=Path(os.devnull),
            )

        if self.config.url:
            return self._resolve_url_transport(str(self.config.url).strip())

        raise ValueError(
            "MCP client requires either command (stdio) or url (http/sse) transport"
        )

    async def connect(self) -> None:
        if self.status == MCPServerStatus.CONNECTED:
            return

        self.status = MCPServerStatus.CONNECTING

        try:
            self._client = Client(transport=self._create_transport())

            await self._client.__aenter__()

            tool_result = await self._client.list_tools()
            for tool in tool_result:

                # Craeting the tool Info class from the returned tools from the MCP server
                self._tools[tool.name] = MCPToolInfo(
                    name=tool.name,
                    description=tool.description or "",
                    input_schema=(
                        tool.inputSchema if hasattr(tool, "inputSchema") else {}
                    ),
                    server_name=self.name,
                )

            self.status = MCPServerStatus.CONNECTED
        except Exception:
            self.status = MCPServerStatus.ERROR
            raise

    async def disconnect(self) -> None:
        if self._client:
            await self._client.__aexit__(None, None, None)
            self._client = None

        self._tools.clear()
        self.status = MCPServerStatus.DISCONNECTED

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]):
        if not self._client or self.status != MCPServerStatus.CONNECTED:
            raise RuntimeError(f"Not connected to server {self.name}")

        result = await self._client.call_tool(tool_name, arguments)

        output = []
        for item in result.content:
            if hasattr(item, "text"):
                output.append(item.text)
            else:
                output.append(str(item))

        return {
            "output": "\n".join(output),
            "is_error": result.is_error,
        }