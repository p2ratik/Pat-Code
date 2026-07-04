# Integration Tools — Profile-Aware Architecture Plan

This document describes everything that must be changed, added, or created to make
integration tools (Google Sheets, etc.) part of the agent profile RBAC system, while
also supporting the incremental-scope OAuth flow you described.

---

## What You Want (Plain English)

1. **Connect** — User clicks "Connect Google Sheets". PAT initiates OAuth requesting **only
   the scopes that tool requires** (`spreadsheets` — not drive, gmail, calendar, etc.).
   After consent, the connection is saved and the tool is **assigned to the user's current
   agent profile** automatically.
2. **Enable a new tool** — User sees a connected provider tool that needs extra scopes
   (e.g. `drive.readonly`). Clicking "Enable" checks what scopes they already have,
   identifies what is missing, and redirects them to an **incremental authorization**
   (same Google account, no new connection — scopes are merged).
3. **Profile-gated** — If a user is switched to a different profile that does not include
   `read_google_sheet`, that tool is unavailable — even if they have a valid Google connection.
4. **Runtime** — On `/chat`, the agent only injects integration tools that are both
   **(a) in the user's profile** and **(b) have a connected + scoped OAuth connection**.

---

## Current State (What Exists Today)

| Concern | Current State |
|---|---|
| Integration tool gating | Tools bypass `profile_tools` entirely — any connected user gets all tools for that provider |
| Scope handling | `initiate_oauth` always requests `max_scopes` ceiling — should request only the tool's `required_scopes` |
| Profile-tool assignment | Manual only via admin API — no auto-assignment post-OAuth |
| Tool seeding | Integration tools are **not** seeded into the `tools` table at all |
| Runtime injection | `get_connected_providers()` injects all tools for that provider, no profile check |

---

## What Must Change / Be Added

### 1. Schema — No New Tables Required

The existing `tools` and `profile_tools` tables already implement RBAC.
You only need to **seed** integration tools into the `tools` table and let the normal
assignment flow handle the rest.

**`tools` table** needs rows for each integration tool at startup:
- `read_google_sheet`
- `append_google_sheet_rows`

These are already defined in `get_all_integration_tools()`. Seeding is the only schema
action required.

---

### 2. Tool Seeder — Startup

**What to add:** An idempotent seeder that runs during `lifespan` startup and ensures
integration tool names are rows in the `tools` table.

```
for tool_cls in get_all_integration_tools():
    INSERT INTO tools (name, description) VALUES (...) ON CONFLICT (name) DO NOTHING
```

---

### 3. OAuth Initiate — Scopes + State Changes

**Files:** `connection_manager.py`, `models.py`, `routes.py`

Two changes here:

**3a. Scope strategy — request `tool.required_scopes`, not `max_scopes`.**

`max_scopes` on the provider is a ceiling/cap (what the admin permits). It is **not**
what gets requested at OAuth time. The OAuth request should ask only for what the
specific tool needs. This keeps the consent screen minimal, which matters for Google's
app review and for user trust.

```python
# OLD — requests entire max_scopes ceiling
scopes = provider_row.max_scopes

# NEW — requests only what the tools being connected actually need
scopes = union(tool.required_scopes for tool in requested_tools)
```

`max_scopes` remains useful as a server-side validation guard — the system should
reject any OAuth request that asks for scopes outside the admin-configured ceiling.

**3b. State blob — `requested_tools` list instead of `tool_name` string.**

Using a list today costs nothing and avoids a breaking redesign when the UI later
allows connecting multiple tools in one OAuth flow.

```python
# Current Redis state blob
{"user_id": "...", "provider": "google", "redirect_uri": "..."}

# New Redis state blob
{"user_id": "...", "provider": "google", "redirect_uri": "...", "requested_tools": ["read_google_sheet"]}
```

The callback iterates `requested_tools` and assigns each one. Single tool = list of one.

---

### 4. OAuth Callback — Auto-Assign Tools to Profile

**File:** `connection_manager.py` → `handle_callback()`

After tokens are stored, iterate `requested_tools` from the state blob:

1. Look up the user's current `profile_id` from `user_agent_profiles`.
2. For each tool name in `requested_tools`, look up its `tool_id` from the `tools` table.
3. Upsert into `profile_tools (profile_id, tool_id)` for each.
4. Call `profile_cache.invalidate_user(user_id)` — invalidates the `profile:{user_id}` key
   which is what the `/chat` hot path reads. The next request will rebuild from DB and see
   the newly assigned tools within the same request cycle.

