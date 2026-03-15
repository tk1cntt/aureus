import asyncpg
import asyncio
import os
from datetime import datetime, timedelta

POSTGRES_URL = "postgresql://postgres:aureus_password@localhost:5432/aureus"

async def diagnose():
    conn = await asyncpg.connect(POSTGRES_URL)
    try:
        # Check latest candles
        latest_candle = await conn.fetchrow("SELECT time FROM aureus_candles ORDER BY time DESC LIMIT 1")
        print(f"Latest candle: {latest_candle['time'] if latest_candle else 'N/A'}")
        
        # Check latest swing points
        latest_sp = await conn.fetchrow("SELECT symbol, time, type, price FROM aureus_swing_points ORDER BY time DESC LIMIT 1")
        print(f"Latest swing point: {latest_sp['symbol']} {latest_sp['time']} {latest_sp['type']} {latest_sp['price'] if latest_sp else 'N/A'}")
        
        # Check a specific range (e.g., Run #11 range)
        run = await conn.fetchrow("SELECT symbol, start_time, end_time FROM aureus_backtest_runs WHERE id = 11")
        if run:
            symbol = run['symbol']
            start = run['start_time']
            end = run['end_time']
            print(f"\nRun #11: {symbol} from {start} to {end}")
            
            candle_count = await conn.fetchval("SELECT count(*) FROM aureus_candles WHERE symbol = $1 AND time >= $2 AND time < $3", symbol, start, end)
            sp_count = await conn.fetchval("SELECT count(*) FROM aureus_swing_points WHERE symbol = $1 AND time >= $2 AND time < $3", symbol, start, end)
            
            print(f"Candles in range: {candle_count}")
            print(f"Swing points in range: {sp_count}")
            
            if sp_count > 0:
                sample_sps = await conn.fetch("SELECT time, type, price FROM aureus_swing_points WHERE symbol = $1 AND time >= $2 AND time < $3 ORDER BY time ASC LIMIT 5", symbol, start, end)
                print("\nSample swing points:")
                for sp in sample_sps:
                    print(f"  {sp['time']} {sp['type']} {sp['price']}")
                    
            # Check if swing labels exist in snapshots (the old way)
            snap_sp_count = await conn.fetchval("SELECT count(*) FROM aureus_signal_snapshots WHERE symbol = $1 AND time >= $2 AND time < $3 AND swing_label IS NOT NULL", symbol, start, end)
            print(f"Snapshots with swing_label: {snap_sp_count}")

    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(diagnose())
