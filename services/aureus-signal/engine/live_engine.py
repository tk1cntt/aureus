"""
Aureus Signal Engine — Stream consumer + Signal processor + DB writer

Pipeline:  Gateway → Redis Stream → [THIS] → TimescaleDB + Redis State → Dashboard API
"""
import asyncio
import os
import json
import logging
import asyncpg
import redis.asyncio as redis
from datetime import datetime, timezone, timedelta
from typing import Optional, Any
import time
import traceback
from dotenv import load_dotenv

# --- Priority Constants ---
PRIO_TRADE = 1
PRIO_PULSE = 2
_queue_counter = 0  # Monotonic counter for PriorityQueue tiebreaking
SPEC_VERSION = "2026-03-20-live-trading-v1"
ENGINE_VERSION = os.getenv("AUREUS_SIGNAL_ENGINE_VERSION", "live-engine-v1")

from engine.manager import WindowManager
from engine.signal_factory import create_signal_set, build_normalized_signal_snapshot
from engine.snapshot_utils import build_snapshot, insert_single_snapshot, batch_insert_snapshots
from engine.strategies.registry import StrategyRegistry
from engine.strategies.seed_strategies import seed_system_strategies
from engine.gap_detector import GapDetector
from engine.orders import SimulatedTradeManager
from engine.ai_validator import AIValidator
from engine.signals.news_provider import NewsProvider
from engine.feature_flags import FeatureFlags
from engine.event_filter import has_structural_event

# Configure logging
log_level = os.getenv("LOG_LEVEL", "INFO")
log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
log_file = os.getenv("LOG_FILE")

handlers = [logging.StreamHandler()]
if log_file:
    # Ensure directory exists
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    handlers.append(logging.FileHandler(log_file))

logging.basicConfig(
    level=log_level,
    format=log_format,
    handlers=handlers
)
logger = logging.getLogger("aureus-signal.live-engine")


def load_symbols_config(path="symbols.json"):
    try:
        if not os.path.exists(path):
            return {}
        with open(path, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"[GLOBAL] [load_symbols_config] Error: Failed to load {path}: {e}")
        return {}




def enrich_strategy_decisions_with_contract_metadata(strategy_results: list[dict], normalized_snapshot: dict) -> list[dict]:
    """Adds required contract metadata to strategy decision payloads."""
    enriched: list[dict] = []
    for result in strategy_results:
        decision = dict(result)
        decision["spec_version"] = SPEC_VERSION
        decision["engine_version"] = ENGINE_VERSION
        decision["strategy_version"] = str(decision.get("strategy_version") or "v0")
        decision["normalized_signal_snapshot"] = normalized_snapshot
        enriched.append(decision)
    return enriched


def enrich_registry_rejections_with_contract_metadata(
    symbol: str,
    rejections: list[dict],
    normalized_snapshot: dict,
    default_t: int,
) -> list[dict]:
    """Adds required contract metadata to strategy registry rejection payloads."""
    enriched: list[dict] = []
    for record in rejections:
        item = dict(record)
        details = dict(item.get("details") or {})
        event_t = int(details.get("t") or default_t)

        item["symbol"] = symbol
        item["status"] = "REJECTED"
        item["spec_version"] = SPEC_VERSION
        item["engine_version"] = ENGINE_VERSION
        item["strategy_version"] = str(details.get("strategy_version") or item.get("strategy_version") or "v0")
        item["reason_code"] = str(item.get("reason_code") or "UNKNOWN_REJECTION")
        item["t"] = event_t
        item["origin_timestamp"] = int(details.get("origin_timestamp") or details.get("t") or event_t)
        item["normalized_signal_snapshot"] = normalized_snapshot
        item["details"] = details
        enriched.append(item)

    return enriched


async def emit_registry_rejections(redis_client: Any, symbol: str, enriched_rejections: list[dict]):
    """Publishes registry rejection records to orders stream for downstream observability."""
    for rejection in enriched_rejections:
        payload = dict(rejection)
        payload.setdefault("symbol", symbol)
        await redis_client.xadd(
            f"aureus:stream:{symbol}:orders",
            {
                "type": "ORDER_REJECTED",
                "data": json.dumps(payload),
            },
        )




def execute_signals_for_candle(signals: dict, df: Any, state: Any, symbol: str, redis_client: Any) -> None:
    """Executes all signal calculators for the current candle and appends emitted tags into state history."""
    if df is None or len(df) == 0:
        return

    ts_unix = int(df.iloc[-1]["t"])
    for signal_name, signal_calc in signals.items():
        try:
            logger.debug(f"[t={ts_unix}] [{symbol}] [execute_signals_for_candle] Calculating signal {signal_name}")
            res = signal_calc.calculate(df, state, redis_client=redis_client, symbol=symbol)
            if res:
                emitted_tag = res.get("tag")
                if emitted_tag:
                    state.log_signal(emitted_tag, ts_unix)
                cross_tag = res.get("cross")
                if cross_tag:
                    state.log_signal(cross_tag, ts_unix)
        except Exception as e:
            logger.error(f"[t={ts_unix}] [{symbol}] [execute_signals_for_candle] Signal {signal_name} calc error: {e}")


