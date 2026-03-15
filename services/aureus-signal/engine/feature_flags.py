"""
Feature Flags — Lightweight Redis-backed feature flag system.

Reads configuration keys from Redis with caching to minimize overhead.
Used by Live Engine V2 for toggling Sparse Storage, Conditional Redis Sync, etc.

Keys:
  aureus:config:snapshot_mode   → "FULL" (default) | "SPARSE"
  aureus:config:redis_sync_mode → "ALWAYS" (default) | "EVENT_ONLY"

Toggle via redis-cli:
  SET aureus:config:snapshot_mode SPARSE
"""
import time
import logging
from typing import Dict, Optional

logger = logging.getLogger("aureus-signal")

# Default cache TTL in seconds
DEFAULT_CACHE_TTL = 60


class FeatureFlags:
    """Reads feature flags from Redis config keys with local caching.
    
    Attributes:
        r: Async Redis client instance.
        _cache: Dict mapping key -> (value, expiry_time).
        _ttl: Cache TTL in seconds.
    """

    def __init__(self, r, ttl: int = DEFAULT_CACHE_TTL):
        self.r = r
        self._cache: Dict[str, tuple] = {}  # key -> (value, expiry_timestamp)
        self._ttl = ttl

    async def get(self, key: str, default: str = "") -> str:
        """Read a feature flag value from Redis, with caching.
        
        Args:
            key: Flag key name (without prefix). Will be read as aureus:config:{key}.
            default: Default value if key doesn't exist or Redis is unreachable.
            
        Returns:
            The flag value string, or default.
        """
        now = time.monotonic()

        # Check cache first
        if key in self._cache:
            cached_value, expiry = self._cache[key]
            if now < expiry:
                return cached_value

        # Cache miss or expired — read from Redis
        try:
            redis_key = f"aureus:config:{key}"
            value = await self.r.get(redis_key)
            result = value if value is not None else default
        except Exception as e:
            # Redis unreachable — return default, don't crash
            logger.warning(f"[FeatureFlags] Redis read failed for '{key}': {e}")
            result = default

        # Update cache
        self._cache[key] = (result, now + self._ttl)
        return result

    def invalidate(self, key: Optional[str] = None):
        """Invalidate cache for a specific key or all keys.
        
        Args:
            key: Specific key to invalidate. If None, invalidates all.
        """
        if key is None:
            self._cache.clear()
        elif key in self._cache:
            del self._cache[key]

    async def get_all(self) -> Dict[str, str]:
        """Read all known feature flags and return as dict.
        
        Useful for logging/debugging current flag state.
        """
        flags = {}
        for key, default in [
            ("snapshot_mode", "FULL"),
            ("redis_sync_mode", "ALWAYS"),
        ]:
            flags[key] = await self.get(key, default)
        return flags
