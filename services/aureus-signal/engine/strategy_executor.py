"""
Aureus Strategy Executor — Decoupled async consumer for strategy evaluation

Pipeline:  Signal Aggregator → Redis Stream (aureus:stream:{symbol}:signals) → [THIS] → Orders/AI Queue

Consumes signal payloads emitted by the Signal Aggregator and runs strategy evaluation,
trade simulation, and AI trigger logic independently.
"""
import asyncio
import os
import json
import time
import redis.asyncio as redis
from datetime import datetime, timezone
from typing import Optional, Any

from engine.logging_common import get_logger
from engine.signal_factory import build_normalized_signal_snapshot
from engine.strategies.registry import StrategyRegistry
from engine.strategies.seed_strategies import seed_system_strategies
from engine.orders import SimulatedTradeManager
from engine.ai_validator import AIValidator
from engine.feature_flags import FeatureFlags

logger = get_logger(__name__)
PIPELINE_LOG_PREFIX = "[PIPELINE]"

SPEC_VERSION = "2026-03-20-live-trading-v1"
ENGINE_VERSION = os.getenv("AUREUS_SIGNAL_ENGINE_VERSION", "live-engine-v1")

PRIO_TRADE = 1
PRIO_PULSE = 2
_queue_counter = 0


# --- Contract Metadata Enrichment (moved from live_engine) ---

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


# --- AI Queue Logic (shared with aggregator brain_worker) ---

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
            logger.error(f"[GLOBAL] [brain_worker] Error: {e}")
            await asyncio.sleep(1)


async def execute_pulse(payload, r, db_pool, validator):
    """Executes the LLM call and stores periodic narrative."""
    symbol = payload['symbol']
    context = payload['context']
    start_time = payload['start_time']

    try:
        start_llm = time.perf_counter()
        analysis = await validator.brain.generate_pulse(context)
        llm_latency = int((time.perf_counter() - start_llm) * 1000)

        analysis['symbol'] = symbol
        analysis['timestamp'] = int(datetime.now().timestamp())
        analysis['llm_latency_ms'] = llm_latency
        analysis['request_payload'] = context

        await r.set(f"aureus:ai:latest:{symbol}", json.dumps(analysis))

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

        logger.info(f"[{symbol}] [execute_pulse] AI Pulse Complete: {analysis['sentiment']} (ACI: {analysis['aci']}) | Latency: {llm_latency}ms / {total_latency}ms")
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
        audit_result = await validator.validate_trigger(symbol, df, state, order)
        await manager.handle_ai_decision(order, audit_result)

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

        logger.info(f"[{symbol}] [execute_audit] Hybrid Audit Complete: Decision={audit_result.get('decision')} (Algo: {audit_result.get('algo_score')})")
    except Exception as e:
        logger.error(f"[{symbol}] [execute_audit] Error: {e}")
        import traceback
        logger.error(traceback.format_exc())


async def queue_ai_audit_task(ai_queue, validator, symbol, df, state, order):
    """Queues an institutional audit task with necessary market data."""
    try:
        global _queue_counter
        _queue_counter += 1
        await ai_queue.put((PRIO_TRADE, _queue_counter, 'AUDIT', {
            'symbol': symbol,
            'df': df.copy() if df is not None else None,
            'state': state,
            'order': order,
            'start_time': time.time()
        }))
    except Exception as e:
        logger.error(f"[{symbol}] [queue_ai_audit_task] Error: {e}")


# --- Main Executor Loop ---

