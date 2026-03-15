import asyncio
import os
import asyncpg
from datetime import datetime, timedelta
from engine.backtest_engine import run_backtest_engine
from dotenv import load_dotenv

async def verify_sparse_storage():
    load_dotenv()
    db_dsn = os.getenv("DATABASE_URL", "postgresql://aureus:aureus_password@localhost:5433/aureus")
    
    run_id = f"verify_3_5_{int(datetime.now().timestamp())}"
    symbol = "XAUUSD"
    # Use available data range from DB
    end_dt = datetime(2026, 2, 8)
    start_dt = datetime(2026, 2, 5)
    
    print(f"--- Starting Verification for Story 3.5 ---")
    print(f"Run ID: {run_id}")
    print(f"Period: {start_dt} to {end_dt}")

    # 1. Clean up potential old data for this run_id (should be empty anyway)
    conn = await asyncpg.connect(db_dsn)
    await conn.execute("DELETE FROM aureus_backtest_snapshots WHERE symbol = $1", symbol)
    await conn.close()

    # 2. Run Backtest
    # Note: run_backtest_engine returns processed_count, stats
    # We need to wrap it because it has its own pool management
    try:
        # We need to mock some things or ensure markers exist in the sample data
        # for these 3 days to trigger some snapshots.
        processed_count, stats = await run_backtest_engine(run_id, symbol, start_dt, end_dt)
    except Exception as e:
        print(f"Backtest failed: {e}")
        return

    # 3. Count Snapshots
    conn = await asyncpg.connect(db_dsn)
    snapshot_count = await conn.fetchval(
        "SELECT COUNT(*) FROM aureus_backtest_snapshots WHERE symbol = $1", 
        symbol
    )
    
    # We need total processed count. In our test case, it should be around 4320.
    # But let's fetch it from a hypothetical candle count or just use the log output.
    # Actually, let's just use the ratio logic.
    
    print(f"Snapshots saved: {snapshot_count}")
    
    # For 3 days (4320 mins), 20% is 864. 
    # If it's a quiet market, it might be even lower.
    
    # REVIEW FIX: processed_count includes ~1440 warmup candles (Story 3.4)
    # Snapshots are only written AFTER warmup, so subtract warmup from denominator
    warmup_candles = 1440  # 1-day fast-forward warmup
    real_candles = max(1, (processed_count - warmup_candles)) if processed_count > warmup_candles else processed_count
    
    print(f"Actual Processed Candles (total): {processed_count}")
    print(f"Real Candles (excluding warmup): {real_candles}")
    
    ratio = (snapshot_count / real_candles) * 100 if real_candles > 0 else 0
    
    print(f"Storage Ratio: {ratio:.2f}%")
    
    if ratio <= 20.0:
        print("✅ SUCCESS: Storage ratio is within limits (<= 20%)")
    else:
        print(f"❌ FAILURE: Storage ratio {ratio:.2f}% exceeds 20% limit")
        
    await conn.close()

if __name__ == "__main__":
    asyncio.run(verify_sparse_storage())
