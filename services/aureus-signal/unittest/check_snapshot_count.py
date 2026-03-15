import asyncio
import os
import asyncpg
from dotenv import load_dotenv

async def check_count():
    load_dotenv()
    db_dsn = os.getenv("DATABASE_URL", "postgresql://aureus:aureus_password@localhost:5433/aureus")
    conn = await asyncpg.connect(db_dsn)
    count = await conn.fetchval("SELECT COUNT(*) FROM aureus_backtest_snapshots")
    print(f"Total Snapshots: {count}")
    
    # Also check the latest timestamp to see progress
    if count > 0:
        latest = await conn.fetchval("SELECT MAX(time) FROM aureus_backtest_snapshots")
        print(f"Latest Snapshot Time: {latest}")
        
    await conn.close()

if __name__ == "__main__":
    asyncio.run(check_count())