async def run_signal_engine(db_pool: Optional[any] = None, redis_client: Optional[any] = None):
    load_dotenv()

    redis_host = os.getenv("REDIS_HOST", "redis")
    redis_port = int(os.getenv("REDIS_PORT", 6379))
    db_dsn = os.getenv("DATABASE_URL", "postgresql://aureus:aureus_password@localhost:5432/aureus")
    
    # --- Multi-Symbol Configuration ---
    symbols_env = os.getenv("SYMBOLS", "XAUUSD")
    symbols_list = [s.strip() for s in symbols_env.split(",") if s.strip()]
    execution_mode = os.getenv("EXECUTION_MODE", "simulated").strip().lower()
    if execution_mode not in {"simulated", "nautilus"}:
        logger.warning(f"[GLOBAL] [run_signal_engine] Invalid EXECUTION_MODE='{execution_mode}', defaulting to simulated")
        execution_mode = "simulated"
    logger.info(f"[GLOBAL] [run_signal_engine] 1... Initializing Signal Engine for: {symbols_list} | execution_mode={execution_mode}")

    # Load symbol-specific parameters
    SYMBOL_CONFIG = load_symbols_config()

    # --- Connect Redis ---
    if redis_client:
        r = redis_client
        logger.info("[GLOBAL] [run_signal_engine] 2... Using provided Redis client")
    else:
        logger.info(f"[GLOBAL] [run_signal_engine] 2... Connecting to Redis at {redis_host}:{redis_port}...")
        r = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
        
    flags = FeatureFlags(r)

    # --- Connect TimescaleDB ---
    if db_pool:
        logger.info("[GLOBAL] [run_signal_engine] 3... Using provided TimescaleDB pool")
    else:
        logger.info(f"[GLOBAL] [run_signal_engine] 3... Connecting to TimescaleDB...")
        db_pool = await asyncpg.create_pool(db_dsn, min_size=10, max_size=50)
        logger.info(f"[GLOBAL] [run_signal_engine] 4... TimescaleDB pool connected with max_size=50")

    # --- Seed System Strategies ---
    logger.info("[GLOBAL] [run_signal_engine] 5... Seeding system strategies...")
    await seed_system_strategies(db_pool)

    # --- Shared Components ---
    window_manager = WindowManager(max_window=2000)
    trade_manager = SimulatedTradeManager(r)
    ai_validator = AIValidator() # Uses host.docker.internal via env
    
    # Init LLM model from Redis
    active_model = await r.get("aureus:config:llm_model")
    if active_model:
        ai_validator.set_model(active_model)
        
    ai_queue = asyncio.PriorityQueue()
    
    # --- News System Initialization (Non-blocking) ---
    logger.info("[GLOBAL] [run_signal_engine] 6... Initializing News System...")
    asyncio.create_task(asyncio.to_thread(NewsProvider.fetch_this_week)) 
    
    # Spawn Brain Workers
    for i in range(2):
        asyncio.create_task(brain_worker(ai_queue, r, db_pool, ai_validator, trade_manager))
    logger.info("[GLOBAL] [run_signal_engine] 7... Brain Worker pool initialized (Size: 2)")
    
    # --- Per-Symbol Registry ---
    symbol_signals = {}      # symbol -> {tag: signal_obj}
    symbol_locks = {}        # symbol -> Lock
    target_streams = {}      # stream_key -> symbol
    symbol_strategies = {}   # symbol -> StrategyRegistry

    for symbol in symbols_list:
        cfg = SYMBOL_CONFIG.get(symbol, SYMBOL_CONFIG.get("XAUUSD", {}))
        if not cfg:
            logger.warning(f"[{symbol}] [run_signal_engine] Error: No config found for {symbol}, using defaults.")
            cfg = {"digits": 2, "point": 0.01, "pivots": {"ext_period": 5, "min_amplitude": 100, "min_motion": 1}}

        # Instantiate signals with symbol-specific params (via shared factory)
        symbol_signals[symbol] = create_signal_set(symbol, cfg)
        
        symbol_locks[symbol] = asyncio.Lock()
        
        stream_key = f"aureus:stream:{symbol}:candle"
        target_streams[stream_key] = symbol
        
        # Load strategies for this symbol (each symbol gets its own registry)
        symbol_strategies[symbol] = StrategyRegistry()
        await symbol_strategies[symbol].load_from_db(db_pool, symbol)

    # --- Consumer Group Setup ---
    group_name = "aureus-signal-group"
    consumer_name = f"consumer-{os.getenv('HOSTNAME', 'local')}"

    for symbol in symbols_list:
        target_stream = f"aureus:stream:{symbol}:candle"
        try:
            await r.xgroup_create(target_stream, group_name, id="0", mkstream=True)
            logger.info(f"[{symbol}] [run_signal_engine] 8... Created consumer group {group_name}")
        except Exception as e:
            if "already exists" not in str(e):
                logger.error(f"[{symbol}] [run_signal_engine] Error: Group creation error: {e}")

        # --- Load history and spawn tasks for each symbol ---
        try:
            from engine.state_snapshot import StateSnapshot
            
            # Step 1: Find the latest snapshot for state restoration
            latest_snap_row = await db_pool.fetchrow("""
                SELECT * FROM aureus_signal_snapshots
                WHERE symbol = $1
                ORDER BY time DESC LIMIT 1
            """, symbol)
            
            # Step 2: Read Checkpoint Marker for Delta processing
            checkpoint_payload = await r.get(f"aureus:checkpoint:{symbol}")
            checkpoint_time = None
            if checkpoint_payload:
                try:
                    cp_data = json.loads(checkpoint_payload)
                    ts_unix = cp_data.get("last_processed_time")
                    if ts_unix:
                        checkpoint_time = datetime.fromtimestamp(ts_unix, tz=timezone.utc)
                except Exception as e:
                    logger.error(f"Failed to parse checkpoint for {symbol}: {e}")
            
            window_manager.reset(symbol)
            window_manager.set_backfill_status(symbol, "WARMING", reason="INIT_WARMUP_STARTED", updated_at=time.time())
            from engine.state import SymbolState
            state = window_manager.states.setdefault(symbol, SymbolState(symbol))

            if latest_snap_row:
                last_snapshot_time = latest_snap_row['time']
                
                # Determine delta start time (checkpoint takes precedence)
                effective_start_time = checkpoint_time if checkpoint_time and checkpoint_time > last_snapshot_time else last_snapshot_time
                
                logger.info(f"[{symbol}] Found recent snapshot at {last_snapshot_time}. Hydrating State...")
                if checkpoint_time:
                    logger.info(f"[{symbol}] Found Checkpoint Marker at {checkpoint_time}. Using for delta.")
                
                # Fetch warm-up for DataFrame context (indicators) using snapshot time
                warmup_rows = await db_pool.fetch("""
                    SELECT time, open, high, low, close, volume
                    FROM aureus_candles
                    WHERE symbol = $1 AND time <= $2
                    ORDER BY time DESC
                    LIMIT 1500
                """, symbol, last_snapshot_time)
                
                # Fetch delta (missing candles while service was offline or not snapshotted)
                new_rows = await db_pool.fetch("""
                    SELECT time, open, high, low, close, volume
                    FROM aureus_candles
                    WHERE symbol = $1 AND time > $2
                    ORDER BY time ASC
                """, symbol, effective_start_time)
                
                # 1. Feed warmup into window without state mutation ruining it
                for row in reversed(warmup_rows):
                    candle_data = {
                        't': str(int(row['time'].timestamp())), 'o': str(row['open']),
                        'h': str(row['high']), 'l': str(row['low']),
                        'c': str(row['close']), 'v': str(row['volume']), 'symbol': symbol
                    }
                    window_manager.update(symbol, candle_data)
                
                # 2. Hard Reset State and Hydrate from Snapshot securely
                state = window_manager.states[symbol]
                state.reset()
                snap = StateSnapshot.from_db_row(latest_snap_row)
                snap.restore_to_state(state)
                
                logger.info(f"[{symbol}] State Hydrated. Processing {len(new_rows)} delta candles...")
                
                # 3. Process new candles individually to catch up to real-time
                signals = symbol_signals[symbol]
                for row in new_rows:
                    candle_data = {
                        't': str(int(row['time'].timestamp())), 'o': str(row['open']),
                        'h': str(row['high']), 'l': str(row['low']),
                        'c': str(row['close']), 'v': str(row['volume']), 'symbol': symbol
                    }
                    df, _ = window_manager.update(symbol, candle_data)
                    state.transient_signals = {}
                    
                    if df is not None and len(df) >= 5:
                        for tag, signal_calc in signals.items():
                            try:
                                res = signal_calc.calculate(df, state, redis_client=r, symbol=symbol)
                                if res:
                                    tag_val = res.get('tag', tag)
                                    if tag_val: state.log_signal(tag_val, int(candle_data['t']))
                                    cross_val = res.get('cross')
                                    if cross_val: state.log_signal(cross_val, int(candle_data['t']))
                            except Exception as e:
                                pass
            else:
                logger.info(f"[{symbol}] No snapshot found. Performing full initial warm-up...")
                logger.debug(f"Starting initial DB fetch for {symbol}...")
                rows = await db_pool.fetch("""
                    SELECT time, open, high, low, close, volume
                    FROM aureus_candles
                    WHERE symbol = $1
                    ORDER BY time DESC
                    LIMIT 1500
                """, symbol)
                logger.debug(f"Found {len(rows)} warm-up rows from DB.")

                for row in reversed(rows):
                    candle_data = {
                        't': str(int(row['time'].timestamp())), 'o': str(row['open']),
                        'h': str(row['high']), 'l': str(row['low']),
                        'c': str(row['close']), 'v': str(row['volume']), 'symbol': symbol
                    }
                    window_manager.update(symbol, candle_data)
                
                df = window_manager.get_df(symbol)
                signals = symbol_signals[symbol]
                if df is not None:
                    for tag, signal_calc in signals.items():
                        try:
                            res = signal_calc.calculate(df, state, redis_client=r, symbol=symbol)
                            if res:
                                tag_val = res.get('tag', tag)
                                if tag_val: state.log_signal(tag_val, int(df.iloc[-1]['t']))
                        except Exception as e:
                            logger.error(f"Init signal calc error for {tag}: {e}")

            # Assign properly seeded state
            df = window_manager.get_df(symbol)
            state = window_manager.states[symbol]
            signals = symbol_signals[symbol]

            # Update Today's News Events cleanly
            if df is not None and len(df) > 0:
                last_t = int(df.iloc[-1]['t'])
                current_dt = datetime.fromtimestamp(last_t, tz=timezone(timedelta(hours=7)))
                state.news_events = NewsProvider.get_todays_events(current_dt)

            # Ensure tracking vars has proper DB pivot time
            if len(state.swing_points) >= 3:
                history_to_db = state.swing_points[:-2]
                for sp in history_to_db:
                    stream_key = f"aureus:stream:{symbol}:swing_point"
                    await r.xadd(stream_key, {
                        "t": str(sp['t']),
                        "price": str(sp['price']),
                        "is_high": "true" if sp['is_high'] else "false",
                        "type": sp['type']
                    })
                state.tracking_vars['last_db_pivot_time'] = history_to_db[-1]['t']

            # Evaluate strategies on initial seed to populate Active Monitoring immediately
            symbol_strategies[symbol].evaluate_all(df, signals, state)

            state_key = f"aureus:state:{symbol}"
            await r.set(state_key, json.dumps(state.to_dict()))
            
            logger.info(f"[{symbol}] [run_signal_engine] 9... Engine ready. Last candle: {state.last_candle.get('t') if state.last_candle else 'None'}")
            window_manager.set_backfill_status(symbol, "READY", reason="INIT_WARMUP_COMPLETED", updated_at=time.time())
        except Exception as e:
            window_manager.set_backfill_status(symbol, "NOT_READY", reason="INIT_WARMUP_FAILED", updated_at=time.time())
            logger.warning(f"[{symbol}] [run_signal_engine] Error: Could not load history for {symbol}: {e}")

        # --- Background Tasks ---
        # Restored DB-based integrity checking but optimized polling to reduce I/O
        asyncio.create_task(integrity_and_recalc_task(symbol, db_pool, r, window_manager, symbol_signals[symbol], symbol_strategies[symbol], symbol_locks[symbol]))




    # --- Strategy Reload Task ---
    async def listen_for_reload():
        pubsub = r.pubsub()
        await pubsub.subscribe("aureus:cmd:refresh_strategies")
        logger.info("[GLOBAL] [listen_for_reload] 1... Subscribed to global strategy refresh channel")
        async for message in pubsub.listen():
            if message['type'] == 'message':
                target_symbol = message['data']
                if target_symbol == "*" or target_symbol == "ALL" or target_symbol in symbols_list:
                    logger.info(f"[GLOBAL] [listen_for_reload] 2... Strategy refresh requested for {target_symbol}")
                    # Load for specific symbol or all
                    refresh_list = symbols_list if target_symbol in ("*", "ALL") else [target_symbol]
                    for s in refresh_list:
                        if s not in symbol_strategies:
                            symbol_strategies[s] = StrategyRegistry()
                        await symbol_strategies[s].load_from_db(db_pool, s)

    asyncio.create_task(listen_for_reload())
    
    # --- Global Command Stream Listener ---
    async def global_command_stream_listener():
        global_stream = "aureus:sys:config"
        global_group = "engine-global-group"
        global_consumer = f"consumer-{os.getenv('HOSTNAME', 'local')}"
        
        try: await r.xgroup_create(global_stream, global_group, id="0", mkstream=True)
        except Exception: pass
        
        logger.info(f"[GLOBAL] [global_command_stream_listener] 1... Subscribed to global command stream: {global_stream}")
        while True:
            try:
                messages = await r.xreadgroup(global_group, global_consumer, {global_stream: ">"}, count=10)
                if messages:
                    for _, msg_list in messages:
                        for entry_id, data in msg_list:
                            cmd_type = data.get('type')
                            if cmd_type == 'LLM_MODEL_CHANGED':
                                new_model = data.get('model')
                                if new_model:
                                    ai_validator.set_model(new_model)
                                    logger.info(f"[GLOBAL] [global_command_stream_listener] 2... LLM model updated to {new_model}")
                            await r.xack(global_stream, global_group, entry_id)
            except Exception as e:
                logger.error(f"[GLOBAL] [global_command_stream_listener] Error: {e}")
            await asyncio.sleep(5)

    asyncio.create_task(global_command_stream_listener())
    
    # --- News Refresh Task (Every 24h) ---
    async def news_refresh_loop():
        while True:
            await asyncio.sleep(86400) # 24 hours
            logger.info("[GLOBAL] [news_refresh_loop] 1... Refreshing weekly news calendar...")
            NewsProvider.fetch_this_week()
            
    asyncio.create_task(news_refresh_loop())
    
    streams_subscription = {f"aureus:stream:{s}:candle": ">" for s in symbols_list}
    candle_count = 0

    while True:
        try:
            logger.debug(f"Waiting for messages on {group_name}...")
            messages = await r.xreadgroup(
                group_name, consumer_name,
                streams_subscription,
                count=500, block=5000
            )
            if not messages:
                continue

            logger.debug(f"Read {sum(len(entries) for _, entries in messages)} stream messages")

            for stream_key, entries in messages:
                symbol = target_streams.get(stream_key)
                if not symbol: continue
                
                # 1. Batch insert candles into DB
                db_payload = []
                for entry_id, data in entries:
                    try:
                        if data.get('type') == 'TICK': continue
                        ts_ms = int(data.get('t', 0))
                        ts_unix = ts_ms // 1000 if ts_ms > 1e12 else ts_ms
                        ts_db = datetime.fromtimestamp(ts_unix, tz=timezone.utc)
                        db_payload.append((
                            ts_db, 
                            data.get('symbol', symbol),
                            float(data.get('o', 0)),
                            float(data.get('h', 0)),
                            float(data.get('l', 0)),
                            float(data.get('c', 0)),
                            int(float(data.get('v', data.get('vol', 0)))),
                            'M1'
                        ))
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Malformed message {entry_id}: {e}")
                
                if db_payload:
                    try:
                        await db_pool.executemany("""
                            INSERT INTO aureus_candles (time, symbol, open, high, low, close, volume, timeframe)
                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                            ON CONFLICT (time, symbol, timeframe) DO UPDATE
                            SET open=$3, high=$4, low=$5, close=$6, volume=$7
                        """, db_payload)
                    except Exception as e:
                        logger.error(f"[GLOBAL] [run_signal_engine] Error: Batch DB insert error: {e}")

                # 2. Process logic with per-symbol concurrency protection
                async with symbol_locks[symbol]:
                    signals = symbol_signals[symbol]
                    for entry_id, data in entries:
                        try:
                            msg_type = data.get('type')
                            if not msg_type:
                                if ':candle' in stream_key:
                                    msg_type = 'CANDLE'
                                elif ':tick' in stream_key:
                                    msg_type = 'TICK'

                            if msg_type == 'CANDLE':
                                eid_str = entry_id.decode('utf-8') if isinstance(entry_id, bytes) else str(entry_id)
                                logger.info(f"[t={data.get('t')}] [{symbol}] [run_signal_engine] 10... Read from Redis Stream {symbol} t={data.get('t')} entry_id={eid_str}")

                            if msg_type == 'COMMAND':
                                if data.get('cmd') == 'RECALCULATE':
                                    logger.info(f"[{symbol}] [run_signal_engine] 11... Received RECALCULATE for {symbol}.")
                                    window_manager.set_backfill_status(symbol, "NOT_READY", reason="RECALC_REQUESTED", updated_at=time.time())
                                    asyncio.create_task(recalculate_all_signals(symbol, db_pool, r, window_manager, signals, symbol_strategies[symbol], symbol_locks[symbol]))
                                await r.xack(stream_key, group_name, entry_id)
                                continue

                            if msg_type != 'CANDLE':
                                # TBD: Currently ignoring TICK (or any other non-candle) events to avoid redundant signal/snapshot processing.
                                # Future enhancement: Strategy SL/TP hits could be tracked here without full signal re-computation.
                                await r.xack(stream_key, group_name, entry_id)
                                continue
                            

                            ts_ms = int(data.get('t', 0))
                            ts_unix = ts_ms // 1000 if ts_ms > 1e12 else ts_ms
                            data['t'] = str(ts_unix)
                            candle_count += 1
                            
                            df, state = window_manager.update(symbol, data)
                            state.transient_signals = {} # Clear for new candle (Producer-Consumer pattern)
                            
                            # Update Today's News Events in State
                            current_dt = datetime.fromtimestamp(ts_unix, tz=timezone(timedelta(hours=7)))
                            state.news_events = NewsProvider.get_todays_events(current_dt)

                            execute_signals_for_candle(
                                signals=signals,
                                df=df,
                                state=state,
                                symbol=symbol,
                                redis_client=r,
                            )


                            strategy_results = symbol_strategies[symbol].evaluate_all(df, signals, state)
                            registry_rejections = symbol_strategies[symbol].get_rejections(clear=True)

                            normalized_snapshot = None
                            if strategy_results or registry_rejections:
                                normalized_snapshot = build_normalized_signal_snapshot(signals, state)

                            if strategy_results:
                                strategy_results = enrich_strategy_decisions_with_contract_metadata(
                                    strategy_results,
                                    normalized_snapshot,
                                )

                            if registry_rejections:
                                enriched_rejections = enrich_registry_rejections_with_contract_metadata(
                                    symbol=symbol,
                                    rejections=registry_rejections,
                                    normalized_snapshot=normalized_snapshot or {},
                                    default_t=ts_unix,
                                )
                                await emit_registry_rejections(r, symbol, enriched_rejections)

                            if execution_mode == "simulated":
                                await trade_manager.update_orders(symbol, data, state)
                            
                            if strategy_results:
                                pending_order = await trade_manager.process_triggers(
                                    symbol,
                                    strategy_results,
                                    state,
                                    ai_validator,
                                    execution_mode=execution_mode,
                                )
                                if pending_order:
                                    await queue_ai_audit_task(ai_queue, ai_validator, symbol, df, state, pending_order)
                                
                                for res in strategy_results:
                                    logger.info(f"[t={res['t']}] [{symbol}] STRATEGY TRIGGERED: {res['strategy']}")
                                    state.log_signal(f"strat:{res['strategy']}", res['t'])

                            await r.xack(stream_key, group_name, entry_id)

                            # --- EVENT EVALUATION ---
                            has_event = has_structural_event(state, trade_manager)

                            # --- CONDITIONAL REDIS SYNC ---
                            flags = FeatureFlags(r)
                            sync_mode = await flags.get("redis_sync_mode", "ALWAYS")
                            if sync_mode == "ALWAYS" or has_event or (candle_count % 5 == 0):
                                logger.info(f"[t={ts_unix}] [{symbol}] [run_signal_engine] 12... State Saved to Redis (reason: sync_mode={sync_mode}, event={has_event}, count={candle_count})")
                                await r.set(f"aureus:state:{symbol}", json.dumps(state.to_dict()))

                            # --- SPARSE STORAGE LOGIC ---
                            snapshot_mode = await flags.get("snapshot_mode", "FULL")
                            
                            if snapshot_mode == "FULL" or has_event:
                                # Write signal snapshot (async, fire-and-forget)
                                try:
                                    snapshot = build_snapshot(state, data)
                                    asyncio.create_task(insert_single_snapshot(db_pool, snapshot))
                                except Exception as e:
                                    logger.debug(f"[{symbol}] [run_signal_engine] Error: Snapshot write error: {e}")
                            
                            # Clean up trade events for the next tick
                            trade_manager.last_tick_events = []

                            # Write checkpoint marker (independent of snapshots)
                            try:
                                checkpoint_payload = json.dumps({
                                    "last_processed_time": int(ts_unix),
                                    "updated_at": int(time.time())
                                })
                                await r.set(f"aureus:checkpoint:{symbol}", checkpoint_payload)
                            except Exception as e:
                                logger.warning(f"[{symbol}] [run_signal_engine] Error: Checkpoint write error: {e}")

                            candle_count += 1
                            if candle_count % 20 == 0:
                                logger.info(f"[t={ts_unix}] [{symbol}] [run_signal_engine] 6... Processed {candle_count} units | Last: {symbol} @ {datetime.fromtimestamp(ts_unix).strftime('%H:%M')}")

                            # Trigger Event-Driven AI Pulse Analysis (Aggregated for this candle)
                            if state.ai_update_pending:
                                now_pulse = time.time()
                                is_fresh = ts_unix > (now_pulse - 300) # Only trigger AI if candle is < 5m old (Live context)
                                last_pulse = state.tracking_vars.get('last_pulse_t', 0)
                                
                                # Process only if FRESH and not in cooldown (60s)
                                if is_fresh and (now_pulse - last_pulse >= 60):
                                    event_list = ", ".join(state.ai_trigger_events)
                                    logger.info(f"[t={ts_unix}] [{symbol}] [run_signal_engine] 14... 🤖 Event-Driven AI Analysis triggered by: {event_list}")
                                    
                                    await queue_periodic_ai_analysis(
                                        ai_queue, ai_validator, symbol, df, state, now_pulse, trigger_events=state.ai_trigger_events
                                    )
                                    state.tracking_vars['last_pulse_t'] = now_pulse
                                
                                # Reset trigger and aggregation list for next candle regardless of pulse firing
                                state.ai_update_pending = False
                                state.ai_trigger_events = []

                        except Exception as e:
                            eid_str = entry_id.decode('utf-8') if isinstance(entry_id, bytes) else str(entry_id)
                            logger.error(f"[{symbol}] [run_signal_engine] Error: Error processing entry {eid_str}: {e}")
                            await r.xack(stream_key, group_name, entry_id)

        except Exception as e:
            logger.error(f"[GLOBAL] [run_signal_engine] Error: Engine loop error: {e}")
            await asyncio.sleep(1)

