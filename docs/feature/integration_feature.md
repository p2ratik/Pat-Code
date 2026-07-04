# Integration Tools Execution Flow: Google Sheets

This document outlines the end-to-end execution flow of an integration tool (e.g., Google Sheets) during an active agent chat session, assuming the user has already completed the OAuth authorization flow.

## 1. Tool Discovery & Injection (Per-Request)

Unlike static builtin tools (which are loaded once at startup), integration tools and MCP tools are dynamically discovered and injected into the agent's context on every single chat request.

1. **Request Start**: The user hits the `POST /chat` endpoint.
2. **Runtime Initialization**: A new `CloudAgentRuntime` is instantiated for this specific request. The runtime is given a reference to the `credential_manager` and the `user_id`.
3. **Connection Check**: Inside `CloudAgentRuntime.initialize()`, the agent asks the `CredentialManager`: *"Which integration providers has this user connected?"*
4. **Tool Injection**: For every connected provider (e.g., `google`), the runtime dynamically instantiates the relevant tools (`ReadGoogleSheetTool`, `AppendGoogleSheetRowsTool`) and injects them into the `ToolRegistryView` under `_integration_tools`.
5. **Prompt Building**: The agent rebuilds the system prompt so the LLM is aware of these newly injected tools. 

## 2. Execution Flow & Endpoints Hit

When the LLM decides to invoke an integration tool (e.g., `read_google_sheet`), the execution follows a strict pipeline designed to minimize database hits and latency.

### Step 1: Authentication Resolution
The `OAuthTool.execute()` base method intercepts the call and asks the `CredentialManager` for an authenticated HTTP client:
- **Redis Cache Check**: The manager checks Redis for a valid `access_token` (`intg:token:{user_id}:google`).
- **Cache Miss (or Expiry)**: If the token is missing or expired, it queries the PostgreSQL database (`integration_credentials`), decrypts the refresh token using the `INTEGRATION_ENCRYPTION_KEY`, and hits the **Google OAuth Token Endpoint** (`POST https://oauth2.googleapis.com/token`) to refresh the session. The new token is saved to DB and Redis.
- **Scope Verification**: The manager ensures the granted scopes still satisfy the tool's `required_scopes`.

### Step 2: The Tool Execution
With an authenticated `httpx.AsyncClient` in hand, the specific tool's `run()` method executes:
- **ReadGoogleSheetTool**: Hits `GET https://sheets.googleapis.com/v4/spreadsheets/{id}/values/{range}`.
- **AppendGoogleSheetRowsTool**: Hits `POST https://sheets.googleapis.com/v4/spreadsheets/{id}/values/{range}:append`.

## 3. RBAC & Profile Assignment (Are they independent?)

**Integration tools behave exactly like MCP tools.** 

They **bypass** the standard agent profile allowlist (RBAC) in the current implementation. Here is how they differ from standard tools:
- **Builtin Tools** (like `read_file`, `write_file`) are strictly filtered by the `allowed_tools` list of the agent profile.
- **Integration Tools** (and MCP tools) require the user to explicitly authenticate via OAuth. The act of completing the OAuth flow is treated as a direct authorization signal. 

Because of this, if a user connects their Google account, the Google Sheets tools will automatically become available to them, acting as personal, user-level plugins rather than profile-level tools. 

*(Note: While the original Phase 5 plan considered seeding them into the `tools` table for RBAC, the cloud runtime was architected to mirror the MCP behavior, injecting them directly via explicit OAuth connections to avoid users needing to whitelist tools they explicitly authorized via Google).*
