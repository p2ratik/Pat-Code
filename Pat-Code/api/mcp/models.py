from pydantic import BaseModel, Field



class MCPServerCreate(BaseModel):
    name: str
    display_name: str
    server_url: str
    transport: str
    startup_timeout_sec: int = 30
    supports_oauth: bool = False
    oauth_client_id: str | None = None
    oauth_client_secret: str | None = None
    enabled: bool = True


class MCPServerResponse(BaseModel):
    id: str
    name: str
    display_name: str
    server_url: str
    transport: str
    startup_timeout_sec: int | None
    supports_oauth: bool | None
    oauth_client_id: str | None = None
    enabled: bool
    created_at: str

    model_config = {"from_attributes": True}


class MCPConnectRequest(BaseModel):
    server_name: str    # Matches mcp_servers.name


class MCPDisconnectRequest(BaseModel):
    server_name: str


class MCPConnectionResponse(BaseModel):
    id: str
    user_id: str
    mcp_server_id: str
    server_name: str
    status: str           # connected | disconnected | error | expired | disabled | refresh_required
    connected_at: str | None
    last_used_at: str | None

    model_config = {"from_attributes": True}



class MCPToolResponse(BaseModel):
    id: str
    mcp_server_id: str
    tool_name: str
    description: str | None
    input_schema: dict | None = Field(None, alias="schema")  # alias keeps JSON key as "schema"
    updated_at: str

    model_config = {"from_attributes": True, "populate_by_name": True}


class OAuthCallbackRequest(BaseModel):
    """Payload sent by the frontend/OAuth redirect handler after a successful OAuth flow."""
    server_name: str
    access_token: str
    refresh_token: str | None = None
    token_type: str = "Bearer"
    expires_in: int | None = None        # seconds until expiry; used to compute expires_at
    provider_user_id: str | None = None


class OAuthTokenStatusResponse(BaseModel):
    server_name: str
    has_token: bool
    expires_at: str | None
    is_expired: bool
    last_refresh_at: str | None = None


class OAuthStartRequest(BaseModel):
    server_name: str
    frontend_redirect_url: str | None = None


class OAuthStartResponse(BaseModel):
    server_name: str
    authorization_url: str
