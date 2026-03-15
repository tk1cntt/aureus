"""
Signal Computer — Offline Pre-computation of Signal Snapshots

Reads historical candles from TimescaleDB, replays them through the signal engine,
and stores computed signal values into aureus_signal_snapshots.

Usage:
    python signal_computer.py --symbol XAUUSD --start 2026-01-01 --end 2026-03-01
    python signal_computer.py --symbol XAUUSD --months 6
"""
import asyncio
import argparse
import json
import os
import sys
import time
import logging
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

# Ensure engine is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import asyncpg
import redis.asyncio as redis_lib

from engine.manager import WindowManager
from engine.signal_factory import create_signal_set
from engine.snapshot_utils import build_snapshot, batch_insert_snapshots

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("signal-computer")


def load_symbols_config(path="symbols.json"):
    try:
        if not os.path.exists(path):
            return {}
        with open(path, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load {path}: {e}")
        return {}


async def precompute_signals(symbol: str, start_dt: datetime, end_dt: datetime, 
                              db_dsn: str, redis_url: str = None):
    """
    Pre-compute all signals for a symbol over a date range.
    
    Args:
        symbol: e.g. "XAUUSD"
        start_dt: Start of range (inclusive)
        end_dt: End of range (exclusive)
        db_dsn: PostgreSQL connection string
        redis_url: Optional Redis URL for progress tracking
    """
    t_start = time.time()
    
    # --- Connect ---
    db_pool = await asyncpg.create_pool(db_dsn)
    logger.info(f"DB connected")
    
    r = None
    if redis_url:
        try:
            r = redis_lib.from_url(redis_url, decode_responses=True)
            await r.ping()
            logger.info(f"Redis connected")
        except Exception:
            r = None
            logger.warning("Redis not available, progress tracking disabled")

    # --- Load Config ---
    symbol_config = load_symbols_config()
    cfg = symbol_config.get(symbol, symbol_config.get("XAUUSD", {}))
    
    # --- Load Candles ---
    logger.info(f"Loading candles for {symbol} from {start_dt} to {end_dt}...")
    
    # Load extra lookback for warmup (200 bars for EMA200)
    lookback_start = start_dt - timedelta(hours=4)  # ~240 extra bars for warmup
    
    rows = await db_pool.fetch("""
        SELECT time, open, high, low, close, volume
        FROM aureus_candles
        WHERE symbol = $1 AND time >= $2 AND time < $3
        ORDER BY time ASC
    """, symbol, lookback_start, end_dt)
    
    if not rows:
        logger.error(f"No candles found for {symbol} in range")
        await db_pool.close()
        return
    
    total_candles = len(rows)
    logger.info(f"Loaded {total_candles} candles (includes warmup)")
    
    # --- Initialize Signal Engine ---
    window_manager = WindowManager()
    signals = create_signal_set(symbol, cfg)
    
    # --- Replay Loop ---
    snapshot_batch = []
    processed = 0
    event_count = 0
    batch_size = 500
    
    # Track which rows are in the target range (not warmup)
    target_start_ts = int(start_dt.timestamp())
    
    # Set progress key format
    progress_key = f"aureus:precompute:status:{symbol}"
    
    for i, row in enumerate(rows):
        candle_data = {
            't': str(int(row['time'].timestamp())),
            'o': str(row['open']),
            'h': str(row['high']),
            'l': str(row['low']),
            'c': str(row['close']),
            'v': str(row['volume']),
            'symbol': symbol,
        }
        
        # Update window manager
        df, state = window_manager.update(symbol, candle_data)
        state.transient_signals = {}  # Clear for each candle
        
        # Calculate ALL signals
        if df is not None and len(df) >= 5:
            for tag, signal_calc in signals.items():
                try:
                    res = signal_calc.calculate(df, state, redis_client=None, symbol=symbol)
                    if res:
                        sig_tag = res.get('tag', tag)
                        if sig_tag:
                            state.log_signal(sig_tag, int(candle_data['t']))
                        cross_tag = res.get('cross')
                        if cross_tag:
                            state.log_signal(cross_tag, int(candle_data['t']))
                except Exception as e:
                    if processed < 5:  # Only log first few errors
                        logger.debug(f"Signal {tag} error at candle {i}: {e}")
        
        # Only store snapshots for candles in the target range (not warmup)
        ts_unix = int(candle_data['t'])
        if ts_unix >= target_start_ts:
            snapshot = build_snapshot(state, candle_data)
            snapshot_batch.append(snapshot)
            processed += 1
            
            if snapshot.get('events'):
                event_count += 1
            
            # Batch insert
            if len(snapshot_batch) >= batch_size:
                inserted = await batch_insert_snapshots(db_pool, snapshot_batch)
                snapshot_batch = []
                
                # Log progress
                pct = (processed / max(total_candles, 1)) * 100
                logger.info(f"[{symbol}] Progress: {processed}/{total_candles} ({pct:.1f}%) | Events: {event_count}")
                
                # Update Redis progress
                if r:
                    try:
                        await r.set(progress_key, json.dumps({
                            "symbol": symbol,
                            "processed": processed,
                            "total": total_candles,
                            "progress": round(pct, 1),
                            "status": "COMPUTING",
                            "updated_at": datetime.now(timezone.utc).isoformat()
                        }))
                    except Exception:
                        pass
    
    # Final batch
    if snapshot_batch:
        await batch_insert_snapshots(db_pool, snapshot_batch)
    
    elapsed = time.time() - t_start
    rate = processed / elapsed if elapsed > 0 else 0
    
    logger.info(f"{'='*60}")
    logger.info(f"Pre-computation COMPLETE for {symbol}")
    logger.info(f"  Candles processed: {processed}")
    logger.info(f"  Events detected:   {event_count}")
    logger.info(f"  Duration:          {elapsed:.1f}s")
    logger.info(f"  Rate:              {rate:.0f} candles/s ({1000/max(rate,1):.2f} ms/candle)")
    logger.info(f"{'='*60}")
    
    # Final progress update
    if r:
        try:
            await r.set(progress_key, json.dumps({
                "symbol": symbol,
                "processed": processed,
                "total": processed,
                "progress": 100.0,
                "status": "COMPLETED",
                "duration_s": round(elapsed, 1),
                "event_count": event_count,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }))
        except Exception:
            pass
        await r.aclose()
    
    await db_pool.close()
    return {"processed": processed, "events": event_count, "duration": elapsed}


async def main():
    load_dotenv()
    
    parser = argparse.ArgumentParser(description="Aureus Signal Pre-computation")
    parser.add_argument("--symbol", required=True, help="Symbol to compute (e.g. XAUUSD)")
    parser.add_argument("--start", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", help="End date (YYYY-MM-DD)")
    parser.add_argument("--months", type=int, help="Number of months back from now")
    args = parser.parse_args()
    
    # Determine date range
    if args.months:
        end_dt = datetime.now(timezone.utc)
        start_dt = end_dt - timedelta(days=args.months * 30)
    elif args.start and args.end:
        start_dt = datetime.strptime(args.start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        end_dt = datetime.strptime(args.end, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    else:
        parser.error("Either --months or both --start and --end required")
        return
    
    db_dsn = os.getenv("DATABASE_URL", "postgresql://aureus:aureus_password@localhost:5432/aureus")
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    
    logger.info(f"Starting pre-computation: {args.symbol} | {start_dt.date()} → {end_dt.date()}")
    
    await precompute_signals(args.symbol, start_dt, end_dt, db_dsn, redis_url)


if __name__ == "__main__":
    asyncio.run(main())
