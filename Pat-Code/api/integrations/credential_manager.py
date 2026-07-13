import logging
import uuid
from datetime import datetime, timedelta

import httpx
from redis.asyncio import Redis
from sqlalchemy import select

from api.db.database import CloudDatabase
from api.db.models import (
    IntegrationProvider,
    IntegrationUserConnection,
    IntegrationCredential,
)
from api.integrations.encryption import decrypt_token, encrypt_token
from api.integrations.exceptions import (
    AuthorizationRequiredError,
    InsufficientScopesError,
    ProviderNotEnabledError,
    TokenExpiredError,
)
from api.integrations.providers.base import BaseProvider

logger = logging.getLogger(__name__)

TOKEN_CACHE_TTL_SECONDS = 40 * 60  # 40 minutes per spec
TOKEN_CACHE_KEY = "intg:token:{user_id}:{provider}"


class CredentialManager:
    """Token-focused service. Tools call get_client() and receive a ready httpx client.

    Flow: Redis cache → DB decrypt → refresh if expired → scope check → build client.
    Never manages connection lifecycle — that belongs to ConnectionManager.
    """

    def __init__(self, db: CloudDatabase, redis: Redis, providers: dict[str, BaseProvider]):
        self.db = db
        self.redis = redis
        self.providers = providers

    # ------------------------------------------------------------------
    # Public API — called by OAuthTool.execute()
    # ------------------------------------------------------------------

    async def get_client(
        self, provider: str, user_id: str, scopes: list[str]
    ) -> httpx.AsyncClient:
        """Return an authenticated httpx client for the given provider and user.

        Raises AuthorizationRequiredError, TokenExpiredError, InsufficientScopesError,
        or ProviderNotEnabledError as appropriate.
        """
        provider_obj = self._get_provider(provider)

        access_token = await self._resolve_token(provider, user_id)

        await self._check_scopes(provider, user_id, scopes)

        await self._touch_last_used(provider, user_id)

        return await provider_obj.build_client(access_token)

    async def store_tokens(
        self,
        connection_id: str,
        access_token: str,
        refresh_token: str | None,
        expires_at: datetime | None,
        scopes_granted: list[str],
        provider_user_email: str | None,
    ) -> None:
        """Encrypt and persist tokens for a connection. Called by ConnectionManager post-OAuth."""
        async with self.db.get_session() as session:
            result = await session.execute(
                select(IntegrationCredential).where(
                    IntegrationCredential.connection_id == uuid.UUID(connection_id)
                )
            )
            cred = result.scalar_one_or_none()
            if not cred:
                cred = IntegrationCredential(connection_id=uuid.UUID(connection_id))
                session.add(cred)

            cred.encrypted_access_token = encrypt_token(access_token)
            # Only overwrite the refresh token when we actually got a new one.
            # Google only returns a refresh_token on the first consent (or explicit re-consent).
            # Overwriting with None would permanently break the next token-refresh cycle.
            if refresh_token:
                cred.encrypted_refresh_token = encrypt_token(refresh_token)
            cred.expires_at = expires_at
            cred.scopes_granted = scopes_granted
            cred.provider_user_email = provider_user_email
            cred.last_refresh_at = datetime.utcnow()

            await session.commit()

    async def invalidate_cache(self, user_id: str, provider: str) -> None:
        """Delete the Redis access token cache entry. Called on disconnect or revoke."""
        key = TOKEN_CACHE_KEY.format(user_id=user_id, provider=provider)
        await self.redis.delete(key)
        logger.debug("Invalidated token cache for user=%s provider=%s", user_id, provider)

    async def get_connected_providers(self, user_id: str) -> list[str]:
        """Return provider names where the user has a 'connected' status. Used by the runtime."""
        async with self.db.get_session() as session:
            result = await session.execute(
                select(IntegrationProvider.name)
                .join(IntegrationUserConnection, IntegrationUserConnection.provider_id == IntegrationProvider.id)
                .where(
                    IntegrationUserConnection.user_id == uuid.UUID(user_id),
                    IntegrationUserConnection.status == "connected",
                    IntegrationProvider.enabled == True,
                )
            )
            return [row[0] for row in result.all()]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_provider(self, name: str) -> BaseProvider:
        provider = self.providers.get(name)
        if not provider:
            raise AuthorizationRequiredError(name)
        return provider

    async def _resolve_token(self, provider: str, user_id: str) -> str:
        """Return a valid plaintext access token — from Redis cache or DB with refresh."""
        key = TOKEN_CACHE_KEY.format(user_id=user_id, provider=provider)

        cached = await self.redis.get(key)
        if cached:
            logger.debug("Token cache HIT for user=%s provider=%s", user_id, provider)
            return cached

        logger.debug("Token cache MISS for user=%s provider=%s — fetching from DB", user_id, provider)
        return await self._load_token_from_db(provider, user_id)

    async def _load_token_from_db(self, provider: str, user_id: str) -> str:
        """Decrypt access token from DB; refresh it if expired. Populates Redis on success."""
        async with self.db.get_session() as session:
            row = await self._fetch_connection_row(session, provider, user_id)
            conn, provider_row, cred = row

            if not cred or not cred.encrypted_access_token:
                raise AuthorizationRequiredError(provider)

            if not provider_row.enabled:
                raise ProviderNotEnabledError(provider)

            access_token = decrypt_token(cred.encrypted_access_token)
            now = datetime.utcnow()
            token_expired = bool(cred.expires_at and cred.expires_at < now)

        if token_expired:
            access_token = await self._refresh(provider, user_id, cred, provider_row)

        key = TOKEN_CACHE_KEY.format(user_id=user_id, provider=provider)
        await self.redis.setex(key, TOKEN_CACHE_TTL_SECONDS, access_token)
        return access_token

    async def _refresh(
        self,
        provider: str,
        user_id: str,
        cred: IntegrationCredential,
        provider_row: IntegrationProvider,
    ) -> str:
        """Exchange the refresh token for a new access token; persist and return it."""
        if not cred.encrypted_refresh_token:
            raise TokenExpiredError(provider)

        try:
            refresh_token = decrypt_token(cred.encrypted_refresh_token)
        except ValueError:
            raise TokenExpiredError(provider)

        if not provider_row.client_id or not provider_row.client_secret:
            raise TokenExpiredError(provider)

        try:
            provider_obj = self._get_provider(provider)
            payload = await provider_obj.refresh_token(
                refresh_token=refresh_token,
                client_id=decrypt_token(provider_row.client_id),
                client_secret=decrypt_token(provider_row.client_secret),
            )
        except Exception as exc:
            logger.warning("Token refresh failed for user=%s provider=%s: %s", user_id, provider, exc)
            raise TokenExpiredError(provider)

        new_access = payload.get("access_token")
        if not new_access:
            raise TokenExpiredError(provider)

        new_refresh = payload.get("refresh_token", refresh_token)
        new_expires_at = (
            datetime.utcnow() + timedelta(seconds=int(payload["expires_in"]))
            if payload.get("expires_in")
            else None
        )

        async with self.db.get_session() as session:
            result = await session.execute(
                select(IntegrationCredential).where(IntegrationCredential.id == cred.id)
            )
            db_cred = result.scalar_one_or_none()
            if db_cred:
                db_cred.encrypted_access_token = encrypt_token(new_access)
                db_cred.encrypted_refresh_token = encrypt_token(new_refresh)
                db_cred.expires_at = new_expires_at
                db_cred.last_refresh_at = datetime.utcnow()
                await session.commit()

        logger.info("Silently refreshed token for user=%s provider=%s", user_id, provider)
        return new_access

    async def _check_scopes(self, provider: str, user_id: str, required: list[str]) -> None:
        """Verify that all required scopes are covered by the stored scopes_granted.

        Uses prefix matching for Google-style scope hierarchies:
        'spreadsheets' (granted) satisfies 'spreadsheets.readonly' (required)
        because the broader scope is a strict superset.
        """
        if not required:
            return

        async with self.db.get_session() as session:
            result = await session.execute(
                select(IntegrationCredential.scopes_granted)
                .join(IntegrationUserConnection, IntegrationUserConnection.id == IntegrationCredential.connection_id)
                .join(IntegrationProvider, IntegrationProvider.id == IntegrationUserConnection.provider_id)
                .where(
                    IntegrationUserConnection.user_id == uuid.UUID(user_id),
                    IntegrationProvider.name == provider,
                )
            )
            row = result.first()

        granted: list[str] = row[0] if row and row[0] else []

        def is_covered(req: str, granted_set: list[str]) -> bool:
            # Exact match first.
            if req in granted_set:
                return True
            # Broader scope covers narrower: granted 'auth/spreadsheets' satisfies
            # required 'auth/spreadsheets.readonly' because the granted scope is a prefix.
            return any(req.startswith(g) or g.startswith(req) for g in granted_set)

        missing = [s for s in required if not is_covered(s, granted)]
        if missing:
            raise InsufficientScopesError(provider, missing)

    async def _touch_last_used(self, provider: str, user_id: str) -> None:
        """Update last_used_at on the connection row after a successful token resolution."""
        try:
            async with self.db.get_session() as session:
                result = await session.execute(
                    select(IntegrationUserConnection)
                    .join(IntegrationProvider, IntegrationProvider.id == IntegrationUserConnection.provider_id)
                    .where(
                        IntegrationUserConnection.user_id == uuid.UUID(user_id),
                        IntegrationProvider.name == provider,
                    )
                )
                conn = result.scalar_one_or_none()
                if conn:
                    conn.last_used_at = datetime.utcnow()
                    await session.commit()
        except Exception as exc:
            logger.debug("Failed to update last_used_at: %s", exc)

    async def _fetch_connection_row(
        self, session, provider: str, user_id: str
    ) -> tuple[IntegrationUserConnection, IntegrationProvider, IntegrationCredential | None]:
        """Single query to load connection + provider + credentials for a user+provider pair."""
        result = await session.execute(
            select(IntegrationUserConnection, IntegrationProvider)
            .join(IntegrationProvider, IntegrationProvider.id == IntegrationUserConnection.provider_id)
            .where(
                IntegrationUserConnection.user_id == uuid.UUID(user_id),
                IntegrationProvider.name == provider,
                IntegrationUserConnection.status == "connected",
            )
        )
        row = result.first()
        if not row:
            raise AuthorizationRequiredError(provider)

        conn, provider_row = row

        cred_result = await session.execute(
            select(IntegrationCredential).where(IntegrationCredential.connection_id == conn.id)
        )
        cred = cred_result.scalar_one_or_none()
        return conn, provider_row, cred
