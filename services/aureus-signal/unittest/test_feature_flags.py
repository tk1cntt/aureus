"""
Unit tests for FeatureFlags — Story 9.1

Tests:
  - AC1: Flag Reader — reads aureus:config:{key} from Redis
  - AC2: Caching — returns cached value within TTL
  - AC3: Default Safe — returns default when key missing
  - AC4: No Crash — returns default when Redis unreachable
"""
import asyncio
import time

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from engine.feature_flags import FeatureFlags


class FakeRedis:
    """Minimal async Redis mock for testing."""
    
    def __init__(self, data=None):
        self._data = data or {}
    
    async def get(self, key):
        return self._data.get(key)
    
    def set_value(self, key, value):
        self._data[key] = value


class BrokenRedis:
    """Redis mock that always raises ConnectionError."""
    
    async def get(self, key):
        raise ConnectionError("Redis connection refused")


def run(coro):
    """Helper to run async test in sync context."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# --- AC1: Flag Reader ---

def test_reads_from_redis():
    """AC1: FeatureFlags reads aureus:config:{key} from Redis."""
    r = FakeRedis({"aureus:config:snapshot_mode": "SPARSE"})
    flags = FeatureFlags(r, ttl=60)
    
    result = run(flags.get("snapshot_mode", "FULL"))
    assert result == "SPARSE", f"Expected SPARSE, got {result}"


def test_reads_correct_prefix():
    """AC1: Key is prefixed with aureus:config:"""
    r = FakeRedis({"aureus:config:redis_sync_mode": "EVENT_ONLY"})
    flags = FeatureFlags(r, ttl=60)
    
    result = run(flags.get("redis_sync_mode", "ALWAYS"))
    assert result == "EVENT_ONLY"


# --- AC2: Caching ---

def test_cache_returns_cached_value():
    """AC2: Second call returns cached value without hitting Redis again."""
    r = FakeRedis({"aureus:config:snapshot_mode": "SPARSE"})
    flags = FeatureFlags(r, ttl=60)
    
    # First call — reads from Redis
    result1 = run(flags.get("snapshot_mode", "FULL"))
    assert result1 == "SPARSE"
    
    # Change Redis value
    r.set_value("aureus:config:snapshot_mode", "FULL")
    
    # Second call — should still return cached "SPARSE"
    result2 = run(flags.get("snapshot_mode", "FULL"))
    assert result2 == "SPARSE", f"Cache miss! Got {result2} instead of cached SPARSE"


def test_cache_expires_after_ttl():
    """AC2: Cache expires after TTL, re-reads from Redis."""
    r = FakeRedis({"aureus:config:snapshot_mode": "SPARSE"})
    flags = FeatureFlags(r, ttl=1)  # 1 second TTL for test
    
    # First call
    result1 = run(flags.get("snapshot_mode", "FULL"))
    assert result1 == "SPARSE"
    
    # Change value and wait for cache to expire
    r.set_value("aureus:config:snapshot_mode", "FULL")
    time.sleep(1.1)
    
    # Should re-read from Redis
    result2 = run(flags.get("snapshot_mode", "FULL"))
    assert result2 == "FULL", f"Cache didn't expire! Got {result2}"


# --- AC3: Default Safe ---

def test_returns_default_when_key_missing():
    """AC3: Returns default value when Redis key doesn't exist."""
    r = FakeRedis({})  # Empty Redis
    flags = FeatureFlags(r, ttl=60)
    
    result = run(flags.get("snapshot_mode", "FULL"))
    assert result == "FULL", f"Expected default FULL, got {result}"


def test_returns_default_for_unknown_key():
    """AC3: Returns default for any unknown key."""
    r = FakeRedis({})
    flags = FeatureFlags(r, ttl=60)
    
    result = run(flags.get("nonexistent_flag", "DEFAULT_VALUE"))
    assert result == "DEFAULT_VALUE"


# --- AC4: No Crash ---

def test_no_crash_on_redis_error():
    """AC4: Returns default and doesn't crash when Redis is unreachable."""
    r = BrokenRedis()
    flags = FeatureFlags(r, ttl=60)
    
    # Should NOT raise, should return default
    result = run(flags.get("snapshot_mode", "FULL"))
    assert result == "FULL", f"Expected FULL on error, got {result}"


def test_no_crash_caches_default_on_error():
    """AC4: After Redis error, default is cached and subsequent calls don't retry."""
    r = BrokenRedis()
    flags = FeatureFlags(r, ttl=60)
    
    result1 = run(flags.get("snapshot_mode", "FULL"))
    assert result1 == "FULL"
    
    # Second call should use cache (no retry)
    result2 = run(flags.get("snapshot_mode", "FULL"))
    assert result2 == "FULL"


# --- Invalidation ---

def test_invalidate_single_key():
    """Invalidating a key forces re-read on next get."""
    r = FakeRedis({"aureus:config:snapshot_mode": "SPARSE"})
    flags = FeatureFlags(r, ttl=60)
    
    run(flags.get("snapshot_mode", "FULL"))  # Cache it
    
    r.set_value("aureus:config:snapshot_mode", "FULL")
    flags.invalidate("snapshot_mode")
    
    result = run(flags.get("snapshot_mode", "FULL"))
    assert result == "FULL", f"Invalidation didn't work, got {result}"


def test_invalidate_all():
    """Invalidating all keys clears entire cache."""
    r = FakeRedis({
        "aureus:config:snapshot_mode": "SPARSE",
        "aureus:config:redis_sync_mode": "EVENT_ONLY"
    })
    flags = FeatureFlags(r, ttl=60)
    
    run(flags.get("snapshot_mode", "FULL"))
    run(flags.get("redis_sync_mode", "ALWAYS"))
    
    flags.invalidate()  # Clear all
    
    assert len(flags._cache) == 0


# --- get_all ---

def test_get_all_returns_all_flags():
    """get_all returns dict of all known flags."""
    r = FakeRedis({
        "aureus:config:snapshot_mode": "SPARSE",
        "aureus:config:redis_sync_mode": "EVENT_ONLY"
    })
    flags = FeatureFlags(r, ttl=60)
    
    result = run(flags.get_all())
    assert result == {"snapshot_mode": "SPARSE", "redis_sync_mode": "EVENT_ONLY"}


def test_get_all_returns_defaults_when_empty():
    """get_all returns defaults when no flags set."""
    r = FakeRedis({})
    flags = FeatureFlags(r, ttl=60)
    
    result = run(flags.get_all())
    assert result == {"snapshot_mode": "FULL", "redis_sync_mode": "ALWAYS"}


# --- Runner ---

if __name__ == "__main__":
    tests = [
        test_reads_from_redis,
        test_reads_correct_prefix,
        test_cache_returns_cached_value,
        test_cache_expires_after_ttl,
        test_returns_default_when_key_missing,
        test_returns_default_for_unknown_key,
        test_no_crash_on_redis_error,
        test_no_crash_caches_default_on_error,
        test_invalidate_single_key,
        test_invalidate_all,
        test_get_all_returns_all_flags,
        test_get_all_returns_defaults_when_empty,
    ]
    
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  [PASS] {t.__name__}")
            passed += 1
        except Exception as e:
            print(f"  [FAIL] {t.__name__}: {e}")
            failed += 1
    
    print(f"\n--- Results: {passed} PASSED, {failed} FAILED ---")
