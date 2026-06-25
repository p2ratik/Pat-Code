# MCP Phase 3 — OAuth Token Support

## What was built

OAuth credential storage and injection for URL-based MCP servers (SSE / StreamableHTTP transports).

### Files created / modified

| File | What |
|---|---|
| `api/mcp/oauth.py` | `encrypt_token` / `decrypt_token` — Fernet AES-128-CBC wrappers. Key loaded once at import from `MCP_ENCRYPTION_KEY` env var. Raises `RuntimeError` at startup if key is absent. |
| `api/mcp/service.py` | `store_oauth_tokens` — encrypts and upserts access + refresh tokens into `mcp_credentials`; sets connection status to `connected`. `get_oauth_token_status` — returns expiry metadata without decrypting. `build_mcp_configs` updated: bulk-fetches credentials, decrypts access token for OAuth servers, injects as `auth_token` into `MCPServerConfig`. Skips server (logs error) on decryption failure instead of crashing. |
| `api/mcp/models.py` | Added `OAuthCallbackRequest` and `OAuthTokenStatusResponse` Pydantic models. |
| `api/routes/mcp.py` | Added `POST /mcp/oauth/callback` and `GET /mcp/oauth/token-status/{server_name}`. |

## Flow

```
1. User completes OAuth flow in browser (external provider)
2. Frontend receives access_token / refresh_token / expires_in
3. POST /mcp/oauth/callback  {server_name, access_token, ...}
     └─ service.store_oauth_tokens()
          ├─ get_or_create mcp_user_connections row
          ├─ upsert mcp_credentials (Fernet-encrypted tokens)
          ├─ conn.status = "connected"
          └─ AuditLog: MCP_OAUTH_TOKENS_STORED
4. On next chat request:
     └─ build_mcp_configs(user_id)
          ├─ joins mcp_user_connections + mcp_servers (status=connected, enabled=True)
          ├─ bulk-fetches mcp_credentials for returned conn IDs
          └─ for OAuth servers: decrypt_token() → MCPServerConfig(auth_token=<token>)
               └─ MCPClient._build_auth() → BearerAuth → Authorization: Bearer <token>
```

## Security properties

- Token never logged or returned by any endpoint.
- `GET /mcp/oauth/token-status/{server_name}` returns only `has_token`, `expires_at`, `is_expired`.
- Decryption failure on a single server skips that server and logs an error — agent still starts with remaining servers.
- All existing user-isolation guarantees from the Phase-1 ADR are preserved (credentials are linked through `connection_id → user_id`).

## Required env var

```
MCP_ENCRYPTION_KEY=<32-byte URL-safe base64 Fernet key>
```

Generate: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`

## What is NOT included (future phases)

- Token refresh (calling the provider's token endpoint when `is_expired=True`)
- OAuth provider redirect / PKCE initiation endpoint (the current model assumes the frontend handles the browser redirect)
