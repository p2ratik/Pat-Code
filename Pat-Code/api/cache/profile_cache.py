"""
ProfileCache
------------
Redis-backed cache for per-user agent profile configuration.

Motivation
----------
Each chat request previously made 3 separate DB round-trips:
  1. AuthService.get_user_profile()   → profile row
  2. AuthService.has_admin_role()     → role check
  3. AuthService.get_allowed_tools()  → profile_tools join

This module collapses those into a single SQL query and caches the result
in Redis under three separately-invalidatable keys:

  profile:{user_id}    TTL 5 min  — invalidated when user's profile changes
  prompt:{prompt_id}   TTL 1 hr   — invalidated when a Prompt row is edited
  tools:{profile_id}   TTL 1 hr   — invalidated when profile tools are reassigned

Cache Layout
------------
`profile:{user_id}` stores the full ProfileConfig JSON including the
resolved prompt content and allowed_tools list. This is the only key that
needs to be read on a hot path. The prompt and tools keys exist so that
targeted invalidation is possible without having to scan all user keys.

Invalidation
------------
  profile_cache.invalidate_user(user_id)          → called on assign_profile()
  profile_cache.invalidate_prompt(prompt_id)       → call when Prompt.content is edited
  profile_cache.invalidate_profile_tools(prof_id) → called on assign_tools_to_profile()
"""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import asdict, dataclass

from redis.asyncio import Redis
from sqlalchemy import text

from api.db.database import CloudDatabase

logger = logging.getLogger(__name__)

# Admin roles that bypass tool filtering — mirrors auth/service.py
ADMIN_ROLES = {"super_admin", "admin"}

# Cache TTLs
PROFILE_TTL_SECONDS = 5 * 60       # 5 minutes
PROMPT_TTL_SECONDS  = 60 * 60      # 1 hour
TOOLS_TTL_SECONDS   = 60 * 60      # 1 hour


@dataclass
class ProfileConfig:
    """Everything _build_config() needs — resolved in one DB round-trip.

    Attributes
    ----------
    profile_id:
        UUID string of the agent_profiles row, or None for admin users
        with no profile.
    model_name:
        LLM model identifier (e.g. "gpt-4.1-mini").
    temperature:
        Sampling temperature.
    max_turns:
        Maximum agentic loop turns per request.
    prompt_content:
        Fully loaded system prompt text from the prompts table, or None
        if the profile has no prompt_id or the prompt row is inactive.
    allowed_tools:
        List of tool names the model is allowed to call.
        None means no restriction (admin bypass).
        Empty list means no tools — fail-closed for unassigned users.
    """
    profile_id: str | None
    model_name: str
    temperature: float
    max_turns: int
    prompt_content: str | None
    allowed_tools: list[str] | None  # None = admin (unrestricted)


