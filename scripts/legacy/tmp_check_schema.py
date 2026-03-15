import asyncio
import asyncpg
import json

async def check():
    conn = await asyncpg.connect('postgresql://aureus:aureus_password@localhost:5432/aureus')
    
    columns = await conn.fetch("SELECT column_name FROM information_schema.columns WHERE table_name = 'aureus_backtest_runs';")
    print(f"Columns in aureus_backtest_runs: {[r['column_name'] for r in columns]}")
    
    await conn.close()

if __name__ == "__main__":
    asyncio.run(check())
