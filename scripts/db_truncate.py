import asyncpg
import asyncio
import os
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("db-truncate")

# Default for internal docker networking if not provided
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://aureus:aureus_password@localhost:5433/aureus")

async def main():
    logger.info("🧨 Truncating Signal Engine Tables...")
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        await conn.execute("TRUNCATE TABLE aureus_signal_snapshots RESTART IDENTITY CASCADE;")
        logger.info("✅ Table 'aureus_signal_snapshots' truncated.")
        
        await conn.execute("TRUNCATE TABLE aureus_swing_points RESTART IDENTITY CASCADE;")
        logger.info("✅ Table 'aureus_swing_points' truncated.")

        await conn.close()
        logger.info("✨ Database reset complete.")
    except Exception as e:
        logger.error(f"❌ DB truncate failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
