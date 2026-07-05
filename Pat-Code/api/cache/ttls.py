"""TTL constants for all Redis cache keys — single source of truth."""

TTL_USER          = 30 * 60        # 30 min
TTL_PROFILE       = 60 * 60        # 1 hr
TTL_PROFILE_DEF   = 7  * 60 * 60   # 7 hr
TTL_PROFILES_ALL  = 60 * 60        # 1 hr
TTL_TOOLS_PROFILE = 2  * 60 * 60   # 2 hr
TTL_CONNECTED     = 60 * 60        # 1 hr
# pat:tools:registry — NO TTL, invalidation-only
