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
import logging
import os
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from api.auth.dependencies import get_current_user
from api.mcp.models import (
    MCPServerCreate, MCPServerResponse,
    MCPConnectRequest, MCPDisconnectRequest, MCPConnectionResponse,
    MCPToolResponse, OAuthCallbackRequest, OAuthTokenStatusResponse,
    OAuthStartRequest, OAuthStartResponse,
)
from api.mcp.oauth_flow import (
    build_authorization_flow,
    dumps_flow,
    exchange_authorization_code,
    loads_flow,
)

router = APIRouter(tags=["mcp"])
logger = logging.getLogger(__name__)


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


# ------------------------------------------------------------------
# OAuth token management (user-scoped)
# ------------------------------------------------------------------

@router.post("/oauth/start", response_model=OAuthStartResponse)
async def oauth_start(
    body: OAuthStartRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """Start the MCP OAuth browser flow and return the provider authorization URL."""
    mcp_service = request.app.state.mcp_service
    try:
        server = await mcp_service.get_server(body.server_name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    if not server.get("supports_oauth"):
        raise HTTPException(status_code=400, detail="MCP server does not support OAuth")

    callback_url = str(request.url_for("oauth_browser_callback"))
    try:
        flow = await build_authorization_flow(server["server_url"], callback_url)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"OAuth discovery failed: {e}")

    flow.update({
        "user_id": current_user["id"],
        "server_name": body.server_name,
        "frontend_redirect_url": body.frontend_redirect_url,
    })
    await request.app.state.redis.setex(
        f"mcp_oauth_state:{flow['state']}",
        600,
        dumps_flow(flow),
    )
    return OAuthStartResponse(
        server_name=body.server_name,
        authorization_url=flow["authorization_url"],
    )


@router.get("/oauth/callback", name="oauth_browser_callback")
async def oauth_browser_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
):
    """OAuth provider redirect endpoint; exchanges code and stores encrypted tokens."""
    if not state:
        raise HTTPException(status_code=400, detail="Missing OAuth state")

    raw_flow = await request.app.state.redis.get(f"mcp_oauth_state:{state}")
    if not raw_flow:
        raise HTTPException(status_code=400, detail="OAuth state expired or invalid")
    await request.app.state.redis.delete(f"mcp_oauth_state:{state}")

    flow = loads_flow(raw_flow)
    frontend_redirect_url = flow.get("frontend_redirect_url")
    if error:
        return _oauth_redirect(frontend_redirect_url, error=error)
    if not code:
        return _oauth_redirect(frontend_redirect_url, error="missing_code")

    try:
        token_payload = await exchange_authorization_code(flow, code)
        from datetime import datetime, timedelta

        expires_at = None
        if token_payload.get("expires_in") is not None:
            expires_at = datetime.utcnow() + timedelta(seconds=int(token_payload["expires_in"]))

        await request.app.state.mcp_service.store_oauth_tokens(
            user_id=flow["user_id"],
            server_name=flow["server_name"],
            access_token=token_payload["access_token"],
            refresh_token=token_payload.get("refresh_token"),
            token_type=token_payload.get("token_type", "Bearer"),
            expires_at=expires_at,
            provider_user_id=token_payload.get("provider_user_id"),
        )
    except Exception as e:
        return _oauth_redirect(frontend_redirect_url, error=str(e))

    # Auto-discover tools using the fresh access token so they appear immediately.
    # Non-fatal: a failed sync never blocks the successful auth redirect.
    try:
        await request.app.state.mcp_service.discover_and_sync(
            flow["server_name"],
            auth_token=token_payload["access_token"],
        )
    except Exception as exc:
        logger.warning("Post-OAuth tool discovery failed for '%s': %s", flow["server_name"], exc)

    return _oauth_redirect(frontend_redirect_url, server=flow["server_name"], connected="1")

@router.post("/oauth/callback", response_model=MCPConnectionResponse)
async def oauth_callback(
    body: OAuthCallbackRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """Receive an OAuth access token after a successful OAuth flow and store it encrypted.

    The frontend completes the OAuth redirect, extracts the token, and POSTs
    it here. The server encrypts it with Fernet (MCP_ENCRYPTION_KEY) before
    writing to mcp_credentials. The connection status is set to 'connected'.
    """
    from datetime import datetime, timedelta

    expires_at: datetime | None = None
    if body.expires_in is not None:
        expires_at = datetime.utcnow() + timedelta(seconds=body.expires_in)

    mcp_service = request.app.state.mcp_service
    try:
        conn = await mcp_service.store_oauth_tokens(
            user_id=current_user["id"],
            server_name=body.server_name,
            access_token=body.access_token,
            refresh_token=body.refresh_token,
            token_type=body.token_type,
            expires_at=expires_at,
            provider_user_id=body.provider_user_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        # MCP_ENCRYPTION_KEY missing
        raise HTTPException(status_code=500, detail=str(e))

    return MCPConnectionResponse(**conn)


@router.get("/oauth/token-status/{server_name}", response_model=OAuthTokenStatusResponse)
async def oauth_token_status(
    server_name: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """Return token expiry metadata for the current user's OAuth connection.

    Never returns the decrypted token — only whether one exists and if it has expired.
    """
    mcp_service = request.app.state.mcp_service
    try:
        status = await mcp_service.get_oauth_token_status(current_user["id"], server_name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return OAuthTokenStatusResponse(server_name=server_name, **status)


def _oauth_redirect(frontend_redirect_url: str | None, **params: str) -> RedirectResponse:
    target = frontend_redirect_url or os.environ.get("FRONTEND_URL") or "http://localhost:3000/mcp"
    clean_params = {k: v for k, v in params.items() if v}
    separator = "&" if "?" in target else "?"
    redirect_url = f"{target}{separator}{urlencode(clean_params)}"
    logger.info("Redirecting MCP OAuth callback to %s", redirect_url)
    return RedirectResponse(redirect_url, status_code=303)
