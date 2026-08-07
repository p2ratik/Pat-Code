# Bug Analysis: Profile Isolation & Google OAuth

## Issue 1 — Profile Isolation (Profiles Are Global, Not User-Owned)

### Root Cause
The `agent_profiles` table has **no `owner_user_id` column**. Profiles are global entities — any admin can see/use any profile, and `list_profiles()` returns ALL active profiles regardless of who created them.

### Specific Bugs

#### Backend

| File | Line(s) | Problem |
|------|---------|---------|
| `api/schema.sql` | L92–103 | `agent_profiles` table has no `owner_user_id` column |
| `api/auth/service.py` | L238–258 | `list_profiles()` returns all profiles — no user filter |
| `api/auth/service.py` | L260–295 | `create_profile()` does NOT record who created the profile |
| `api/auth/service.py` | L297–338 | `update_profile()` does NOT check if the requester owns the profile |
| `api/routes/profiles.py` | L41–42 | Create requires `admin` role — regular users can't create their own profile |
| `api/routes/profiles.py` | L26–29 | `list_profiles` has auth check but calls service with no user filter |
| `api/routes/profiles.py` | L68–69 | `update_profile` checks admin role, not ownership |

#### Frontend

| File | Problem |
|------|---------|
| `profiles/page.tsx` | Fetches ALL profiles from `GET /profiles` — user sees everyone's profiles |
| `profiles/page.tsx` | "Create Profile" button shows for all users; 403 only visible after submit |

### What Needs to Happen

1. **Schema**: Add `owner_user_id UUID REFERENCES users(id)` to `agent_profiles` + DB migration.
2. **`create_profile()`**: Accept `owner_user_id`, store it. Drop admin-only gate — any authenticated user can create their own profile.
3. **`list_profiles()`**: Filter by `owner_user_id = user_id`. Admins optionally see all.
4. **`update_profile()` / `assign_tools_to_profile()`**: Ownership check — only the owner (or admin) can edit.
5. **Routes**: Pass `current_user["id"]` into every service call. Remove the `has_admin_role` guard on create.
6. **Frontend**: Automatic once the backend filters correctly.

---

## Issue 2 — Google Sheets OAuth: Broken End-to-End Flow

### How the Design Should Work (n8n model)

`integration_providers` holds **one app-level** `client_id`/`client_secret` (your Google Cloud Console app). Every user then goes through the Google consent screen individually — their personal tokens land in `integration_credentials`, scoped per user via `integration_user_connections`. **This design is correct.** The problem is the flow is never wired up end-to-end.

### Specific Bugs

#### Backend

| File | Line | Problem |
|------|------|---------|
| `api/app.py` `lifespan()` | — | No seed for the `integration_providers` google row. Must be inserted manually or via admin API before any OAuth can work. If missing, all OAuth calls crash with `AuthorizationRequiredError`. |
| `api/integrations/routes.py` | L89–99 | `/oauth/callback` endpoint is **POST** with JSON body — but Google issues a **GET redirect** with `?code=&state=` query params. Mismatch. |
| `api/integrations/routes.py` | — | No `GET /integrations/oauth/callback` endpoint exists for Google's actual redirect URI. |
| `api/integrations/credential_manager.py` | L175 | `_refresh()` raises `TokenExpiredError` silently when `client_id` is None — no indicator that the provider row is misconfigured. |

#### Frontend

| File | Problem |
|------|---------|
| `app/integrations/callback/` | **Directory exists but has no `page.tsx`** — Google's redirect lands on a 404. |
| Dashboard | **No "Connect Google" button anywhere.** Users can't initiate the OAuth flow from the UI. |
| Dashboard canvas | Tools like Google Sheets show as available but there's no UI to authorize them per-user. |

### What Needs to Happen

1. **Backend — Seed the google provider at startup**: In `lifespan()`, call a `seed_integration_providers()` that reads `GOOGLE_CLIENT_ID` + `GOOGLE_CLIENT_SECRET` from env and upserts the row (with encrypted tokens) into `integration_providers`. No manual DB step.

2. **Backend — GET callback endpoint**: Add `GET /integrations/oauth/callback?code=&state=&redirect_uri=` that maps to the same `conn_mgr.handle_callback()` logic. This is the URI you register in Google Cloud Console.

3. **Frontend — Callback page**: Create `app/integrations/callback/page.tsx`:
   - Reads `code` + `state` from URL query params
   - Calls `POST /integrations/oauth/callback`
   - Shows success/error, then redirects back to integrations canvas

4. **Frontend — "Connect Google" button**: Add a "Connect Google Account" card that:
   - Calls `POST /integrations/oauth/initiate` (with provider_name=`google`, redirect_uri pointing to the callback page)
   - Redirects user to the returned `authorization_url`

5. **Design note — no per-user client_id**: The `client_id`/`client_secret` in `integration_providers` are **app-level** (same for all users). Each user's tokens are private in `integration_credentials`. This is exactly right — no need to change the data model.

---

## Summary Table

| # | Severity | File(s) | Fix |
|---|----------|---------|-----|
| 1a | Critical | `schema.sql`, `auth/service.py` | Add `owner_user_id` to `agent_profiles`, filter by it |
| 1b | Critical | `routes/profiles.py` | Remove admin-only gate on create; add ownership check on update |
| 1c | Low | `profiles/page.tsx` | Auto-fixes once backend filters correctly |
| 2a | Critical | `app.py` `lifespan()` | Seed google provider row from env vars at startup |
| 2b | Critical | `integrations/routes.py` | Add GET callback endpoint matching Google's redirect |
| 2c | Critical | `app/integrations/callback/` | Create callback `page.tsx` |
| 2d | High | Dashboard | Add "Connect Google" initiate button |