# --- AI Queue Logic ---

async def brain_worker(queue, r, db_pool, validator, manager):
    """Processes AI tasks from the priority queue."""
    while True:
        try:
            priority, _counter, task_type, payload = await queue.get()
            
            if task_type == 'PULSE':
                await execute_pulse(payload, r, db_pool, validator)
            elif task_type == 'AUDIT':
                await execute_audit(payload, r, db_pool, validator, manager)
                
            queue.task_done()
        except Exception as e:
            logger.error(f"[GLOBAL] [brain_worker] Error: Brain Worker Error: {e}")
            await asyncio.sleep(1)

async def queue_periodic_ai_analysis(queue, validator, symbol, df, state, start_time, trigger_events=None):
    """Generates context and queues a market pulse analysis."""
    try:
        context = validator.builder.build_pulse_context(symbol, df, state, trigger_events=trigger_events)
        global _queue_counter
        _queue_counter += 1
        await queue.put((PRIO_PULSE, _queue_counter, 'PULSE', {
            'symbol': symbol,
            'context': context,
            'start_time': start_time
        }))
    except Exception as e:
        logger.error(f"[{symbol}] [queue_periodic_ai_analysis] Error: Error queueing pulse for {symbol}: {e}")

async def queue_ai_audit_task(ai_queue, validator, symbol, df, state, order):
    """Queues an institutional audit task with necessary market data."""
    try:
        global _queue_counter
        _queue_counter += 1
        # Pass df and state references to the worker for fresh hybrid evaluation
        await ai_queue.put((PRIO_TRADE, _queue_counter, 'AUDIT', {
            'symbol': symbol,
            'df': df.copy() if df is not None else None, # Snapshot
            'state': state,
            'order': order,
            'start_time': time.time()
        }))
    except Exception as e:
        logger.error(f"[{symbol}] [queue_ai_audit_task] Error: Error queueing audit: {e}")

