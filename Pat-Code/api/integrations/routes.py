from fastapi import APIRouter, Depends, HTTPException, Request, Query
from api.auth.dependencies import get_current_user
from api.integrations.models import (
    IntegrationProviderCreate,
    IntegrationProviderUpdate,
    IntegrationProviderResponse,
    IntegrationConnectionResponse,
    OAuthInitiateRequest,
    OAuthInitiateResponse,
    OAuthCallbackRequest,
    OAuthCallbackResponse,
    ScopeUpgradeRequest,
    ScopeUpgradeResponse,
)

router = APIRouter(tags=["integrations"])


@router.get("/providers", response_model=list[IntegrationProviderResponse])
async def list_providers(request: Request, current_user: dict = Depends(get_current_user)):
    svc = request.app.state.integration_service
    return await svc.list_providers()


@router.post("/providers", response_model=IntegrationProviderResponse)
async def create_provider(
    body: IntegrationProviderCreate,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    svc = request.app.state.integration_service
    try:
        return await svc.create_provider(body)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/providers/{name}", response_model=IntegrationProviderResponse)
async def update_provider(
    name: str,
    body: IntegrationProviderUpdate,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    svc = request.app.state.integration_service
    provider = await svc.update_provider(name, body)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    return provider


@router.get("/connections", response_model=list[IntegrationConnectionResponse])
async def get_connections(request: Request, current_user: dict = Depends(get_current_user)):
    conn_mgr = request.app.state.connection_manager
    return await conn_mgr.get_connections(current_user["id"])


@router.delete("/connections/{provider_name}")
async def disconnect(
    provider_name: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    conn_mgr = request.app.state.connection_manager
    try:
        return await conn_mgr.disconnect(current_user["id"], provider_name)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/oauth/initiate", response_model=OAuthInitiateResponse)
async def initiate_oauth(
    body: OAuthInitiateRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    conn_mgr = request.app.state.connection_manager
    try:
        return await conn_mgr.initiate_oauth(
            current_user["id"],
            body.provider_name,
            body.redirect_uri,
            requested_tools=body.requested_tools,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/oauth/callback", response_model=OAuthCallbackResponse)
async def oauth_callback(
    body: OAuthCallbackRequest,
    request: Request,
):
    """State param encodes the user_id — no JWT auth needed on this endpoint."""
    conn_mgr = request.app.state.connection_manager
    try:
        return await conn_mgr.handle_callback(body.code, body.state, body.redirect_uri)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/oauth/callback", response_model=OAuthCallbackResponse)
async def oauth_callback_get(
    request: Request,
    code: str = Query(...),
    state: str = Query(...),
):
    """Google's browser redirect lands here with ?code=&state= as GET query params."""
    conn_mgr = request.app.state.connection_manager
    # Reconstruct the redirect_uri from the incoming request so it matches what was sent.
    redirect_uri = str(request.url).split("?")[0]
    try:
        return await conn_mgr.handle_callback(code, state, redirect_uri)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/oauth/upgrade", response_model=ScopeUpgradeResponse)
async def upgrade_scopes(
    body: ScopeUpgradeRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """Enable additional tools that need scopes beyond what the user has already granted.

    If all required scopes are already granted, tools are assigned immediately (upgraded=True).
    Otherwise returns an authorization_url for incremental OAuth — same Google account,
    same connection, just new scopes merged in.
    """
    conn_mgr = request.app.state.connection_manager
    try:
        return await conn_mgr.initiate_scope_upgrade(
            user_id=current_user["id"],
            provider_name=body.provider_name,
            requested_tools=body.requested_tools,
            redirect_uri=body.redirect_uri,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
