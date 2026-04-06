"""
Idempotency checker — dedup order commands via Redis with TTL.

Uses Redis SET ... NX for atomic check-and-mark to prevent
race conditions when multiple order commands arrive concurrently.
"""


class IdempotencyChecker:
    """Check and mark processed order commands using Redis dedup keys.

    Key format: aureus:trader:dedup:{cmd_id}
    Default TTL: 86400 seconds (24 hours)
    """

    def __init__(self, redis_client, ttl: int = 86400):
        self.redis = redis_client
        self.ttl = ttl

    async def is_duplicate(self, cmd_id: str) -> bool:
        """Check if cmd_id was already processed."""
        key = f"aureus:trader:dedup:{cmd_id}"
        return await self.redis.exists(key) > 0

    async def mark_processed(self, cmd_id: str) -> None:
        """Mark cmd_id as processed with TTL expiry."""
        key = f"aureus:trader:dedup:{cmd_id}"
        await self.redis.set(key, "1", ex=self.ttl)

    async def check_and_mark(self, cmd_id: str) -> bool:
        """Atomic check-and-mark. Returns True if NEW (not duplicate).

        Uses Redis SET ... NX for race-condition safety.
        """
        key = f"aureus:trader:dedup:{cmd_id}"
        # SET with NX returns True only if key was set (new)
        result = await self.redis.set(key, "1", ex=self.ttl, nx=True)
        return result is not None