async def execute_pulse(payload, r, db_pool, validator):
    """Executes the LLM call and stores periodic narrative."""
    symbol = payload['symbol']
    context = payload['context']
    start_time = payload['start_time']
    
    try:
        # LLM Call
        start_llm = time.perf_counter()
        analysis = await validator.brain.generate_pulse(context)
        llm_latency = int((time.perf_counter() - start_llm) * 1000)
        
        # Meta
        analysis['symbol'] = symbol
        analysis['timestamp'] = int(datetime.now().timestamp())
        analysis['llm_latency_ms'] = llm_latency
        analysis['request_payload'] = context
        
        # Redis Snapshot
        await r.set(f"aureus:ai:latest:{symbol}", json.dumps(analysis))
        
        # DB Persistence
        ts_db = datetime.fromtimestamp(analysis['timestamp'], tz=timezone.utc)
        total_latency = int((time.time() - start_time) * 1000)

        await db_pool.execute("""
            INSERT INTO aureus_ai_analysis (
                time, symbol, aci, sentiment, narrative, debate_log,
                prompt_tokens, completion_tokens, llm_latency_ms, total_latency_ms, 
                request_payload, response_payload, analysis_type
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
        """, 
        ts_db, symbol, analysis['aci'], analysis['sentiment'], analysis['narrative'], json.dumps(analysis['debate_log']),
        analysis.get('prompt_tokens'), analysis.get('completion_tokens'), 
        llm_latency, total_latency, context, analysis.get('raw_response'), 'PULSE'
        )
        
        logger.info(f"[{symbol}] [execute_pulse] 1... AI Pulse Complete: {analysis['sentiment']} (ACI: {analysis['aci']}) | Latency: {llm_latency}ms / {total_latency}ms")
    except Exception as e:
        logger.error(f"[{symbol}] [execute_pulse] Error: {e}")

