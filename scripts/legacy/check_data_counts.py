import asyncpg
import asyncio
from datetime import datetime, timedelta

async def run():
    try:
        conn = await asyncpg.connect('postgresql://aureus:aureus_password@localhost:5432/aureus')
        rows = await conn.fetch('''
            SELECT date_trunc('day', time) as day, count(*) 
            FROM aureus_signal_snapshots 
            GROUP BY day 
            ORDER BY day DESC 
            LIMIT 10;
        ''')
        print("Snapshots per day:")
        for r in rows:
            print(f"{r[0]}: {r[1]}")
        
        # Also check candles
        c_rows = await conn.fetch('''
            SELECT date_trunc('day', time) as day, count(*) 
            FROM aureus_candles 
            GROUP BY day 
            ORDER BY day DESC 
            LIMIT 10;
        ''')
        print("\nCandles per day:")
        for r in c_rows:
            print(f"{r[0]}: {r[1]}")
            
        await conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(run())
