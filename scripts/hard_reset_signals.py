import redis
import asyncpg
import asyncio
import os
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("hard-reset")

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6380))
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://aureus:aureus_password@localhost:5433/aureus")

async def main():
    logger.info("🧨 Starting Hard Reset...")

    # 1. Clear Redis
    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
        r.flushall()
        logger.info("✅ Redis FLUSHALL complete.")
    except Exception as e:
        logger.error(f"❌ Redis flush failed: {e}")

    # 2. Clear DB Snapshots
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        # Using TRUNCATE with RESTART IDENTITY to be thorough
        await conn.execute("TRUNCATE TABLE aureus_signal_snapshots RESTART IDENTITY CASCADE;")
        logger.info("✅ Table 'aureus_signal_snapshots' truncated.")
        
        # Optional: clear swing points if we want true scratch (already handled by engine if snapshots missing, but safer)
        await conn.execute("TRUNCATE TABLE aureus_swing_points RESTART IDENTITY CASCADE;")
        logger.info("✅ Table 'aureus_swing_points' truncated.")

        await conn.close()
    except Exception as e:
        logger.error(f"❌ DB truncate failed: {e}")

    logger.info("✨ Hard Reset finished. Please restart the aureus-signal service to begin full recalculation.")

if __name__ == "__main__":
    asyncio.run(main())
