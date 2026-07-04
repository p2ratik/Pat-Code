import json
import logging
import secrets
import uuid
from datetime import datetime, timedelta

from redis.asyncio import Redis
from sqlalchemy import select

from api.db.database import CloudDatabase
from api.db.models import IntegrationProvider, IntegrationUserConnection, IntegrationCredential
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
    Delegates all token persistence to CredentialManager.store_tokens().
    """

    def __init__(
        self,
        db: CloudDatabase,
        redis: Redis,
        credential_manager: CredentialManager,
        providers: dict[str, BaseProvider],
    ):
        self.db = db
        self.redis = redis
        self.credential_manager = credential_manager
        self.providers = providers

    # ------------------------------------------------------------------
    # OAuth flow
    # ------------------------------------------------------------------

    async def initiate_oauth(
        self, user_id: str, provider_name: str, redirect_uri: str
    ) -> dict:
        """Build the authorization URL and persist a short-lived state token in Redis."""
        provider_row = await self._get_provider_row(provider_name)
        if not provider_row.enabled:
            raise ProviderNotEnabledError(provider_name)

        provider_obj = self._get_provider(provider_name)
        state = secrets.token_urlsafe(32)
        scopes = await self._resolve_scopes(provider_name)

        await self.redis.setex(
            _OAUTH_STATE_KEY.format(state=state),
            OAUTH_STATE_TTL_SECONDS,
            json.dumps({"user_id": user_id, "provider": provider_name, "redirect_uri": redirect_uri}),
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
        """Exchange authorization code for tokens and persist the connection."""
        state_data = await self._validate_state(state)
        user_id: str = state_data["user_id"]
        provider_name: str = state_data["provider"]

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

        logger.info("User %s connected to provider '%s'", user_id, provider_name)
        return {
            "provider": provider_name,
            "status": "connected",
            "email": provider_email,
            "scopes": scopes_granted,
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
        """Return max_scopes for the provider (what we request during OAuth)."""
        async with self.db.get_session() as session:
            result = await session.execute(
                select(IntegrationProvider.max_scopes).where(IntegrationProvider.name == provider_name)
            )
            row = result.first()
        max_scopes: list[str] | None = row[0] if row else None
        return max_scopes or []

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
