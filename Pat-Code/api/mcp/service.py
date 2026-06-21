"""
CloudMCPService — all DB operations for MCP servers, connections, and tool syncing.

Design: DB is the single source of truth for tool discovery.
  register_server  → mcp_servers row
  connect_for_user → mcp_user_connections row (status=connected)
  sync_tools       → upsert mcp_tools rows from live discovery
  build_mcp_configs → returns dict[name, MCPServerConfig] for PATService
"""
import uuid
import shlex
import logging
from datetime import datetime
from pathlib import Path

from sqlalchemy import select, delete
from config.config import MCPServerConfig as ConfigMCPServerConfig
from tools.mcp.client import MCPClient
from api.db.database import CloudDatabase
from api.db.models import (
    MCPServer, MCPServerScope, MCPUserConnection,
    MCPCredential, MCPServerConfig, MCPTool, AuditLog,
)

logger = logging.getLogger(__name__)

# Valid status transitions the API can set
VALID_STATUSES = {"connected", "disconnected", "disabled", "error", "expired", "refresh_required"}


class CloudMCPService:
    def __init__(self, db: CloudDatabase):
        self.db = db

    async def register_server(
        self,
        name: str,
        display_name: str,
        server_url: str,
        transport: str,
        startup_timeout_sec: int = 30,
        supports_oauth: bool = False,
        enabled: bool = True,
    ) -> dict:
        async with self.db.get_session() as session:
            server = MCPServer(
                name=name,
                display_name=display_name,
                server_url=server_url,
                transport=transport,
                startup_timeout_sec=startup_timeout_sec,
                supports_oauth=supports_oauth,
                enabled=enabled,
            )
            session.add(server)
            await session.commit()
            await session.refresh(server)
            return self._server_to_dict(server)

    async def list_servers(self) -> list[dict]:
        """Return all registered MCP servers regardless of enabled state."""
        async with self.db.get_session() as session:
            result = await session.execute(select(MCPServer).order_by(MCPServer.name))
            return [self._server_to_dict(s) for s in result.scalars().all()]

    # ------------------------------------------------------------------
    # User connection management
    # ------------------------------------------------------------------

    async def connect_for_user(self, user_id: str, server_name: str) -> dict:
        """Create or update a connection record and set status=connected."""
        async with self.db.get_session() as session:
            server = await self._get_server_by_name(session, server_name)
            conn = await self._get_or_create_connection(session, user_id, server.id)

            conn.status = "connected"
            conn.connected_at = datetime.utcnow()
            conn.last_used_at = datetime.utcnow()

            session.add(AuditLog(
                user_id=uuid.UUID(user_id),
                action="MCP_CONNECTED",
                metadata_json={"server": server_name},
            ))

            await session.commit()
            await session.refresh(conn)
            return self._connection_to_dict(conn, server.name)

    async def disconnect_for_user(self, user_id: str, server_name: str) -> dict:
        """Set connection status to disconnected."""
        async with self.db.get_session() as session:
            server = await self._get_server_by_name(session, server_name)
            conn = await self._require_connection(session, user_id, server.id)

            conn.status = "disconnected"

            session.add(AuditLog(
                user_id=uuid.UUID(user_id),
                action="MCP_DISCONNECTED",
                metadata_json={"server": server_name},
            ))

            await session.commit()
            await session.refresh(conn)
            return self._connection_to_dict(conn, server.name)

    async def get_user_connections(self, user_id: str) -> list[dict]:
        """Return all connection records for a user with their server name."""
        async with self.db.get_session() as session:
            result = await session.execute(
                select(MCPUserConnection, MCPServer.name)
                .join(MCPServer, MCPServer.id == MCPUserConnection.mcp_server_id)
                .where(MCPUserConnection.user_id == uuid.UUID(user_id))
            )
            return [
                self._connection_to_dict(conn, server_name)
                for conn, server_name in result.all()
            ]

    # ------------------------------------------------------------------
    # Tool sync — the core performance feature
    # ------------------------------------------------------------------

    async def sync_tools(self, server_name: str, tools: list[dict]) -> int:
        """Upsert a batch of tool definitions into mcp_tools.

        Each dict must contain: tool_name, description, schema.
        Old tools for this server are deleted and replaced atomically.
        Returns the count of tools stored.
        """
        async with self.db.get_session() as session:
            server = await self._get_server_by_name(session, server_name)

            # Delete all previous tool snapshots for this server
            await session.execute(
                delete(MCPTool).where(MCPTool.mcp_server_id == server.id)
            )

            # Insert fresh snapshot
            for tool_data in tools:
                session.add(MCPTool(
                    mcp_server_id=server.id,
                    tool_name=tool_data["tool_name"],
                    description=tool_data.get("description"),
                    schema=tool_data.get("schema"),
                ))

            await session.commit()
            logger.info(f"Synced {len(tools)} tools for MCP server '{server_name}'")
            return len(tools)

    async def get_server_tools(self, server_name: str) -> list[dict]:
        """Return cached tool definitions for a given server."""
        async with self.db.get_session() as session:
            server = await self._get_server_by_name(session, server_name)
            result = await session.execute(
                select(MCPTool)
                .where(MCPTool.mcp_server_id == server.id)
                .order_by(MCPTool.tool_name)
            )
            return [self._tool_to_dict(t) for t in result.scalars().all()]

    async def discover_and_sync(self, server_name: str) -> int:
        """Connect to the live MCP server, list its tools, persist them to mcp_tools.

        Uses MCPClient directly so no Agent or Config is needed.
        The client is disconnected immediately after discovery.
        Returns the number of tools synced.
        """
        # Extract plain scalars inside the session — ORM attrs become detached after close.
        async with self.db.get_session() as session:
            server = await self._get_server_by_name(session, server_name)
            server_url = server.server_url
            transport = server.transport
            timeout = server.startup_timeout_sec or 30

        is_url_transport = transport in ("sse", "http", "streamable-http")
        if is_url_transport:
            server_config = ConfigMCPServerConfig(
                startup_timeout_sec=timeout,
                url=server_url,
                transport=transport,
            )
        else:
            # server_url is stored as a full shell command string, e.g.
            # "npx @modelcontextprotocol/server-filesystem /tmp"
            # StdioTransport requires command (executable) and args (list) separately.
            parts = shlex.split(server_url)
            server_config = ConfigMCPServerConfig(
                startup_timeout_sec=timeout,
                command=parts[0],
                args=parts[1:],
            )

        client = MCPClient(name=server_name, config=server_config, cwd=Path.cwd())
        try:
            await client.connect()
            tools = [
                {
                    "tool_name": t.name,
                    "description": t.description,
                    "schema": t.input_schema,
                }
                for t in client.tools
            ]
        finally:
            await client.disconnect()

        return await self.sync_tools(server_name, tools)




    async def build_mcp_configs(self, user_id: str) -> dict[str, ConfigMCPServerConfig]:
        """Translate DB rows into the MCPServerConfig objects that Config expects.

        Only connections with status='connected' are included.
        MCPManager consumes Config.mcp_servers as-is — no changes needed there.
        """
        async with self.db.get_session() as session:
            result = await session.execute(
                select(MCPUserConnection, MCPServer)
                .join(MCPServer, MCPServer.id == MCPUserConnection.mcp_server_id)
                .where(
                    MCPUserConnection.user_id == uuid.UUID(user_id),
                    MCPUserConnection.status == "connected",
                    MCPServer.enabled == True,
                )
            )
            configs: dict[str, ConfigMCPServerConfig] = {}
            for conn, server in result.all():
                is_url_transport = server.transport in ("sse", "http", "streamable-http")
                if is_url_transport:
                    cfg = ConfigMCPServerConfig(
                        startup_timeout_sec=server.startup_timeout_sec or 30,
                        url=server.server_url,
                        transport=server.transport,
                    )
                else:
                    parts = shlex.split(server.server_url)
                    cfg = ConfigMCPServerConfig(
                        startup_timeout_sec=server.startup_timeout_sec or 30,
                        command=parts[0],
                        args=parts[1:],
                    )
                configs[server.name] = cfg
            return configs

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _get_server_by_name(self, session, name: str) -> MCPServer:
        result = await session.execute(select(MCPServer).where(MCPServer.name == name))
        server = result.scalar_one_or_none()
        if not server:
            raise ValueError(f"MCP server not found: {name}")
        return server

    async def _get_or_create_connection(
        self, session, user_id: str, server_id: uuid.UUID
    ) -> MCPUserConnection:
        """Fetch existing connection or create a new disconnected one."""
        result = await session.execute(
            select(MCPUserConnection).where(
                MCPUserConnection.user_id == uuid.UUID(user_id),
                MCPUserConnection.mcp_server_id == server_id,
            )
        )
        conn = result.scalar_one_or_none()
        if not conn:
            conn = MCPUserConnection(
                user_id=uuid.UUID(user_id),
                mcp_server_id=server_id,
            )
            session.add(conn)
            await session.flush()  
        return conn

    async def _require_connection(
        self, session, user_id: str, server_id: uuid.UUID
    ) -> MCPUserConnection:
        """Like _get_or_create but raises if connection doesn't exist yet."""
        result = await session.execute(
            select(MCPUserConnection).where(
                MCPUserConnection.user_id == uuid.UUID(user_id),
                MCPUserConnection.mcp_server_id == server_id,
            )
        )
        conn = result.scalar_one_or_none()
        if not conn:
            raise ValueError("No existing connection found. Call /mcp/connect first.")
        return conn

    @staticmethod
    def _server_to_dict(s: MCPServer) -> dict:
        return {
            "id": str(s.id),
            "name": s.name,
            "display_name": s.display_name,
            "server_url": s.server_url,
            "transport": s.transport,
            "startup_timeout_sec": s.startup_timeout_sec,
            "supports_oauth": s.supports_oauth,
            "enabled": s.enabled,
            "created_at": s.created_at.isoformat(),
        }

    @staticmethod
    def _connection_to_dict(conn: MCPUserConnection, server_name: str) -> dict:
        return {
            "id": str(conn.id),
            "user_id": str(conn.user_id),
            "mcp_server_id": str(conn.mcp_server_id),
            "server_name": server_name,
            "status": conn.status,
            "connected_at": conn.connected_at.isoformat() if conn.connected_at else None,
            "last_used_at": conn.last_used_at.isoformat() if conn.last_used_at else None,
        }

    @staticmethod
    def _tool_to_dict(t: MCPTool) -> dict:
        return {
            "id": str(t.id),
            "mcp_server_id": str(t.mcp_server_id),
            "tool_name": t.tool_name,
            "description": t.description,
            "schema": t.schema,
            "updated_at": t.updated_at.isoformat() if t.updated_at else None,
        }
