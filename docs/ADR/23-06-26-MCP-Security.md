
# Security audit result: ✅ User isolation is valid

## Layer-by-layer trace
Layer	Isolated?	Evidence
mcp_servers table	Shared by design — it's just a directory of what servers exist, like an app store. No credentials here.	✅ Correct
mcp_user_connections table	Per-user — UNIQUE(user_id, mcp_server_id) enforced at DB level. One row per user per server.	✅ Correct
/mcp/connect route	Uses current_user["id"] extracted from the JWT — the user cannot inject a different ID.	✅ Correct
/mcp/disconnect route	Same — current_user["id"] from JWT, then _require_connection verifies the row belongs to that user before touching it.	✅ Correct
/mcp/status route	get_user_connections(user_id) has .where(MCPUserConnection.user_id == uuid.UUID(user_id)) — only that user's rows.	✅ Correct
build_mcp_configs(user_id)	Hard-filters .where(MCPUserConnection.user_id == uuid.UUID(user_id), status == "connected") — only that user's connected servers reach the agent.	✅ Correct
mcp_credentials table	Linked to connection_id, which is per-user. No other user's connection_id can reach another user's credentials.	✅ Correct
mcp_tools table	Shared per server — stores tool definitions only (names, schemas), not credentials or data. Think of it as a schema catalogue, not access.	✅ Correct, by design
The one thing you need to understand clearly
mcp_servers is a global registry, but that does not mean all users have access to all servers.

When you register a Gmail MCP server, it simply appears in the list like an available integration. A user is only connected to it if there is a row in mcp_user_connections with their user_id and status = connected. Until that row exists for them, the server is invisible to their agent.

mcp_servers (global, public listing)
    ├── User A's agent
    │     └── only sees servers where mcp_user_connections.user_id = A AND status=connected
    └── User B's agent
          └── only sees servers where mcp_user_connections.user_id = B AND status=connected
What changes when OAuth is added
When Gmail OAuth is built, the env dict in build_mcp_configs() (currently {}) will be populated with that specific user's decrypted token from mcp_credentials. So even on a shared server definition, each user's agent process gets their own token injected. The isolation boundary is already in the schema — it just isn't populated yet because OAuth is deferred.