class ProfileCache:
    """Single-query profile config with Redis caching.

    Usage
    -----
    Inject into PATService via app.state.profile_cache at startup.

        config = await profile_cache.get_profile_config(user_id)
        # config.model_name, config.allowed_tools, config.prompt_content
    """

    def __init__(self, db: CloudDatabase, redis: Redis) -> None:
        self.db = db
        self.redis = redis


    @staticmethod
    def _profile_key(user_id: str) -> str:
        return f"profile:{user_id}"

    @staticmethod
    def _prompt_key(prompt_id: str) -> str:
        return f"prompt:{prompt_id}"

    @staticmethod
    def _tools_key(profile_id: str) -> str:
        return f"tools:{profile_id}"



    async def get_profile_config(self, user_id: str) -> ProfileConfig:
        """Return the ProfileConfig for user_id, using Redis when warm.

        On a cache miss the single aggregated SQL query runs and the
        result is stored in Redis before returning.
        """
        key = self._profile_key(user_id)
        cached = await self.redis.get(key)
        if cached:
            logger.debug("ProfileCache HIT for user %s", user_id)
            return ProfileConfig(**json.loads(cached))

        logger.debug("ProfileCache MISS for user %s — querying DB", user_id)
        config = await self._fetch_from_db(user_id)
        await self.redis.setex(key, PROFILE_TTL_SECONDS, json.dumps(asdict(config)))
        return config

    async def invalidate_user(self, user_id: str) -> None:
        """Drop the profile cache for a user.

        Call whenever the user's profile assignment changes so the next
        request gets fresh data instead of a stale 5-minute window.
        """
        deleted = await self.redis.delete(self._profile_key(user_id))
        if deleted:
            logger.info("ProfileCache invalidated for user %s", user_id)

    async def invalidate_prompt(self, prompt_id: str) -> None:
        """Drop the prompt-scoped cache key.

        Call whenever a Prompt row's content is edited. Users on profiles
        that reference this prompt will reload on the next request.
        Note: this alone does not force a user-level cache refresh — pair
        it with invalidate_user() for each affected user if you need
        instant propagation.
        """
        await self.redis.delete(self._prompt_key(prompt_id))
        logger.info("ProfileCache prompt key invalidated: prompt_id=%s", prompt_id)

    async def invalidate_profile_tools(self, profile_id: str) -> None:
        """Drop the tools-scoped cache key.

        Call whenever profile_tools are reassigned. Users on this profile
        will reload tools on the next request (within 5-minute profile TTL).
        For instant propagation, also call invalidate_user() per affected user.
        """
        await self.redis.delete(self._tools_key(profile_id))
        logger.info("ProfileCache tools key invalidated: profile_id=%s", profile_id)


    async def _fetch_from_db(self, user_id: str) -> ProfileConfig:
        """Fetch profile config in one SQL round-trip.

        The query:
        - Uses an EXISTS subquery to check admin role (no extra round-trip)
        - LEFT JOINs agent_profiles, prompts, and profile_tools in one pass
        - Uses array_agg to collect tool names without Python-side grouping
        - Always returns exactly one row (even if the user has no profile)
        """
        user_uuid = uuid.UUID(user_id)

        async with self.db.get_session() as session:
            result = await session.execute(
                text("""
                    SELECT
                        ap.id::text                                              AS profile_id,
                        COALESCE(ap.model_name,  'gpt-4.1-mini')                AS model_name,
                        COALESCE(ap.temperature, 0.7)                           AS temperature,
                        COALESCE(ap.max_turns,   100)                           AS max_turns,
                        p.content                                               AS prompt_content,
                        array_agg(t.name) FILTER (WHERE t.name IS NOT NULL)    AS tool_names,
                        EXISTS(
                            SELECT 1
                            FROM   user_roles ur
                            JOIN   roles r ON r.id = ur.role_id
                            WHERE  ur.user_id = :user_id
                            AND    r.name = ANY(ARRAY['super_admin', 'admin'])
                        )                                                        AS is_admin
                    FROM (SELECT CAST(:user_id AS uuid) AS uid) AS u
                    LEFT JOIN user_agent_profiles uap ON uap.user_id   = u.uid
                    LEFT JOIN agent_profiles      ap  ON ap.id          = uap.profile_id
                                                     AND ap.is_active   = TRUE
                    LEFT JOIN prompts             p   ON p.id            = ap.prompt_id
                                                     AND p.is_active    = TRUE
                    LEFT JOIN profile_tools       pt  ON pt.profile_id  = ap.id
                    LEFT JOIN tools               t   ON t.id            = pt.tool_id
                    GROUP BY ap.id, ap.model_name, ap.temperature,
                             ap.max_turns, p.content
                    LIMIT 1
                """),
                {"user_id": str(user_uuid)},
            )
            row = result.mappings().first()

        # No row at all — shouldn't happen with the dummy FROM, but guard anyway
        if row is None:
            logger.warning("ProfileCache: no DB row for user %s — using defaults", user_id)
            return ProfileConfig(
                profile_id=None,
                model_name="gpt-4.1-mini",
                temperature=0.7,
                max_turns=100,
                prompt_content=None,
                allowed_tools=[],   # fail-closed
            )

        is_admin: bool = bool(row["is_admin"])

        # Admin bypass: no tool restriction
        if is_admin:
            return ProfileConfig(
                profile_id=row["profile_id"],
                model_name=row["model_name"],
                temperature=float(row["temperature"]),
                max_turns=int(row["max_turns"]),
                prompt_content=row["prompt_content"],
                allowed_tools=None,  # None = unrestricted
            )

        # Non-admin: tool list from profile_tools
        raw_tools: list[str] | None = row["tool_names"]
        if raw_tools is None:
            # No profile assigned at all
            logger.warning(
                "ProfileCache: user %s has no agent profile — denying all tools (fail-closed)",
                user_id,
            )
            allowed_tools: list[str] = []
        elif len(raw_tools) == 0:
            logger.warning(
                "ProfileCache: user %s profile has no tools configured — denying all tools",
                user_id,
            )
            allowed_tools = []
        else:
            allowed_tools = raw_tools

        return ProfileConfig(
            profile_id=row["profile_id"],
            model_name=row["model_name"],
            temperature=float(row["temperature"]),
            max_turns=int(row["max_turns"]),
            prompt_content=row["prompt_content"],
            allowed_tools=allowed_tools,
        )
