import json
import logging
import secrets
import uuid
from datetime import datetime, timedelta

from redis.asyncio import Redis
from sqlalchemy import select

from api.db.database import CloudDatabase
from api.db.models import (
    IntegrationProvider,
    IntegrationUserConnection,
    IntegrationCredential,
    Tool,
    ProfileTool,
    UserAgentProfile,
)
from api.integrations.credential_manager import CredentialManager
from api.integrations.encryption import decrypt_token
from api.integrations.exceptions import AuthorizationRequiredError, ProviderNotEnabledError
from api.integrations.providers.base import BaseProvider

logger = logging.getLogger(__name__)

# Redis key for OAuth state param; short-lived to prevent CSRF replay.
_OAUTH_STATE_KEY = "intg:oauth_state:{state}"
OAUTH_STATE_TTL_SECONDS = 10 * 60  # 10 minutes


class ConnectionManager:
    """Manages the lifecycle of user ↔ provider connections.

    Owns: initiate OAuth, handle callback, disconnect, list connections.
    Delegates token persistence to CredentialManager and profile assignment to profile_cache.
    """

    def __init__(
        self,
        db: CloudDatabase,
        redis: Redis,
        credential_manager: CredentialManager,
        providers: dict[str, BaseProvider],
        profile_cache=None,
    ):
        self.db = db
        self.redis = redis
        self.credential_manager = credential_manager
        self.providers = providers
        self.profile_cache = profile_cache  # Optional; used for cache invalidation post-assign.

    # ------------------------------------------------------------------
    # OAuth flow
    # ------------------------------------------------------------------

    async def initiate_oauth(
        self, user_id: str, provider_name: str, redirect_uri: str,
        requested_tools: list[str] | None = None,
    ) -> dict:
        """Build the authorization URL and persist a short-lived state token in Redis.

        Scopes are the union of required_scopes from each requested tool — never max_scopes.
        max_scopes is used only as a server-side ceiling guard.
        """
        provider_row = await self._get_provider_row(provider_name)
        if not provider_row.enabled:
            raise ProviderNotEnabledError(provider_name)

        provider_obj = self._get_provider(provider_name)
        state = secrets.token_urlsafe(32)
        scopes = self._scopes_for_tools(requested_tools or [], provider_row)

        await self.redis.setex(
            _OAUTH_STATE_KEY.format(state=state),
            OAUTH_STATE_TTL_SECONDS,
            json.dumps({
                "user_id": user_id,
                "provider": provider_name,
                "redirect_uri": redirect_uri,
                "requested_tools": requested_tools or [],
            }),
        )

        auth_url = provider_obj.build_auth_url(
            client_id=decrypt_token(provider_row.client_id),
            redirect_uri=redirect_uri,
            scopes=scopes,
            state=state,
        )
        return {"authorization_url": auth_url, "state": state}

    async def handle_callback(
        self, code: str, state: str, redirect_uri: str
    ) -> dict:
        """Exchange authorization code for tokens, persist the connection, and assign tools."""
        state_data = await self._validate_state(state)
        user_id: str = state_data["user_id"]
        provider_name: str = state_data["provider"]
        requested_tools: list[str] = state_data.get("requested_tools", [])

        provider_row = await self._get_provider_row(provider_name)
        provider_obj = self._get_provider(provider_name)

        payload = await provider_obj.exchange_code(
            code=code,
            redirect_uri=redirect_uri,
            client_id=decrypt_token(provider_row.client_id),
            client_secret=decrypt_token(provider_row.client_secret),
        )

        access_token: str = payload["access_token"]
        refresh_token: str | None = payload.get("refresh_token")
        expires_at = (
            datetime.utcnow() + timedelta(seconds=int(payload["expires_in"]))
            if payload.get("expires_in")
            else None
        )
        scopes_granted: list[str] = payload.get("scope", "").split() if payload.get("scope") else []

        provider_email = await self._fetch_provider_email(provider_name, access_token)

        conn = await self._upsert_connection(user_id, provider_row, status="connected")

        await self.credential_manager.store_tokens(
            connection_id=str(conn.id),
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
            scopes_granted=scopes_granted,
            provider_user_email=provider_email,
        )

        # Auto-assign requested tools to the user's current agent profile.
        assigned: list[str] = []
        if requested_tools:
            assigned = await self._assign_tools_to_profile(user_id, requested_tools)
            if assigned and self.profile_cache:
                await self.profile_cache.invalidate_user(user_id)

        logger.info(
            "User %s connected to provider '%s', tools assigned: %s",
            user_id, provider_name, assigned,
        )
        return {
            "provider": provider_name,
            "status": "connected",
            "email": provider_email,
            "scopes": scopes_granted,
            "tools_assigned": assigned,
        }

    async def initiate_scope_upgrade(
        self, user_id: str, provider_name: str,
        requested_tools: list[str], redirect_uri: str,
    ) -> dict:
        """Check whether requested_tools need more scopes than the user has granted.

        If no new scopes are needed: assigns the tools immediately and returns upgraded=True.
        If new scopes are needed: builds an incremental OAuth URL (include_granted_scopes=true)
        so the user can approve only the delta. The same handle_callback() processes the result.
        """
        provider_row = await self._get_provider_row(provider_name)
        if not provider_row.enabled:
            raise ProviderNotEnabledError(provider_name)

        # Load what the user currently has granted.
        granted = await self._get_granted_scopes(user_id, provider_name)
        granted_set = set(granted)

        # Compute the union of required scopes across all requested tools.
        required_set = set(self._scopes_for_tools(requested_tools, provider_row))
        missing = list(required_set - granted_set)

        if not missing:
            # Scopes already sufficient — just assign the tools and we're done.
            assigned = await self._assign_tools_to_profile(user_id, requested_tools)
            if assigned and self.profile_cache:
                await self.profile_cache.invalidate_user(user_id)
            logger.info(
                "Scope upgrade for user %s provider '%s': no new scopes needed, assigned %s",
                user_id, provider_name, assigned,
            )
            return {"upgraded": True, "tools_assigned": assigned, "missing_scopes": []}

        # Build an incremental OAuth URL — grants_set ∪ missing.
        upgrade_scopes = list(granted_set | set(missing))
        provider_obj = self._get_provider(provider_name)
        state = secrets.token_urlsafe(32)

        await self.redis.setex(
            _OAUTH_STATE_KEY.format(state=state),
            OAUTH_STATE_TTL_SECONDS,
            json.dumps({
                "user_id": user_id,
                "provider": provider_name,
                "redirect_uri": redirect_uri,
                "requested_tools": requested_tools,
            }),
        )

        auth_url = provider_obj.build_auth_url(
            client_id=decrypt_token(provider_row.client_id),
            redirect_uri=redirect_uri,
            scopes=upgrade_scopes,
            state=state,
            include_granted_scopes=True,
        )
        logger.info(
            "Scope upgrade for user %s provider '%s': redirecting for missing scopes %s",
            user_id, provider_name, missing,
        )
        return {
            "upgraded": False,
            "authorization_url": auth_url,
            "state": state,
            "tools_assigned": [],
            "missing_scopes": missing,
        }

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    async def disconnect(self, user_id: str, provider_name: str) -> dict:
        """Revoke tokens at the provider, clear cache, and mark connection disconnected."""
        provider_row = await self._get_provider_row(provider_name)
        provider_obj = self._get_provider(provider_name)

        async with self.db.get_session() as session:
            result = await session.execute(
                select(IntegrationUserConnection).where(
                    IntegrationUserConnection.user_id == uuid.UUID(user_id),
                    IntegrationUserConnection.provider_id == provider_row.id,
                )
            )
            conn = result.scalar_one_or_none()
            if not conn:
                return {"provider": provider_name, "status": "disconnected"}

            # Explicit credential query — avoids lazy-load greenlet error in async sessions.
            cred_result = await session.execute(
                select(IntegrationCredential).where(IntegrationCredential.connection_id == conn.id)
            )
            cred = cred_result.scalar_one_or_none()

            if cred and cred.encrypted_access_token:
                try:
                    access_token = decrypt_token(cred.encrypted_access_token)
                    client_id = decrypt_token(provider_row.client_id) if provider_row.client_id else ""
                    client_secret = decrypt_token(provider_row.client_secret) if provider_row.client_secret else ""
                    await provider_obj.revoke_token(access_token, client_id, client_secret)
                except Exception as exc:
                    logger.warning("Revoke call failed for user=%s provider=%s: %s", user_id, provider_name, exc)

            conn.status = "disconnected"
            conn.connected_at = None
            await session.commit()

        await self.credential_manager.invalidate_cache(user_id, provider_name)
        logger.info("User %s disconnected from provider '%s'", user_id, provider_name)
        return {"provider": provider_name, "status": "disconnected"}

    async def get_connections(self, user_id: str) -> list[dict]:
        """Return all provider connections for a user with their current status."""
        async with self.db.get_session() as session:
            result = await session.execute(
                select(IntegrationUserConnection, IntegrationProvider)
                .join(IntegrationProvider, IntegrationProvider.id == IntegrationUserConnection.provider_id)
                .where(IntegrationUserConnection.user_id == uuid.UUID(user_id))
            )
            rows = result.all()

        return [
            {
                "provider": provider.name,
                "display_name": provider.display_name,
                "status": conn.status,
                "connected_at": conn.connected_at.isoformat() if conn.connected_at else None,
                "last_used_at": conn.last_used_at.isoformat() if conn.last_used_at else None,
            }
            for conn, provider in rows
        ]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_provider(self, name: str) -> BaseProvider:
        provider = self.providers.get(name)
        if not provider:
            raise AuthorizationRequiredError(name)
        return provider

    async def _get_provider_row(self, provider_name: str) -> IntegrationProvider:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(IntegrationProvider).where(IntegrationProvider.name == provider_name)
            )
            row = result.scalar_one_or_none()
        if not row:
            raise AuthorizationRequiredError(provider_name)
        return row

    async def _validate_state(self, state: str) -> dict:
        """Consume and validate the OAuth state from Redis; raises ValueError if invalid/expired."""
        key = _OAUTH_STATE_KEY.format(state=state)
        raw = await self.redis.get(key)
        if not raw:
            raise ValueError("Invalid or expired OAuth state parameter")
        await self.redis.delete(key)
        return json.loads(raw)

    async def _upsert_connection(
        self, user_id: str, provider_row: IntegrationProvider, status: str
    ) -> IntegrationUserConnection:
        """Create or update the integration_user_connections row."""
        async with self.db.get_session() as session:
            result = await session.execute(
                select(IntegrationUserConnection).where(
                    IntegrationUserConnection.user_id == uuid.UUID(user_id),
                    IntegrationUserConnection.provider_id == provider_row.id,
                )
            )
            conn = result.scalar_one_or_none()
            if not conn:
                conn = IntegrationUserConnection(
                    user_id=uuid.UUID(user_id),
                    provider_id=provider_row.id,
                )
                session.add(conn)

            conn.status = status
            if status == "connected":
                conn.connected_at = datetime.utcnow()

            await session.commit()
            await session.refresh(conn)
            return conn

    async def _resolve_scopes(self, provider_name: str) -> list[str]:
        """Return max_scopes for the provider — used as a fallback/ceiling guard only."""
        async with self.db.get_session() as session:
            result = await session.execute(
                select(IntegrationProvider.max_scopes).where(IntegrationProvider.name == provider_name)
            )
            row = result.first()
        max_scopes: list[str] | None = row[0] if row else None
        return max_scopes or []

    async def _get_granted_scopes(self, user_id: str, provider_name: str) -> list[str]:
        """Return the scopes_granted stored for this user+provider connection."""
        async with self.db.get_session() as session:
            result = await session.execute(
                select(IntegrationCredential.scopes_granted)
                .join(IntegrationUserConnection, IntegrationUserConnection.id == IntegrationCredential.connection_id)
                .join(IntegrationProvider, IntegrationProvider.id == IntegrationUserConnection.provider_id)
                .where(
                    IntegrationUserConnection.user_id == uuid.UUID(user_id),
                    IntegrationProvider.name == provider_name,
                    IntegrationUserConnection.status == "connected",
                )
            )
            row = result.first()
        return list(row[0]) if row and row[0] else []

    def _scopes_for_tools(self, tool_names: list[str], provider_row: IntegrationProvider) -> list[str]:
        """Build the OAuth scope set as the union of required_scopes across requested tools.

        Falls back to provider max_scopes when no tools are specified.
        Validates that requested scopes don't exceed the admin-configured max_scopes ceiling.
        """
        from tools.integrations import get_all_integration_tools
        # required_scopes is a class-level attribute — no dummy Config needed.
        tool_map: dict[str, list[str]] = {}
        for tool_cls in get_all_integration_tools():
            name = getattr(tool_cls, "name", None)
            scopes = getattr(tool_cls, "required_scopes", [])
            if name:
                tool_map[name] = scopes

        if not tool_names or not tool_map:
            return list(provider_row.max_scopes or [])

        requested: set[str] = set()
        for name in tool_names:
            requested.update(tool_map.get(name, []))

        # Enforce ceiling: strip any scope not in max_scopes (if max_scopes is set).
        ceiling = set(provider_row.max_scopes or [])
        if ceiling:
            allowed = requested & ceiling
            stripped = requested - ceiling
            if stripped:
                logger.warning("Scope ceiling stripped from OAuth request: %s", stripped)
            return list(allowed)

        return list(requested)


    async def _assign_tools_to_profile(self, user_id: str, tool_names: list[str]) -> list[str]:
        """Upsert each tool_name into profile_tools for the user's current profile.

        Returns the list of tool names that were successfully assigned.
        """
        async with self.db.get_session() as session:
            # Get the user's active profile_id.
            profile_result = await session.execute(
                select(UserAgentProfile.profile_id).where(
                    UserAgentProfile.user_id == uuid.UUID(user_id)
                )
            )
            profile_row = profile_result.first()
            if not profile_row:
                logger.warning("No profile found for user %s — skipping tool assignment", user_id)
                return []

            profile_id = profile_row[0]

            # Fetch matching tool rows.
            tool_result = await session.execute(
                select(Tool).where(Tool.name.in_(tool_names))
            )
            found_tools = tool_result.scalars().all()

            # Fetch already-assigned tool ids for this profile to avoid duplicates.
            existing_result = await session.execute(
                select(ProfileTool.tool_id).where(ProfileTool.profile_id == profile_id)
            )
            existing_ids = {row[0] for row in existing_result.all()}

            assigned: list[str] = []
            for tool in found_tools:
                if tool.id not in existing_ids:
                    session.add(ProfileTool(profile_id=profile_id, tool_id=tool.id))
                    assigned.append(tool.name)
                else:
                    assigned.append(tool.name)  # Already assigned — still report it.

            await session.commit()

        if assigned:
            logger.info("Assigned tools %s to profile %s for user %s", assigned, profile_id, user_id)
        return assigned

    async def _fetch_provider_email(self, provider_name: str, access_token: str) -> str | None:
        """Fetch the user's email from the provider's userinfo endpoint after OAuth."""
        try:
            provider_obj = self._get_provider(provider_name)
            async with await provider_obj.build_client(access_token) as client:
                if provider_name == "google":
                    resp = await client.get("https://www.googleapis.com/oauth2/v3/userinfo")
                    resp.raise_for_status()
                    return resp.json().get("email")
        except Exception as exc:
            logger.warning("Could not fetch provider email for %s: %s", provider_name, exc)
        return None
