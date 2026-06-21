"""
MCP API routes.

  GET  /mcp/servers              → list all registered servers
  POST /mcp/servers              → register a new server (admin only)
  POST /mcp/connect              → connect current user to a server
  POST /mcp/disconnect           → disconnect current user from a server
  GET  /mcp/status               → list current user's connection statuses
  POST /mcp/servers/{name}/sync  → upsert tool cache for a server (admin only)
  GET  /mcp/servers/{name}/tools → read cached tools for a server
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from api.auth.dependencies import get_current_user
from api.mcp.models import (
    MCPServerCreate, MCPServerResponse,
    MCPConnectRequest, MCPDisconnectRequest, MCPConnectionResponse,
    MCPToolResponse,
)

router = APIRouter(tags=["mcp"])


# ------------------------------------------------------------------
# Server management (admin only)
# ------------------------------------------------------------------

@router.get("/servers", response_model=list[MCPServerResponse])
async def list_servers(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    mcp_service = request.app.state.mcp_service
    servers = await mcp_service.list_servers()
    return [MCPServerResponse(**s) for s in servers]


@router.post("/servers", response_model=MCPServerResponse)
async def register_server(
    body: MCPServerCreate,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    auth_service = request.app.state.auth_service
    if not await auth_service.has_admin_role(current_user["id"]):
        raise HTTPException(status_code=403, detail="Only admins can register MCP servers")

    mcp_service = request.app.state.mcp_service
    try:
        server = await mcp_service.register_server(
            name=body.name,
            display_name=body.display_name,
            server_url=body.server_url,
            transport=body.transport,
            startup_timeout_sec=body.startup_timeout_sec,
            supports_oauth=body.supports_oauth,
            enabled=body.enabled,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    return MCPServerResponse(**server)


# ------------------------------------------------------------------
# Tool cache management (admin only)
# ------------------------------------------------------------------

@router.post("/servers/{server_name}/sync")
async def sync_server_tools(
    server_name: str,
    tools: list[dict],          # Caller passes [{ tool_name, description, schema }]
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """Replace the cached tool list for a server.

    Call this after MCP discovery. Runtime reads from DB — no live network call.
    """
    auth_service = request.app.state.auth_service
    if not await auth_service.has_admin_role(current_user["id"]):
        raise HTTPException(status_code=403, detail="Only admins can sync MCP tools")

    mcp_service = request.app.state.mcp_service
    try:
        count = await mcp_service.sync_tools(server_name, tools)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return {"detail": f"Synced {count} tools for server '{server_name}'"}


@router.post("/servers/{server_name}/discover")
async def discover_server_tools(
    server_name: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """Connect to the live MCP server, discover its tools, and cache them in DB.

    Admin only. Takes up to startup_timeout_sec seconds to complete.
    """
    auth_service = request.app.state.auth_service
    if not await auth_service.has_admin_role(current_user["id"]):
        raise HTTPException(status_code=403, detail="Only admins can run tool discovery")

    mcp_service = request.app.state.mcp_service
    try:
        count = await mcp_service.discover_and_sync(server_name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Discovery failed: {e}")

    return {"detail": f"Discovered and synced {count} tools for server '{server_name}'"}


@router.get("/servers/{server_name}/tools", response_model=list[MCPToolResponse])
async def get_server_tools(
    server_name: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """Return the cached tool definitions stored for this server."""
    mcp_service = request.app.state.mcp_service
    try:
        tools = await mcp_service.get_server_tools(server_name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return [MCPToolResponse(**t) for t in tools]


# ------------------------------------------------------------------
# User connection management
# ------------------------------------------------------------------

@router.post("/connect", response_model=MCPConnectionResponse)
async def connect(
    body: MCPConnectRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    mcp_service = request.app.state.mcp_service
    try:
        conn = await mcp_service.connect_for_user(current_user["id"], body.server_name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return MCPConnectionResponse(**conn)


@router.post("/disconnect", response_model=MCPConnectionResponse)
async def disconnect(
    body: MCPDisconnectRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    mcp_service = request.app.state.mcp_service
    try:
        conn = await mcp_service.disconnect_for_user(current_user["id"], body.server_name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return MCPConnectionResponse(**conn)


@router.get("/status", response_model=list[MCPConnectionResponse])
async def user_status(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """Return all connection statuses for the current user."""
    mcp_service = request.app.state.mcp_service
    connections = await mcp_service.get_user_connections(current_user["id"])
    return [MCPConnectionResponse(**c) for c in connections]
