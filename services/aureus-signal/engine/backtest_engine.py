"""
Aureus Backtest Engine V5 — Core processor for historical data.
This module is isolated from the live engine to prevent production interference.
"""
import asyncio
import os
import json
import asyncpg
import redis.asyncio as redis
from datetime import datetime, timezone, timedelta
import time
from dotenv import load_dotenv

from engine.logging_common import get_logger

from engine.manager import WindowManager
from engine.signal_factory import create_signal_set
from engine.snapshot_utils import build_snapshot, insert_single_snapshot, batch_insert_snapshots
from engine.strategies.registry import StrategyRegistry
from engine.strategies.seed_strategies import seed_system_strategies
# from engine.gap_detector import GapDetector  # Live-only
from engine.simulated_orders import SimulatedTradeManager
from engine.mock_producer import CSVMockProducer
from engine.event_filter import has_structural_event
# from engine.ai_validator import AIValidator       # Live-only
# from engine.signals.news_provider import NewsProvider # Live-only

logger = get_logger(__name__)
def load_symbols_config(path="symbols.json"):
    try:
        if not os.path.exists(path):
            return {}
        with open(path, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"[GLOBAL] [load_symbols_config] Failed to load {path}: {e}")
        return {}

def get_redis_key(run_id: str, symbol: str, base_key: str) -> str:
    """Adds aureus:backtest:{run_id}:{symbol}: prefix to any base key."""
    # Remove any leading 'aureus:' if present to avoid double prefixing
    clean_base = base_key
    if base_key.startswith("aureus:"):
        clean_base = base_key.replace("aureus:", "", 1)
    
    return f"aureus:backtest:{run_id}:{symbol}:{clean_base}"

async def startup_reaper(r: redis.Redis, symbol: str, current_run_id: str):
    """Layer 0: Scans and removes orphaned keys for the specific symbol."""
    pattern = f"aureus:backtest:*:{symbol}:*"
    logger.info(f"[{symbol}] [startup_reaper] 1... Scanning for orphaned keys with pattern: {pattern}")
    
    count = 0
    async for key in r.scan_iter(match=pattern):
        # Don't delete keys belonging to the current run
        if f":{current_run_id}:" not in key:
            logger.info(f"[{symbol}] [startup_reaper] 2... Unlinking orphaned key: {key}")
            await r.unlink(key)
            count += 1
            
    if count > 0:
        logger.info(f"[{symbol}] [startup_reaper] 3... Cleaned up {count} orphaned keys")

async def graceful_teardown(r: redis.Redis, run_id: str, symbol: str):
    """Layer 1: Explicitly removes all keys for the current run/symbol."""
    pattern = f"aureus:backtest:{run_id}:{symbol}:*"
    logger.info(f"[{symbol}] [graceful_teardown] 1... Tearing down run {run_id}...")
    
    count = 0
    async for key in r.scan_iter(match=pattern):
        await r.unlink(key)
        count += 1
        
    logger.info(f"[{symbol}] [graceful_teardown] 2... Removed {count} keys.")

