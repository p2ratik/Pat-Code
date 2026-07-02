# ADR: MCP OAuth 401 After Re-Login — Root Cause and Fix

**Date**: 2026-07-02 (Updated from 2026-07-01)
**Status**: Resolved
**Scope**: `api/mcp/service.py`, `api/routes/mcp.py`, `api/db/models.py`, `api/db/table_validator.py`

---

## Problem

After completing an MCP OAuth flow (e.g. with Notion), the agent receives all tools correctly. After the user logs out of PAT and back in (or after the MCP access token naturally expires), the agent receives a 401 Unauthorized from the provider's token refresh endpoint. The connection is marked as `expired` and tools are lost.

An earlier fix (2026-07-01) added a token refresh mechanism, but the refresh requests themselves were failing with a 401.

---

## Root Cause

### Bug 1 (Primary) — `_try_refresh_token` sent empty `client_id` for DCR providers

During the initial OAuth flow, `build_authorization_flow` performs Dynamic Client Registration (DCR) to obtain a dynamic `client_id` and `client_secret` specific to that connection. This `client_info` was stored in the ephemeral Redis flow state and used for the initial code exchange, but it was **never persisted to the database**.

When `_try_refresh_token` attempted to refresh the token, it checked the static `server.oauth_client_id`, which is empty for DCR-based servers like Notion. The refresh request was sent with `client_id: ""`, which the provider correctly rejected with a 401.

### Bug 2 — Redis OAuth state double-delete

The previous ADR claimed to have fixed a bug where the Redis state was deleted before the token exchange, preventing retries on transient errors. However, the `await redis.delete(state_key)` line was still present before the exchange, resulting in a double-delete (once before, once after). The first delete still wiped the state prematurely.

---

## Fix

### 1. Store DCR credentials in `mcp_credentials`

Added a new `dcr_client_info` JSONB column to the `MCPCredential` model.

During `oauth_browser_callback`, we now extract the dynamic `client_info` (which includes `client_id`, `client_secret`, and `token_endpoint_auth_method`) as well as the discovered `token_endpoint` from the Redis flow state. This is passed to `store_oauth_tokens` and saved in the new column.

### 2. Inject DCR credentials during refresh

`_try_refresh_token` now checks `cred.dcr_client_info` first. If present, it uses the dynamically registered `client_id` and `client_secret` to construct the refresh request (either via `client_secret_post` or `client_secret_basic`, as dictated by the provider). This satisfies Notion's requirement that the refresh grant uses the exact same client credentials as the original code exchange.

It also uses the stored `token_endpoint`, avoiding a slow live discovery round-trip on every refresh.

### 3. Automated Column-Level Schema Drift Handling

To deploy the new column without manual SQL, `table_validator.py:ensure_tables` was upgraded. It now compares existing database columns against the ORM definitions and automatically executes `ALTER TABLE ... ADD COLUMN IF NOT EXISTS ...` for any missing columns, allowing seamless schema upgrades.

### 4. True fix for Redis state deletion

Removed the premature `redis.delete` call before the exchange in `oauth_browser_callback`. The state is now exclusively deleted after `store_oauth_tokens` successfully persists the credentials.

---

## Behaviour After Fix

| Scenario | Before (2026-07-01 fix) | After (2026-07-02 fix) |
|---|---|---|
| Token refresh for DCR server (Notion) | ❌ 401 (empty client_id) | ✅ Silent refresh using stored DCR client_id |
| OAuth callback network error | ❌ State deleted prematurely | ✅ State preserved; user can retry |
| DB schema update (new column) | ❌ Requires manual `psql` | ✅ Handled automatically at startup |

---

## What is still NOT included

- Proactive token refresh before expiry (background task / scheduler).
- Token rotation handling if the provider returns a new `client_secret` during refresh (very rare).

