import asyncio
import asyncpg
import json

async def check():
    conn = await asyncpg.connect('postgresql://aureus:aureus_password@localhost:5432/aureus')
    
    symbols = await conn.fetch("SELECT DISTINCT symbol FROM aureus_candles;")
    print(f"Symbols in candles: {[r['symbol'] for r in symbols]}")
    
    for r in symbols:
        sym = r['symbol']
        s_count = await conn.fetchval('SELECT count(*) FROM aureus_signal_snapshots WHERE symbol=$1', sym)
        c_count = await conn.fetchval('SELECT count(*) FROM aureus_candles WHERE symbol=$1', sym)
        
        latest_snapshot = await conn.fetchrow('SELECT time FROM aureus_signal_snapshots WHERE symbol=$1 ORDER BY time DESC LIMIT 1', sym)
        earliest_snapshot = await conn.fetchrow('SELECT time FROM aureus_signal_snapshots WHERE symbol=$1 ORDER BY time ASC LIMIT 1', sym)
        
        print(f"Symbol: {sym}")
        print(f"  Snapshots: {s_count}")
        print(f"  Candles: {c_count}")
        if latest_snapshot:
            print(f"  Snapshot range: {earliest_snapshot['time']} to {latest_snapshot['time']}")
        print("-" * 20)
        
    await conn.close()

if __name__ == "__main__":
    asyncio.run(check())
