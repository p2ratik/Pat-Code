from pydantic import BaseModel, Field



class MCPServerCreate(BaseModel):
    name: str                          # Unique slug, e.g. "github"
    display_name: str                  # Human label, e.g. "GitHub MCP"
    server_url: str                    # URL or local path for the server
    transport: str                     # "stdio" | "sse" | "http"
    startup_timeout_sec: int = 30      # How long to wait before declaring failure
    supports_oauth: bool = False       # Whether this server uses OAuth tokens
    enabled: bool = True


class MCPServerResponse(BaseModel):
    id: str
    name: str
    display_name: str
    server_url: str
    transport: str
    startup_timeout_sec: int | None
    supports_oauth: bool | None
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
