"""One-time script to clear old data from TimescaleDB and Redis."""
import asyncio
import asyncpg
import redis

async def clear_all():
    # 1. Clear TimescaleDB
    print("Clearing TimescaleDB...")
    conn = await asyncpg.connect("postgresql://aureus:aureus_password@localhost:5433/aureus")
    await conn.execute("DELETE FROM aureus_candles WHERE symbol = 'XAUUSD'")
    count = await conn.fetchval("SELECT count(*) FROM aureus_candles")
    print(f"  DB cleared. Remaining rows: {count}")
    await conn.close()

    # 2. Clear Redis
    print("Clearing Redis (flushdb)...")
    r = redis.Redis(host="localhost", port=6380, decode_responses=True)
    r.flushdb()
    r.close()
    print("Done! All old data cleared.")

if __name__ == "__main__":
    asyncio.run(clear_all())