async def execute_audit(payload, r, db_pool, validator, manager):
    """Executes the Hybrid audit flow and processes trade decision."""
    symbol = payload['symbol']
    df = payload['df']
    state = payload['state']
    order = payload['order']
    start_time = payload['start_time']
    
    try:
        # Hybrid Call (Algo + AI)
        audit_result = await validator.validate_trigger(symbol, df, state, order)
        
        # Process Decision (manager handles orders)
        await manager.handle_ai_decision(order, audit_result)
        
        # Persistence
        ts_db = datetime.fromtimestamp(audit_result['timestamp'], tz=timezone.utc)
        total_latency = int((time.time() - start_time) * 1000)
        
        await db_pool.execute("""
            INSERT INTO aureus_ai_analysis (
                time, symbol, aci, debate_log, analysis_type, 
                decision, key_insight, trigger_id,
                prompt_tokens, completion_tokens, llm_latency_ms, total_latency_ms, 
                request_payload, response_payload,
                algo_score, algo_breakdown, audit_source
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)
        """, 
        ts_db, symbol, audit_result['aci'], json.dumps(audit_result['debate_log']), 'AUDIT',
        audit_result['decision'], audit_result['key_insight'], order.get('trace_id'),
        audit_result.get('prompt_tokens'), audit_result.get('completion_tokens'),
        audit_result.get('llm_latency_ms', 0), total_latency, 
        audit_result.get('request_payload', ''), audit_result.get('raw_response'),
        audit_result.get('algo_score'), json.dumps(audit_result.get('algo_breakdown', {})),
        audit_result.get('audit_source', 'HYBRID')
        )

        logger.info(f"[{symbol}] [execute_audit] 1... Hybrid Audit Complete: Decision={audit_result.get('decision')} (Algo: {audit_result.get('algo_score')})")
    except Exception as e:
        logger.error(f"[{symbol}] [execute_audit] Error: {e}")
        import traceback
        logger.error(traceback.format_exc())


