import asyncio
import os
import asyncpg
from dotenv import load_dotenv

async def check_db():
    load_dotenv()
    db_dsn = os.getenv("DATABASE_URL", "postgresql://aureus:aureus_password@localhost:5433/aureus")
    
    conn = await asyncpg.connect(db_dsn)
    # Check aureus_backtest_candles
    try:
        rows = await conn.fetch("SELECT symbol, MIN(time), MAX(time), COUNT(*) FROM aureus_backtest_candles GROUP BY symbol;")
        print("--- Table: aureus_backtest_candles ---")
        for r in rows:
            print(f"Symbol: {r[0]}, Min: {r[1]}, Max: {r[2]}, Count: {r[3]}")
    except Exception as e:
        print(f"aureus_backtest_candles check failed: {e}")

    # Check candles
    try:
        rows = await conn.fetch("SELECT symbol, MIN(time), MAX(time), COUNT(*) FROM candles GROUP BY symbol;")
        print("--- Table: candles ---")
        for r in rows:
            print(f"Symbol: {r[0]}, Min: {r[1]}, Max: {r[2]}, Count: {r[3]}")
    except Exception as e:
        print(f"candles check failed: {e}")
        
    await conn.close()

if __name__ == "__main__":
    asyncio.run(check_db())
