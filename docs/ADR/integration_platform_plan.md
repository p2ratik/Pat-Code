# Integration Platform — Implementation Plan

> **Scope**: Build the integration provider infrastructure per the [PRD](file:///g:/Projects/Pat-Code/AIAgentFromScrach/prds/integrations.md), using **Google Sheets** (by the Google Provider) as the test integration. MCP tools remain a parallel, untouched subsystem.

---

## 1. Architecture Overview

The PRD mandates a **three-pillar** model where every tool is a `Tool` subclass and the runtime doesn't know the difference:

```
                Tool (tools/base.py)
                  │
      ┌───────────┼────────────┐
      │           │            │
 Built-in     OAuthTool     MCPTool
 (existing)   (NEW)         (existing)
```

The critical design constraint: **tools must remain stateless**. Authentication is delegated to a `CredentialManager` which speaks to `Providers`. The flow:

```
LLM → ReadGoogleSheetTool.execute()
        → GoogleProvider.get_client(user_id, scopes)
            → CredentialManager.get_valid_token(provider, user, scopes)
                → integration_credentials table (decrypt, check expiry)
                → refresh if needed
            → return authenticated httpx client
        → Google Sheets API call
        → return ToolResult
```

> [!IMPORTANT]
> This is **completely separate from MCP**. MCP has its own `mcp_servers`, `mcp_user_connections`, `mcp_credentials` tables. The integration system gets its own parallel set of tables prefixed with `integration_`.

---

## 2. Database Schema — New Tables

Three new tables in [schema.sql](file:///g:/Projects/Pat-Code/AIAgentFromScrach/Pat-Code/api/schema.sql) + corresponding ORM models in [models.py](file:///g:/Projects/Pat-Code/AIAgentFromScrach/Pat-Code/api/db/models.py):

### 2.1 `integration_providers`

The **admin-registered** catalog of providers (Google, GitHub, Slack, etc.). Configured once by the admin via the dashboard (like the screenshot shows — Client ID, Client Secret, Redirect URL).

```sql
CREATE TABLE integration_providers (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(100) UNIQUE NOT NULL,    -- 'google', 'github', 'slack'
    display_name    VARCHAR(255) NOT NULL,            -- 'Google', 'GitHub'
    auth_type       VARCHAR(50) NOT NULL DEFAULT 'oauth2',  -- 'oauth2', 'api_key', 'none'
    
    -- OAuth2 app credentials (entered by admin, like the n8n screenshot)
    client_id       TEXT,
    client_secret   TEXT,                             -- encrypted at rest
    
    -- OAuth2 endpoints (Google-specific defaults, overridable per provider)
    auth_url        TEXT,          -- https://accounts.google.com/o/oauth2/v2/auth
    token_url       TEXT,          -- https://oauth2.googleapis.com/token
    revoke_url      TEXT,          -- https://oauth2.googleapis.com/revoke
    
    -- Default scopes for this provider (tools can request additional)
    default_scopes  TEXT[],        -- ARRAY['openid','email','profile']
    
    -- Metadata
    icon_url        TEXT,
    enabled         BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP NOT NULL DEFAULT NOW()
);
```

### 2.2 `integration_user_connections`

Per-user, per-provider connection status. One row per user+provider pair.

```sql
CREATE TABLE integration_user_connections (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(id) ON DELETE CASCADE,
    provider_id     UUID REFERENCES integration_providers(id) ON DELETE CASCADE,
    status          VARCHAR(50) NOT NULL DEFAULT 'disconnected',
    -- 'connected' | 'disconnected' | 'expired' | 'error'
    connected_at    TIMESTAMP,
    last_used_at    TIMESTAMP,
    UNIQUE(user_id, provider_id)
);
```

### 2.3 `integration_credentials`

Encrypted OAuth tokens per user connection. Mirrors the MCP pattern but scoped to integration providers.

```sql
CREATE TABLE integration_credentials (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    connection_id           UUID REFERENCES integration_user_connections(id) ON DELETE CASCADE,
    encrypted_access_token  TEXT,
    encrypted_refresh_token TEXT,
    token_type              VARCHAR(50) DEFAULT 'Bearer',
    scopes_granted          TEXT[],       -- actual scopes Google returned
    expires_at              TIMESTAMP,
    last_refresh_at         TIMESTAMP,
    provider_user_email     TEXT,         -- from Google userinfo
    created_at              TIMESTAMP DEFAULT NOW(),
    updated_at              TIMESTAMP DEFAULT NOW()
);
```

> [!NOTE]
> We reuse the same Fernet encryption from [oauth.py](file:///g:/Projects/Pat-Code/AIAgentFromScrach/Pat-Code/api/mcp/oauth.py). The `encrypt_token` / `decrypt_token` functions get promoted to a shared location.

---

## 3. Package Structure

```
Pat-Code/
├── tools/
│   ├── base.py                          # Existing — unchanged
│   ├── registry.py                      # Existing — minor change (new Toolkind)
│   ├── builtins/                        # Existing — unchanged
│   ├── mcp/                             # Existing — unchanged (DO NOT TOUCH)
│   └── integrations/                    # NEW — integration tool implementations
│       ├── __init__.py
│       ├── base.py                      # OAuthTool base class
│       └── google/
│           ├── __init__.py
│           ├── read_sheet.py            # ReadGoogleSheetTool
│           └── append_rows.py           # AppendGoogleSheetRowsTool
│
├── api/
│   ├── integrations/                    # NEW — integration services + routes
│   │   ├── __init__.py
│   │   ├── providers/
│   │   │   ├── __init__.py
│   │   │   ├── base.py                  # BaseProvider ABC
│   │   │   └── google.py               # GoogleProvider
│   │   ├── credential_manager.py        # CredentialManager service
│   │   ├── models.py                    # Pydantic request/response models
│   │   ├── service.py                   # IntegrationService (DB operations)
│   │   └── routes.py                    # /integrations/* API endpoints
│   ├── mcp/                             # Existing — UNTOUCHED
│   └── db/
│       └── models.py                    # Add 3 new ORM models
```

---

## 4. Core Abstractions

### 4.1 `OAuthTool` — Base for all integration tools

```python
# tools/integrations/base.py

class OAuthTool(Tool):
    """Base class for tools that need an authenticated API client from a provider.
    
    The tool is STATELESS — it requests a valid client from CredentialManager
    at execute() time. Never holds tokens, never knows about OAuth.
    """
    
    provider_name: str = ""          # e.g., "google"
    required_scopes: list[str] = []  # e.g., ["spreadsheets.readonly"]
    
    kind = Toolkind.INTEGRATION      # New enum value
    
    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        # Extract user_id from the session context
        user_id = invocation.session.get("user_id") if invocation.session else None
        if not user_id:
            return ToolResult.error_result(
                "Integration tools require an authenticated user session."
            )
        
        # Get an authenticated client — CredentialManager handles refresh
        credential_manager = invocation.session.get("credential_manager")
        if not credential_manager:
            return ToolResult.error_result(
                "No credential manager available in session context."
            )
        
        try:
            client = await credential_manager.get_client(
                provider=self.provider_name,
                user_id=user_id,
                scopes=self.required_scopes,
            )
        except AuthorizationRequiredError:
            return ToolResult.error_result(
                f"User has not connected their {self.provider_name} account. "
                f"Please connect via the dashboard first.",
                metadata={"requires_auth": True, "provider": self.provider_name}
            )
        except TokenExpiredError:
            return ToolResult.error_result(
                f"Your {self.provider_name} connection has expired. "
                f"Please reconnect via the dashboard.",
                metadata={"requires_reauth": True, "provider": self.provider_name}
            )
        
        # Delegate to subclass — receives a ready-to-use authenticated client
        return await self.run(client, invocation)
    
    @abc.abstractmethod
    async def run(self, client: httpx.AsyncClient, invocation: ToolInvocation) -> ToolResult:
        """Subclasses implement the actual API call here."""
        pass
```

### 4.2 `BaseProvider` — Provider abstraction

```python
# api/integrations/providers/base.py

class BaseProvider(ABC):
    """Knows how to build an authenticated HTTP client for a specific provider."""
    
    name: str = ""
    
    @abstractmethod
    async def build_client(self, access_token: str) -> httpx.AsyncClient:
        """Return an httpx client configured with auth headers for this provider."""
        pass
    
    @abstractmethod
    async def refresh_token(
        self, refresh_token: str, client_id: str, client_secret: str
    ) -> dict:
        """Exchange a refresh token for a new access token.
        Returns: {"access_token": ..., "expires_in": ..., "refresh_token": ...}
        """
        pass
    
    @abstractmethod
    async def revoke_token(self, token: str) -> bool:
        pass
```

### 4.3 `GoogleProvider`

```python
# api/integrations/providers/google.py

class GoogleProvider(BaseProvider):
    name = "google"
    
    GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
    GOOGLE_REVOKE_URL = "https://oauth2.googleapis.com/revoke"
    
    async def build_client(self, access_token: str) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=30.0,
        )
    
    async def refresh_token(self, refresh_token, client_id, client_secret) -> dict:
        async with httpx.AsyncClient(timeout=15.0) as http:
            response = await http.post(self.GOOGLE_TOKEN_URL, data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": client_id,
                "client_secret": client_secret,
            })
            response.raise_for_status()
            return response.json()
```

### 4.4 `CredentialManager`

```python
# api/integrations/credential_manager.py

class CredentialManager:
    """Central service for obtaining authenticated API clients.
    
    Tools call: credential_manager.get_client(provider, user_id, scopes)
    
    Internally:
      1. Looks up integration_user_connections + integration_credentials
      2. Decrypts tokens
      3. Refreshes if expired (using the provider's refresh_token method)
      4. Persists new tokens
      5. Returns a configured httpx.AsyncClient via the provider
    """
    
    def __init__(self, db: CloudDatabase, providers: dict[str, BaseProvider]):
        self.db = db
        self.providers = providers  # {"google": GoogleProvider(), ...}
    
    async def get_client(self, provider: str, user_id: str, scopes: list[str]) -> httpx.AsyncClient:
        # 1. Lookup provider registration
        # 2. Lookup user connection + credentials
        # 3. Decrypt access_token, check expiry
        # 4. Refresh if needed (using provider + integration_providers.client_id/secret)
        # 5. Build and return client via provider.build_client()
        ...
```

---

## 5. Google Sheets — Test Tools

### 5.1 `ReadGoogleSheetTool`

```python
# tools/integrations/google/read_sheet.py

class ReadGoogleSheetParams(BaseModel):
    spreadsheet_id: str = Field(description="The Google Sheets spreadsheet ID")
    range: str = Field(default="Sheet1", description="A1 notation range, e.g. 'Sheet1!A1:D10'")

class ReadGoogleSheetTool(OAuthTool):
    name = "read_google_sheet"
    description = "Read data from a Google Sheets spreadsheet"
    provider_name = "google"
    required_scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
    
    @property
    def schema(self) -> type[BaseModel]:
        return ReadGoogleSheetParams
    
    async def run(self, client: httpx.AsyncClient, invocation: ToolInvocation) -> ToolResult:
        params = ReadGoogleSheetParams(**invocation.params)
        url = (
            f"https://sheets.googleapis.com/v4/spreadsheets/"
            f"{params.spreadsheet_id}/values/{params.range}"
        )
        response = await client.get(url)
        if response.status_code != 200:
            return ToolResult.error_result(f"Google Sheets API error: {response.text}")
        
        data = response.json()
        values = data.get("values", [])
        # Format as markdown table for LLM readability
        return ToolResult.success_result(self._format_as_table(values))
```

### 5.2 `AppendGoogleSheetRowsTool`

```python
# tools/integrations/google/append_rows.py

class AppendRowsParams(BaseModel):
    spreadsheet_id: str
    range: str = "Sheet1"
    values: list[list[str]] = Field(description="Rows to append, e.g. [['A','B'],['C','D']]")

class AppendGoogleSheetRowsTool(OAuthTool):
    name = "append_google_sheet_rows"
    description = "Append rows to a Google Sheets spreadsheet"
    provider_name = "google"
    required_scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    
    async def run(self, client: httpx.AsyncClient, invocation: ToolInvocation) -> ToolResult:
        params = AppendRowsParams(**invocation.params)
        url = (
            f"https://sheets.googleapis.com/v4/spreadsheets/"
            f"{params.spreadsheet_id}/values/{params.range}:append"
            f"?valueInputOption=USER_ENTERED"
        )
        response = await client.post(url, json={"values": params.values})
        ...
```

---

## 6. API Routes — `/integrations/*`

New route file at `api/integrations/routes.py`, mounted in [app.py](file:///g:/Projects/Pat-Code/AIAgentFromScrach/Pat-Code/api/app.py):

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/integrations/providers` | List all registered providers |
| `POST` | `/integrations/providers` | Admin: register a new provider (client_id, secret, etc.) |
| `PATCH` | `/integrations/providers/{name}` | Admin: update provider config |
| `GET` | `/integrations/connections` | List user's provider connections |
| `POST` | `/integrations/connect/{provider_name}` | Start OAuth flow for user → returns `authorization_url` |
| `GET` | `/integrations/callback` | OAuth callback — exchanges code, stores tokens |
| `POST` | `/integrations/disconnect/{provider_name}` | Revoke + disconnect |
| `GET` | `/integrations/status/{provider_name}` | Token health check |

> [!TIP]
> The OAuth flow for integration providers is **standard Google OAuth 2.0** (not MCP-specific DCR). The admin provides Client ID + Secret via the dashboard (like the n8n screenshot), and we use those directly in the authorization_code → token exchange.

---

## 7. Runtime Injection — How Tools Get to the Agent

### 7.1 New `Toolkind` Enum Value

```diff
# tools/base.py
 class Toolkind(str, Enum):
     READ = "read"
     WRITE = "write"
     SHELL = "shell"
     NETWORK = "network"
     MEMORY = "memory"
     MCP = "mcp"
+    INTEGRATION = "integration"
```

### 7.2 `ToolRegistryView` Enhancement

The [ToolRegistryView](file:///g:/Projects/Pat-Code/AIAgentFromScrach/Pat-Code/api/cloud_runtime.py#L48-L103) already has a pattern for injecting per-request tools (MCP). Integration tools follow the **same pattern**:

```diff
 class ToolRegistryView:
     def __init__(self, base_registry, config: Config):
         self._base = base_registry
         self.config = config
         self._mcp_tools: dict[str, Tool] = {}
+        self._integration_tools: dict[str, Tool] = {}

     def get_tools(self) -> list[Tool]:
         builtins = list(self._base._tools.values())
         if self.config.allowed_tools is not None:
             allowed = set(self.config.allowed_tools)
             builtins = [t for t in builtins if t.name in allowed]
-        return builtins + list(self._mcp_tools.values())
+        return builtins + list(self._mcp_tools.values()) + list(self._integration_tools.values())
```

### 7.3 `CloudAgentRuntime.initialize()` Enhancement

After MCP initialization, discover which integration providers the user is connected to and inject the corresponding tools:

```python
# In CloudAgentRuntime.initialize():

# Phase 2: Inject integration tools for connected providers
if self._credential_manager:
    connected_providers = await self._credential_manager.get_connected_providers(user_id)
    for provider_name in connected_providers:
        for tool_class in get_integration_tools(provider_name):
            tool = tool_class(self.config)
            self.tool_registry._integration_tools[tool.name] = tool
```

### 7.4 Session Context Injection

The `CredentialManager` must be available in `ToolInvocation.session` so stateless tools can request clients:

```python
# In PATService.chat(), when building the runtime:
session_context = {
    "user_id": user_id,
    "credential_manager": credential_manager,  # injected once
}
```

This flows through `ToolInvocation.session` → `OAuthTool.execute()` → `CredentialManager.get_client()`.

---

## 8. Phased Implementation Plan

### Phase 1: Database Layer
| # | Task | Files |
|---|------|-------|
| 1.1 | Add 3 new ORM models | [models.py](file:///g:/Projects/Pat-Code/AIAgentFromScrach/Pat-Code/api/db/models.py) |
| 1.2 | Add SQL to schema.sql | [schema.sql](file:///g:/Projects/Pat-Code/AIAgentFromScrach/Pat-Code/api/schema.sql) |
| 1.3 | `table_validator.py` handles the new tables automatically (no changes needed) | — |
| 1.4 | Promote `encrypt_token` / `decrypt_token` to shared util | `api/crypto.py` (new, move from `api/mcp/oauth.py`) |

### Phase 2: Provider Abstraction
| # | Task | Files |
|---|------|-------|
| 2.1 | Create `BaseProvider` ABC | `api/integrations/providers/base.py` |
| 2.2 | Implement `GoogleProvider` | `api/integrations/providers/google.py` |
| 2.3 | Create provider registry (simple dict) | `api/integrations/providers/__init__.py` |

### Phase 3: Credential Manager
| # | Task | Files |
|---|------|-------|
| 3.1 | Implement `CredentialManager` | `api/integrations/credential_manager.py` |
| 3.2 | Token lookup, decryption, expiry check, refresh, persistence | same file |
| 3.3 | Define custom exceptions (`AuthorizationRequiredError`, `TokenExpiredError`) | same file |

### Phase 4: Integration Service + API Routes
| # | Task | Files |
|---|------|-------|
| 4.1 | `IntegrationService` — DB CRUD for providers, connections, credentials | `api/integrations/service.py` |
| 4.2 | Pydantic request/response models | `api/integrations/models.py` |
| 4.3 | Google OAuth 2.0 flow (standard, not MCP-DCR) | `api/integrations/oauth_flow.py` |
| 4.4 | FastAPI routes `/integrations/*` | `api/integrations/routes.py` |
| 4.5 | Mount routes in `app.py` | [app.py](file:///g:/Projects/Pat-Code/AIAgentFromScrach/Pat-Code/api/app.py) |

### Phase 5: Tool Layer
| # | Task | Files |
|---|------|-------|
| 5.1 | Add `Toolkind.INTEGRATION` | [base.py](file:///g:/Projects/Pat-Code/AIAgentFromScrach/Pat-Code/tools/base.py) |
| 5.2 | Create `OAuthTool` base class | `tools/integrations/base.py` |
| 5.3 | Implement `ReadGoogleSheetTool` | `tools/integrations/google/read_sheet.py` |
| 5.4 | Implement `AppendGoogleSheetRowsTool` | `tools/integrations/google/append_rows.py` |
| 5.5 | Integration tool discovery function | `tools/integrations/__init__.py` |

### Phase 6: Runtime Wiring
| # | Task | Files |
|---|------|-------|
| 6.1 | Extend `ToolRegistryView` with `_integration_tools` dict | [cloud_runtime.py](file:///g:/Projects/Pat-Code/AIAgentFromScrach/Pat-Code/api/cloud_runtime.py) |
| 6.2 | Inject `CredentialManager` into session context in `PATService` | [pat_service.py](file:///g:/Projects/Pat-Code/AIAgentFromScrach/Pat-Code/api/pat_service.py) |
| 6.3 | Enhance `CloudAgentRuntime.initialize()` to register integration tools for connected providers | [cloud_runtime.py](file:///g:/Projects/Pat-Code/AIAgentFromScrach/Pat-Code/api/cloud_runtime.py) |
| 6.4 | Instantiate `CredentialManager` + `IntegrationService` at app startup | [app.py](file:///g:/Projects/Pat-Code/AIAgentFromScrach/Pat-Code/api/app.py) |

### Phase 7: Testing + Seed Data
| # | Task | Files |
|---|------|-------|
| 7.1 | Seed Google provider in DB (manual / admin route) | — |
| 7.2 | End-to-end test: Admin registers Google → User connects → Agent reads sheet | — |
| 7.3 | Verify token refresh flow works when access token expires | — |

---

## 9. Key Design Decisions

### Why separate from MCP?

MCP is a **protocol-level** integration — PAT connects to an MCP server that *exposes* tools. The MCP server owns the tool logic, OAuth is often MCP-spec DCR.

Integration providers are **direct API** integrations — PAT owns the tool logic, talks to Google/GitHub APIs directly using standard OAuth 2.0. Completely different lifecycle.

### Why stateless tools?

Per the PRD: *"The tool should never care how authentication happened. It should simply ask: Give me a valid client."*

The `OAuthTool.execute()` method is a template method that:
1. Extracts `user_id` from session
2. Calls `CredentialManager.get_client()` 
3. Passes the ready client to `self.run()` (subclass)

The tool never sees tokens, never calls refresh, never touches the DB.

### Why per-operation tools?

Per the PRD: *"Smaller tools have clearer schemas, easier prompting, easier retries, easier verification."*

So instead of one `GoogleSheetsTool` with an `operation` param, we have:
- `ReadGoogleSheetTool`
- `AppendGoogleSheetRowsTool`
- `UpdateGoogleSheetCellsTool` (future)
- `CreateGoogleSpreadsheetTool` (future)

### Why the admin registers providers?

Like the n8n screenshot shows, the admin enters the Google Cloud Console's Client ID and Client Secret once. Users then just click "Connect" to OAuth into their Google account. This is standard SaaS OAuth pattern.

---

## 10. What Is NOT Changing

| Component | Status |
|-----------|--------|
| `tools/base.py` Tool class | Unchanged (except adding INTEGRATION to Toolkind enum) |
| `tools/registry.py` | Unchanged |
| `tools/builtins/*` | Unchanged |
| `tools/mcp/*` | **Untouched** |
| `api/mcp/*` | **Untouched** |
| `mcp_servers`, `mcp_credentials`, `mcp_user_connections` tables | **Untouched** |
| Execution engine, hooks, agent loop | Unchanged |

---

## 11. Open Questions for You

1. **Encryption key reuse**: Should integration credentials use the same `MCP_ENCRYPTION_KEY` or a separate `INTEGRATION_ENCRYPTION_KEY`? I'd lean toward reusing the same key (and renaming the env var to something generic like `PAT_ENCRYPTION_KEY`).

2. **Admin UI**: The dashboard currently has an MCP page. Do you want a new `/integrations` page in the dashboard for Phase 1, or is API-only sufficient for testing?

3. **Scopes granularity**: Should the admin define allowed scopes per provider, or should each tool declare exactly what scopes it needs and the system requests the union at OAuth time?

4. **Tool registration in `tools` table**: Currently the `tools` table stores builtin tool names for RBAC (`profile_tools`). Should integration tools also be seeded into the `tools` table so they can be assigned to profiles, or should integration tools bypass the allowlist (like MCP tools currently do)?
