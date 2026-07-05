"""CacheManager — single injection point for all Redis-backed caches.

Owns all key namespaces and TTL constants. Internal concerns (profile,
conversation) are delegated to their existing modules unchanged.
"""
from __future__ import annotations

import logging

from redis.asyncio import Redis

from api.db.database import CloudDatabase
from api.cache.ttls import (
    TTL_USER, TTL_PROFILE, TTL_PROFILE_DEF, TTL_PROFILES_ALL,
    TTL_TOOLS_PROFILE, TTL_CONNECTED,
)
from api.cache.profile_cache import ProfileCache, ProfileConfig
from api.cache.conv_context import ConversationContextRepository

logger = logging.getLogger(__name__)

# Re-export TTL names so callers can import from api.cache.cache_manager directly.
__all__ = [
    "CacheManager",
    "TTL_USER", "TTL_PROFILE", "TTL_PROFILE_DEF",
    "TTL_PROFILES_ALL", "TTL_TOOLS_PROFILE", "TTL_CONNECTED",
]


class CacheManager:
    """Unified cache facade; delegates to ProfileCache and ConversationContextRepository internally."""

    def __init__(self, db: CloudDatabase, redis: Redis) -> None:
        self.redis = redis
        # Reuse existing implementations — no rewrite.
        self.profiles = ProfileCache(db, redis)
        self.conversations = ConversationContextRepository(db, redis)


    async def get_profile_config(self, user_id: str) -> ProfileConfig:
        """Thin pass-through so existing PATService call sites need no changes."""
        return await self.profiles.get_profile_config(user_id)

    async def invalidate_user(self, user_id: str) -> None:
        """Invalidate the per-user profile cache entry."""
        await self.profiles.invalidate_user(user_id)

    async def invalidate_prompt(self, prompt_id: str) -> None:
        """Invalidate the prompt-scoped cache key."""
        await self.profiles.invalidate_prompt(prompt_id)

    async def invalidate_profile_tools(self, profile_id: str) -> None:
        """Invalidate the tools-scoped cache key for a profile."""
        await self.profiles.invalidate_profile_tools(profile_id)

    @staticmethod
    def key_user(user_id: str) -> str:
        return f"pat:user:{user_id}"

    @staticmethod
    def key_profile(user_id: str) -> str:
        return f"pat:profile:{user_id}"

    @staticmethod
    def key_profile_def(profile_id: str) -> str:
        return f"pat:profile_def:{profile_id}"

    @staticmethod
    def key_profiles_all() -> str:
        return "pat:profiles:all"

    @staticmethod
    def key_tools_registry() -> str:
        return "pat:tools:registry"

    @staticmethod
    def key_tools_profile(profile_id: str) -> str:
        return f"pat:tools:profile:{profile_id}"

    @staticmethod
    def key_connected(user_id: str) -> str:
        return f"pat:connected:{user_id}"