async def run_strategy_executor(db_pool=None, redis_client=None):
    """
    Asynchronous Strategy Executor worker.
    Consumes aureus:stream:{symbol}:signals and evaluates strategies.
    """
    from dotenv import load_dotenv
    import asyncpg

    load_dotenv()

    redis_host = os.getenv("REDIS_HOST", "redis")
    redis_port = int(os.getenv("REDIS_PORT", 6379))
    db_dsn = os.getenv("DATABASE_URL", "postgresql://aureus:aureus_password@localhost:5432/aureus")

    symbols_env = os.getenv("SYMBOLS", "XAUUSD")
    symbols_list = [s.strip() for s in symbols_env.split(",") if s.strip()]
    execution_mode = os.getenv("EXECUTION_MODE", "simulated").strip().lower()
    if execution_mode not in {"simulated", "nautilus"}:
        execution_mode = "simulated"

    logger.info(f"[EXECUTOR] Initializing Strategy Executor for: {symbols_list} | execution_mode={execution_mode}")

    # --- Connect Redis ---
    if redis_client:
        r = redis_client
    else:
        r = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)

    # --- Connect TimescaleDB ---
    if db_pool:
        pass
    else:
        db_pool = await asyncpg.create_pool(db_dsn, min_size=5, max_size=20)

    # --- Seed System Strategies ---
    await seed_system_strategies(db_pool)

    # --- Shared Components ---
    trade_manager = SimulatedTradeManager(r)
    ai_validator = AIValidator()

    active_model = await r.get("aureus:config:llm_model")
    if active_model:
        ai_validator.set_model(active_model)

    ai_queue = asyncio.PriorityQueue()

    # Spawn Brain Workers
    for i in range(2):
        asyncio.create_task(brain_worker(ai_queue, r, db_pool, ai_validator, trade_manager))
    logger.info("[EXECUTOR] Brain Worker pool initialized (Size: 2)")

    # --- Per-Symbol Strategy Registry ---
    symbol_strategies = {}
    for symbol in symbols_list:
        symbol_strategies[symbol] = StrategyRegistry()
        await symbol_strategies[symbol].load_from_db(db_pool, symbol)

    # --- Consumer Group Setup for signal streams ---
    group_name = "aureus-strategy-executor-group"
    consumer_name = f"executor-{os.getenv('HOSTNAME', 'local')}"

    for symbol in symbols_list:
        signal_stream = f"aureus:stream:{symbol}:signals"
        try:
            await r.xgroup_create(signal_stream, group_name, id="0", mkstream=True)
            logger.info(f"[EXECUTOR][{symbol}] Created consumer group on {signal_stream}")
        except Exception as e:
            if "already exists" not in str(e):
                logger.error(f"[EXECUTOR][{symbol}] Group creation error: {e}")

    # --- Strategy Reload Listener ---
    async def listen_for_reload():
        pubsub = r.pubsub()
        await pubsub.subscribe("aureus:cmd:refresh_strategies")
        logger.info("[EXECUTOR] Subscribed to strategy refresh channel")
        async for message in pubsub.listen():
            if message['type'] == 'message':
                target_symbol = message['data']
                if target_symbol == "*" or target_symbol == "ALL" or target_symbol in symbols_list:
                    refresh_list = symbols_list if target_symbol in ("*", "ALL") else [target_symbol]
                    for s in refresh_list:
                        if s not in symbol_strategies:
                            symbol_strategies[s] = StrategyRegistry()
                        await symbol_strategies[s].load_from_db(db_pool, s)
                    logger.info(f"[EXECUTOR] Strategies reloaded for {refresh_list}")

    asyncio.create_task(listen_for_reload())

    # --- Main Consumer Loop ---
    streams_subscription = {f"aureus:stream:{s}:signals": ">" for s in symbols_list}

    logger.info(f"[EXECUTOR] Entering main loop. Listening on: {list(streams_subscription.keys())}")

    while True:
        try:
            messages = await r.xreadgroup(
                group_name, consumer_name,
                streams_subscription,
                count=100, block=5000
            )
            if not messages:
                continue

            for stream_key, entries in messages:
                # Extract symbol from stream key: aureus:stream:{symbol}:signals
                parts = stream_key.split(":")
                symbol = parts[2] if len(parts) >= 4 else None
                if not symbol or symbol not in symbol_strategies:
                    continue

                for entry_id, data in entries:
                    try:
                        payload_raw = data.get("payload")
                        if not payload_raw:
                            await r.xack(stream_key, group_name, entry_id)
                            continue

                        payload = json.loads(payload_raw)
                        ts_unix = payload.get("t", 0)
                        log_signal_normalize = payload.get("log_signal_normalize", [])
                        signals_snapshot = payload.get("signals_snapshot", {})

                        # Reconstruct minimal state-like object for evaluate_all
                        from engine.state import SymbolState
                        executor_state = SymbolState(symbol)
                        executor_state.log_signal_normalize = log_signal_normalize
                        # Restore transient signals if provided
                        executor_state.transient_signals = payload.get("transient_signals", {})
                        # Restore current_signal
                        executor_state.current_signal = payload.get("current_signal", {})
                        # Restore swing_points for context
                        executor_state.swing_points = payload.get("swing_points", [])

                        # evaluate_all expects df — we pass None since executor doesn't build candles
                        # StrategyRegistry.evaluate_all uses df only for bar_ts extraction
                        # We provide a minimal proxy
                        import pandas as pd
                        mini_df = pd.DataFrame([{"t": ts_unix, "c": payload.get("close", 0)}])

                        strategy_results = symbol_strategies[symbol].evaluate_all(
                            mini_df, signals_snapshot, executor_state
                        )
                        registry_rejections = symbol_strategies[symbol].get_rejections(clear=True)

                        accepted_count = len(strategy_results) if strategy_results else 0
                        rejection_count = len(registry_rejections) if registry_rejections else 0
                        logger.info(
                            f"{PIPELINE_LOG_PREFIX}{symbol}[EXECUTOR][post_evaluate_all] "
                            f"t={ts_unix} accepted={accepted_count} rejections={rejection_count}"
                        )

                        normalized_snapshot = None
                        if strategy_results or registry_rejections:
                            normalized_snapshot = signals_snapshot  # Already normalized by aggregator

                        if strategy_results:
                            strategy_results = enrich_strategy_decisions_with_contract_metadata(
                                strategy_results,
                                normalized_snapshot or {},
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
                            candle_data = {
                                "t": str(ts_unix),
                                "o": str(payload.get("open", 0)),
                                "h": str(payload.get("high", 0)),
                                "l": str(payload.get("low", 0)),
                                "c": str(payload.get("close", 0)),
                                "v": str(payload.get("volume", 0)),
                            }
                            await trade_manager.update_orders(symbol, candle_data, executor_state)

                        if strategy_results:
                            pending_order = await trade_manager.process_triggers(
                                symbol,
                                strategy_results,
                                executor_state,
                                ai_validator,
                                execution_mode=execution_mode,
                            )
                            if pending_order:
                                await queue_ai_audit_task(ai_queue, ai_validator, symbol, mini_df, executor_state, pending_order)

                            for res in strategy_results:
                                logger.info(f"[t={res['t']}] [{symbol}] STRATEGY TRIGGERED: {res['strategy']}")

                        await r.xack(stream_key, group_name, entry_id)

                    except Exception as e:
                        eid_str = entry_id.decode('utf-8') if isinstance(entry_id, bytes) else str(entry_id)
                        logger.error(f"[EXECUTOR][{symbol}] Error processing entry {eid_str}: {e}")
                        await r.xack(stream_key, group_name, entry_id)

        except Exception as e:
            if "NOGROUP" in str(e):
                logger.warning(f"[EXECUTOR] NOGROUP detected. Recreating consumer groups...")
                for symbol in symbols_list:
                    signal_stream = f"aureus:stream:{symbol}:signals"
                    try:
                        await r.xgroup_create(signal_stream, group_name, id="0", mkstream=True)
                    except Exception:
                        pass
                await asyncio.sleep(1)
                continue
            logger.error(f"[EXECUTOR] Loop error: {e}")
            await asyncio.sleep(1)