This is a single-pass operation over `requested_tools`, no schema change.

---

### 5. Incremental Scope Flow — New Endpoint

**Files:** `routes.py`, `connection_manager.py`, `models.py`

New method: `initiate_scope_upgrade(user_id, provider_name, requested_tools, redirect_uri)`
New endpoint: `POST /integrations/oauth/upgrade`

**Logic:**
1. Load `scopes_granted` from `integration_credentials` for this user+provider.
2. For each tool in `requested_tools`, load `required_scopes` from the tool class.
3. Compute `missing = union(required_scopes) - granted`.
4. If `missing` is empty → no OAuth needed. Assign all tools to profile and return `{"upgraded": true}`.
5. If `missing` is non-empty → build an OAuth URL requesting `granted ∪ missing`.
   Google supports incremental auth via `include_granted_scopes=true`.
   Store state with `{"requested_tools": [...]}` so the **same** existing `handle_callback()`
   processes it. No new callback path needed.

The state blob is identical to the initial connect flow — callback is fully reused.

**Google-specific URL params to add for incremental auth:**
```
include_granted_scopes=true
access_type=offline
prompt=consent
```

---

### 6. Runtime Injection — Add Profile Check

**File:** `cloud_runtime.py` → `initialize()`

**Current logic:**
```
connected_providers = get_connected_providers(user_id)
injected = all tools for each connected provider   # no profile gate
```

**New logic:**
```python
connected_set = set(connected_providers)           # already a list, convert once
allowed_set = set(self.config.allowed_tools) if self.config.allowed_tools is not None else None

for tool_cls in get_all_integration_tools():
    instance = tool_cls(self.config)
    in_connected = instance.provider_name in connected_set
    in_profile   = allowed_set is None or instance.name in allowed_set  # None = admin
    if in_connected and in_profile:
        self.tool_registry._integration_tools[instance.name] = instance
```

Both `connected_set` and `allowed_set` are Python `set` objects — the `in` check is O(1)
regardless of how many tools or providers exist. No list scan.

---

### 7. `ConnectionManager` — Inject `ProfileCache`

**File:** `connection_manager.py`, `app.py`

The `ConnectionManager` needs a reference to `profile_cache` to invalidate it after
auto-assignment. Add it as a constructor parameter (same pattern as `credential_manager`).

---

## Summary Table

| # | What | File(s) | Type |
|---|------|---------|------|
| 1 | Seed integration tools into `tools` table at startup | `app.py` / `database.py` | New logic, no schema change |
| 2 | Request `tool.required_scopes` at OAuth time (not `max_scopes`) | `connection_manager.py` | Scope strategy change |
| 3 | `requested_tools` list in OAuth state blob (replaces `tool_name` string) | `connection_manager.py`, `models.py`, `routes.py` | Extend existing |
| 4 | Auto-assign all `requested_tools` to profile after callback | `connection_manager.py` | Extend existing method |
| 5 | Invalidate `ProfileCache` via `invalidate_user(user_id)` after assignment | `connection_manager.py` (inject `profile_cache`) | Extend existing |
| 6 | New `POST /integrations/oauth/upgrade` endpoint | `routes.py`, `connection_manager.py`, `models.py` | New endpoint + method |
| 7 | Profile gate + O(1) set lookup in runtime injection | `cloud_runtime.py` → `initialize()` | Small refactor |

**No new database tables.**
**No changes to MCP, builtins, execution engine, or agent loop.**
**No schema migrations** — only an idempotent INSERT at startup.

---

## Phase Breakdown Suggestion

### Phase A — Profile Gating (Safest, No UX Change)
- Seed integration tools into `tools` table.
- Add profile check to `cloud_runtime.initialize()`.
- **Result:** Integration tools now respect `profile_tools` RBAC. Admins see all;
  users only see tools explicitly assigned to their profile.

### Phase B — Auto-Assignment After OAuth Connect
- Switch OAuth initiate from `max_scopes` → `tool.required_scopes`.
- Add `requested_tools` list to OAuth state blob.
- Add auto-assign + `invalidate_user()` logic to `handle_callback()`.
- Inject `profile_cache` into `ConnectionManager`.
- **Result:** Connecting Google Sheets requests minimal scopes, assigns only the tools
  selected, and the profile cache is updated immediately.

### Phase C — Incremental Scope Upgrade
- New `initiate_scope_upgrade()` method + `POST /integrations/oauth/upgrade` endpoint.
- **Result:** "Enable" button works. Missing scopes trigger a targeted re-auth without
  creating a new connection or new refresh token.