async def run_backtest_engine(run_id: str, symbol: str, start_dt: datetime, end_dt: datetime):
    """
    Backtest Engine V5 - Clone & Isolate from Live Engine.
    
    Khung rỗng chuẩn bị cho:
    - Epic 2: DB/Redis Isolation  
    - Epic 3: Queue Simulator + Consumer Loop
    """
    load_dotenv()

    redis_host = os.getenv("REDIS_HOST", "redis")
    redis_port = int(os.getenv("REDIS_PORT", 6379))
    db_dsn = os.getenv("DATABASE_URL", "postgresql://aureus:aureus_password@localhost:5432/aureus")
    
    logger.info(f"[{symbol}] [run_backtest_engine] 1... Initializing for RunID: {run_id}")

    # --- Connect Redis ---
    logger.info(f"[{symbol}] [run_backtest_engine] 2... Connecting to Redis: {redis_host}:{redis_port}")
    r = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)

    try:
        # --- [Story 2.3]: Layer 0 - Startup Reaper ---
        await startup_reaper(r, symbol, run_id)

        # --- Connect TimescaleDB ---
        logger.info(f"[{symbol}] [run_backtest_engine] 3... Connecting to Database: {db_dsn.split('@')[-1]}") # Log host/db only
        db_pool = await asyncpg.create_pool(db_dsn, min_size=2, max_size=10) # Reduced pool for backtest
        logger.info(f"[{symbol}] [run_backtest_engine] 4... Database connection pool created.")

        # --- Shared Components ---
        window_manager = WindowManager(max_window=2000)
        
        # Init Registry & Signals
        strategy_registry = StrategyRegistry()
        await seed_system_strategies(db_pool) # Still seed system strategies
        
        # Load symbol-specific parameters (mostly for signal digits/pivots)
        SYMBOL_CONFIG = load_symbols_config()
        cfg = SYMBOL_CONFIG.get(symbol, SYMBOL_CONFIG.get("XAUUSD", {}))
        
        signals = create_signal_set(symbol, cfg)
        
        # Init SimulatedTradeManager
        trade_manager = SimulatedTradeManager(r=r, run_id=run_id)
        
        # --- [Story 2.2]: Redis Prefixing ---
        # get_redis_key is now a module-level function
        
        # --- [Story 2.1]: Isolated DB Configuration ---
        snapshot_table = "aureus_backtest_snapshots"
        candle_table = "aureus_backtest_candles"
        logger.info(f"[BT-V5] Using isolated tables: Snapshots={snapshot_table}, Candles={candle_table}")

        # REVIEW FIX 3: Clear History State at Startup
        history_key = get_redis_key(run_id, symbol, "orders:history")
        await r.delete(history_key)

        # --- [Story 3.2]: Mock Producer (DB to Stream) ---
        stream_key = get_redis_key(run_id, symbol, "stream")
        producer = CSVMockProducer(db_pool, r, run_id, symbol, stream_key)
        
        # --- [Story 3.3]: Backtest Consumer Loop ---
        logger.info(f"[{symbol}] [run_backtest_engine] 5... Ready to start Loop on stream: {stream_key}")
        
        state = window_manager.states[symbol] if symbol in window_manager.states else None
        
        async def consumer_task():
            last_id = "0-0"
            processed_count = 0
            empty_reads = 0
            
            while True:
                # Read from stream (blocking for up to 2 seconds)
                messages = await r.xread({stream_key: last_id}, count=500, block=2000)
                
                if not messages:
                    empty_reads += 1
                    # If we waited multiple times and producer is likely done, exit loop
                    if empty_reads > 2:
                        logger.info(f"[{symbol}] [consumer_task] 1... Stream empty. Finished processing {processed_count} candles.")
                        break
                    continue
                
                empty_reads = 0
                for _, entries in messages:
                    for msg_id, data in entries:
                        try:
                            payload_str = data.get('payload')
                            if not payload_str:
                                continue
                                
                            candle_data = json.loads(payload_str)
                            if candle_data.get('type') != 'CANDLE':
                                last_id = msg_id
                                continue
                            
                            # Set current time state
                            ts_str = candle_data.get('t')
                            ts_dt = datetime.fromisoformat(ts_str)
                            # We need a proper unix timestamp for the pipeline
                            ts_unix = int(ts_dt.timestamp())
                            
                            # Re-map payload to match what pipeline expects ('t', 'o', 'h', 'l', 'c', 'v')
                            mapped_candle = {
                                'symbol': symbol,
                                't': str(ts_unix),
                                'o': str(candle_data['o']),
                                'h': str(candle_data['h']),
                                'l': str(candle_data['l']),
                                'c': str(candle_data['c']),
                                'v': str(candle_data['v'])
                            }
                            
                            # Pipeline Step 1: Update Window Manager
                            df, c_state = window_manager.update(symbol, mapped_candle)
                            c_state.transient_signals = {}
                            
                            # REVIEW FIX: Compute is_warmup BEFORE len(df) check
                            # to avoid UnboundLocalError on first 4 candles
                            is_warmup = ts_unix < int(start_dt.timestamp())
                            
                            # Pipeline Step 2: Signal Calculation
                            if df is not None and len(df) >= 5:
                                for tag, signal_calc in signals.items():
                                    try:
                                        res = signal_calc.calculate(df, c_state, redis_client=r, symbol=symbol)
                                        if res:
                                            t_tag = res.get('tag')
                                            if t_tag: c_state.log_signal(t_tag, ts_unix)
                                            t_cross = res.get('cross')
                                            if t_cross: c_state.log_signal(t_cross, ts_unix)
                                    except Exception as e:
                                        logger.error(f"Signal {tag} calc error: {e}")
                                # Story 3.4: Trade Lock Mechanism during 24H Warmup
                                # is_warmup already computed above before len(df) check
                                
                                if not is_warmup:
                                    # Pipeline Step 3: Strategy Evaluation (Multi-Strategy)
                                    strategy_results = strategy_registry.evaluate_all(df, signals, c_state)
                                    
                                    # Pipeline Step 4: Simulated Order Management
                                    if strategy_results:
                                        new_orders = await trade_manager.process_triggers(symbol, strategy_results, c_state)
                                        if new_orders > 0:
                                            for res in strategy_results:
                                                logger.debug(f"[{symbol}] STRATEGY TRIGGERED: {res['strategy']}")
                                                c_state.log_signal(f"strat:{res['strategy']}", ts_unix)
    
                                    # REVIEW FIX: Reset events at engine level for clean tick lifecycle
                                    # process_triggers may have appended ORDER_OPENED above
                                    # update_orders will append SL_HIT/TP_HIT below
                                    # Do NOT clear here — let both contribute to this tick's events
                                    trade_manager.update_orders(symbol, mapped_candle, c_state)

                            # --- [Story 3.5]: Event-Driven Sparse Storage ---
                            if not is_warmup:
                                # 1. Always sync to Redis for Real-time Dashboard (UI state)
                                state_key = get_redis_key(run_id, symbol, "state")
                                await r.set(state_key, json.dumps(c_state.to_dict()))

                                # 2. Only persist to TimescaleDB if a significant event occurred
                                if has_structural_event(c_state, trade_manager):
                                    snapshot = build_snapshot(c_state, mapped_candle)
                                    await insert_single_snapshot(db_pool, snapshot, snapshot_table)
                                
                                # 3. [Story 3.5] Clear trade events for next candle
                                trade_manager.last_tick_events = []
                            
                            # Acknowledge & Delete handled message to save memory
                            await r.xdel(stream_key, msg_id)
                            
                            last_id = msg_id
                            processed_count += 1
                            
                            if processed_count % 1000 == 0:
                                logger.debug(f"[{symbol}] [consumer_task] 2... Processed {processed_count} candles... Time: {ts_str}")
                                
                        except Exception as e:
                            logger.error(f"Error processing candle {msg_id}: {e}")
                            last_id = msg_id # Skip bad message
                            
            # Return stats to caller
            return processed_count, trade_manager.get_stats()

        # REVIEW FIX 2: Run Producer and Consumer Concurrently
        # This prevents the Redis Stream from blowing up RAM on large historical arrays.
        producer_task = asyncio.create_task(producer.produce(start_dt, end_dt))
        consumer_task = asyncio.create_task(consumer_task())
        
        _, (proc_count, stats) = await asyncio.gather(producer_task, consumer_task)
        
        logger.info(f"[{symbol}] [run_backtest_engine] 6... Backtest complete. Total: {proc_count}")
        logger.info(f"[{symbol}] [run_backtest_engine] 7... Results: {json.dumps(stats)}")
        
        return proc_count, stats


    finally:
        # --- [Story 2.3]: Layer 1 - Graceful Teardown ---
        if 'r' in locals():
            await graceful_teardown(r, run_id, symbol)
            await r.aclose()
        if 'db_pool' in locals():
            await db_pool.close()

# AI Logic and Background Tasks removed for Backtest V5 isolate.