async def recalculate_all_signals(symbol, db_pool, r, window_manager, signals, strategy_registry, lock):
    """
    Refreshes memory state and recalculates signals INCREMENTALLY.
    Processes only new candles after the last snapshot.

    Uses 200-bar warm-up for EMA convergence. ON CONFLICT ensures idempotency.
    Publishes progress to Redis for UI tracking.
    """
    from engine.state_snapshot import StateSnapshot

    async with lock:
        try:
            window_manager.set_backfill_status(symbol, "WARMING", reason="RECALC_RUNNING", updated_at=time.time())

            # Step 2: Check last existing snapshot (INCREMENTAL)
            last_snapshot_time = await db_pool.fetchval("""
                SELECT MAX(time) FROM aureus_signal_snapshots WHERE symbol = $1
            """, symbol)

            # Step 2.5: Read Checkpoint Marker for Delta processing
            checkpoint_payload = await r.get(f"aureus:checkpoint:{symbol}")
            checkpoint_time = None
            if checkpoint_payload:
                try:
                    cp_data = json.loads(checkpoint_payload)
                    ts_unix = cp_data.get("last_processed_time")
                    if ts_unix:
                        checkpoint_time = datetime.fromtimestamp(ts_unix, tz=timezone.utc)
                except Exception as e:
                    logger.error(f"[{symbol}] [recalculate_all_signals] Error: Failed to parse checkpoint: {e}")

            if last_snapshot_time:
                # Determine delta start time (checkpoint takes precedence)
                effective_start_time = checkpoint_time if checkpoint_time and checkpoint_time > last_snapshot_time else last_snapshot_time
                if checkpoint_time:
                    logger.info(f"[{symbol}] [recalculate_all_signals] 2... Using Checkpoint Marker {checkpoint_time} for recalculation delta.")

                # Incremental: Load candles after last snapshot (+ 1500 bar warm-up)
                warmup_rows = await db_pool.fetch("""
                    SELECT time, open, high, low, close, volume
                    FROM aureus_candles
                    WHERE symbol = $1 AND time <= $2
                    ORDER BY time DESC
                    LIMIT 1500
                """, symbol, last_snapshot_time)

                new_rows = await db_pool.fetch("""
                    SELECT time, open, high, low, close, volume
                    FROM aureus_candles
                    WHERE symbol = $1 AND time > $2
                    ORDER BY time ASC
                """, symbol, effective_start_time)

                if not new_rows:
                    logger.info(f"[{symbol}] [recalculate_all_signals] 3... No new candles since last snapshot. Skipping.")
                    await r.set(f"aureus:precompute:status:{symbol}", json.dumps({
                        "symbol": symbol, "status": "COMPLETED", "progress": 100,
                        "processed": 0, "total": 0, "message": "Already up to date"
                    }))
                    window_manager.set_backfill_status(symbol, "READY", reason="RECALC_UP_TO_DATE", updated_at=time.time())
                    return

                # Combine: warm-up (oldest first) + new candles
                warmup_list = list(reversed(warmup_rows))
                all_rows = warmup_list + list(new_rows)
                warmup_count = len(warmup_list)
                total_new = len(new_rows)

                logger.info(f"[{symbol}] [recalculate_all_signals] 4... Incremental — {warmup_count} warm-up + {total_new} new candles")
            else:
                # No snapshot at all (shouldn't really happen if init logic worked)
                logger.warning(f"[{symbol}] [recalculate_all_signals] Error: No history found in DB")
                window_manager.set_backfill_status(symbol, "NOT_READY", reason="RECALC_NO_SNAPSHOT", updated_at=time.time())
                return

            window_manager.reset(symbol)
            snapshot_batch = []
            event_count = 0
            processed_new = 0

            # Publish initial progress
            await r.set(f"aureus:precompute:status:{symbol}", json.dumps({
                "symbol": symbol, "status": "RUNNING", "progress": 0,
                "processed": 0, "total": total_new
            }))

            # Process each candle individually (oldest first)
            for i, row in enumerate(all_rows):
                candle_data = {
                    't': str(int(row['time'].timestamp())),
                    'o': str(row['open']), 'h': str(row['high']),
                    'l': str(row['low']), 'c': str(row['close']),
                    'v': str(row['volume']), 'symbol': symbol,
                }

                df, state = window_manager.update(symbol, candle_data)
                state.transient_signals = {}  # Clear for each candle

                # Yield control every 100 candles
                if i % 100 == 0:
                    await asyncio.sleep(0)

                # Run all signals per candle
                if df is not None and len(df) >= 5:
                    for tag, signal_calc in signals.items():
                        try:
                            res = signal_calc.calculate(df, state, redis_client=r, symbol=symbol)
                            if res:
                                sig_tag = res.get('tag', tag)
                                if sig_tag:
                                    state.log_signal(sig_tag, int(candle_data['t']))
                                cross_tag = res.get('cross')
                                if cross_tag:
                                    state.log_signal(cross_tag, int(candle_data['t']))
                        except Exception as e:
                            if i < 3:
                                logger.error(f"[{symbol}] [recalculate_all_signals] Error: Signal {tag} calc error: {e}")

                    # Only save snapshots for NEW candles (skip warm-up)
                    if i >= warmup_count:
                        snapshot = StateSnapshot.from_state(state, candle_data)
                        snapshot_batch.append(snapshot.to_db_row())
                        if snapshot.events:
                            event_count += 1
                        processed_new += 1

                    # Batch insert every 500
                    if len(snapshot_batch) >= 500:
                        await batch_insert_snapshots(db_pool, snapshot_batch)
                        snapshot_batch = []
                        # Update progress
                        progress = int((processed_new / total_new) * 100) if total_new > 0 else 100
                        await r.set(f"aureus:precompute:status:{symbol}", json.dumps({
                            "symbol": symbol, "status": "RUNNING", "progress": progress,
                            "processed": processed_new, "total": total_new
                        }))

            # Final batch
            if snapshot_batch:
                await batch_insert_snapshots(db_pool, snapshot_batch)

            # Evaluate strategies on final state
            df = window_manager.get_df(symbol)
            state = window_manager.states[symbol]
            if df is not None:
                strategy_registry.evaluate_all(df, signals, state)

                # Update Redis state
                state_key = f"aureus:state:{symbol}"
                await r.set(state_key, json.dumps(state.to_dict()))

                # --- Update Checkpoint ---
                if all_rows:
                    last_candle_time = int(all_rows[-1]['time'].timestamp())
                    try:
                        checkpoint_payload = json.dumps({
                            "last_processed_time": last_candle_time,
                            "updated_at": int(time.time())
                        })
                        await r.set(f"aureus:checkpoint:{symbol}", checkpoint_payload)
                    except Exception as e:
                        logger.warning(f"[{symbol}] [recalculate_all_signals] Error: Checkpoint update error: {e}")

            # Publish completion status
            await r.set(f"aureus:precompute:status:{symbol}", json.dumps({
                "symbol": symbol, "status": "COMPLETED", "progress": 100,
                "processed": processed_new, "total": total_new
            }))
            window_manager.set_backfill_status(symbol, "READY", reason="RECALC_COMPLETED", updated_at=time.time())
        except Exception:
            window_manager.set_backfill_status(symbol, "NOT_READY", reason="RECALC_FAILED", updated_at=time.time())
            raise


