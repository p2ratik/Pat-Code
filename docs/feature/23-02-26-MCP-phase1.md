# MCP Phase -3 . No Oauth based MCP created yt

Why mcp_tools table exists
On every chat request, the agent needs to know what tools each connected MCP server exposes. Calling each server live on every request introduces N network round-trips (GitHub, Slack, Notion…) before the agent can even start. Instead: an admin calls POST /mcp/servers/{name}/sync once after discovery, which writes all tool definitions (tool_name, description, schema) into mcp_tools. Runtime reads from DB — zero extra network calls.

Files created / modified
File	What
api/db/models.py	Added MCPTool ORM model (every schema field: id, mcp_server_id, tool_name, description, schema, created_at, updated_at). Added back_populates relationships on MCPServer, MCPUserConnection, MCPCredential, MCPServerConfig
api/mcp/__init__.py	Package marker
api/mcp/models.py	Pydantic models: MCPServerCreate, MCPServerResponse, MCPConnectRequest, MCPDisconnectRequest, MCPConnectionResponse, MCPToolResponse — every DB field exposed
api/mcp/service.py	CloudMCPService: register_server, list_servers, connect_for_user, disconnect_for_user, get_user_connections, sync_tools (atomic delete+insert), get_server_tools, build_mcp_configs() (the runtime bridge)
api/routes/mcp.py	6 routes: GET /mcp/servers, POST /mcp/servers, POST /mcp/connect, POST /mcp/disconnect, GET /mcp/status, POST /mcp/servers/{name}/sync, GET /mcp/servers/{name}/tools
api/app.py	CloudMCPService injected into app.state.mcp_service, mcp_service passed into PATService, /mcp router registered
api/pat_service.py	mcp_service parameter added; _build_config() now receives mcp_configs dict; chat() awaits build_mcp_configs(user_id) before building config — agent receives live MCP servers
models.py
models.py
service.py
mcp.py
__init__.py
app.py
pat_service.py