async def integrity_and_recalc_task(symbol, db_pool, r, window_manager, signals, strategy_registry, lock):
    """
    Background worker that monitors data gaps and triggers a full state
    recalculation once historical data is complete and continuous.
    
    Optimized: Reduced polling frequency and lookback window to minimize DB I/O.
    """
    detector = GapDetector(db_pool)
    recalc_triggered = False
    
    await asyncio.sleep(60) # Initial wait
    
    while True:
        try:
            # CHECK GAPS (Limit to last 1 hour to save DB IO, down from 2h)
            gaps = await detector.find_gaps(symbol, lookback_hours=1)

            if gaps:
                logger.info(f"[{symbol}] [integrity_and_recalc_task] 1... Found {len(gaps)} gaps. Requesting recovery...")
                window_manager.set_backfill_status(symbol, "NOT_READY", reason="GAP_DETECTED", updated_at=time.time())
                for gap in gaps:
                    cmd = {"type": "REQUEST_BACKFILL", "symbol": symbol, "start": gap["start"], "end": gap["end"]}
                    await r.publish("aureus:mt5:commands", json.dumps(cmd))
                recalc_triggered = False # Reset flag if new gaps appear
            else:
                # No gaps! Trigger full recalculation once
                if not recalc_triggered:
                    logger.info(f"[{symbol}] [integrity_and_recalc_task] 2... Gaps cleared. Preparing recalculation...")
                    await recalculate_all_signals(symbol, db_pool, r, window_manager, signals, strategy_registry, lock)
                    recalc_triggered = True
            
            # SLOW POLL: Check every 3 minutes instead of 60 seconds to reduce DB load
            await asyncio.sleep(180)
            
        except Exception as e:
            logger.error(f"[{symbol}] [integrity_and_recalc_task] Error: {e}")
            await asyncio.sleep(60)
