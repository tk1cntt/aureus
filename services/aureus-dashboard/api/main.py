from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import logging

logger = logging.getLogger("aureus-dashboard-api")
import redis as redis_sync
import redis.asyncio as redis_async
import os
import json
import asyncpg
import httpx
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime, timezone
import os
import math
import numpy as np
import time

# Configure logging
log_level = os.getenv("LOG_LEVEL", "INFO")
log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
log_file = os.getenv("LOG_FILE")

handlers = [logging.StreamHandler()]
if log_file:
    log_file = log_file.strip()
    if log_file:
        log_dir = os.path.dirname(log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        handlers.append(logging.FileHandler(log_file))

logging.basicConfig(
    level=log_level,
    format=log_format,
    handlers=handlers,
    force=True,
)
logger = logging.getLogger("aureus-dashboard-api.main")

app = FastAPI(title="Aureus Visualization API")

# Configure CORS — read allowed origins from env (comma-separated)
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:17222").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
POSTGRES_URL = os.getenv("DATABASE_URL", "postgresql://aureus:aureus_password@localhost:5432/aureus")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:8000/v1") # Use http://host.docker.internal:8000/v1 if in Docker

POSTGRES_URL = os.getenv("DATABASE_URL", "postgresql://aureus:aureus_password@localhost:5432/aureus")
DATABASE_URL = os.getenv("DATABASE_URL", POSTGRES_URL)
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:8000/v1") # Use http://host.docker.internal:8000/v1 if in Docker

# Sync Redis (backward compat for existing endpoints)
r = redis_sync.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

# Async Redis client for new performance endpoints (caching)
redis_client = redis_async.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)


@app.on_event("startup")
async def startup():
    # Connection pool for PostgreSQL
    app.state.pg_pool = await asyncpg.create_pool(
        DATABASE_URL,
        min_size=2,
        max_size=10,
    )
    logger.info("[GLOBAL] [startup] PostgreSQL connection pool created (min=2, max=10)")


@app.on_event("shutdown")
async def shutdown():
    if hasattr(app.state, 'pg_pool'):
        await app.state.pg_pool.close()
        logger.info("[GLOBAL] [shutdown] PostgreSQL connection pool closed")



# --- Pydantic Models ---
class StrategyStep(BaseModel):
    tag: str
    weight: float
    required: bool = False

class StrategyConfig(BaseModel):
    sequence: List[StrategyStep]

class StrategyCreate(BaseModel):
    name: str
    description: Optional[str] = ""
    config: StrategyConfig
    min_score: float = 10.0
    symbols: Optional[List[str]] = []

class BacktestRequest(BaseModel):
    symbol: str
    start: str # ISO Date
    end: str   # ISO Date
    strategy_ids: Optional[List[int]] = None


# Performance API Models
class TradeResponse(BaseModel):
    id: int
    trace_id: str
    ticket: Optional[int] = None
    symbol: str
    strategy_name: Optional[str] = None
    direction: str
    entry_price: Optional[float] = None
    exit_price: Optional[float] = None
    sl: Optional[float] = None
    tp: Optional[float] = None
    volume: Optional[float] = None
    profit: float
    commission: float
    swap: float
    filled_at: Optional[str] = None
    closed_at: Optional[str] = None

class MetaResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    filters: dict

def load_symbols():
    """Loads symbol metadata from symbols.json."""
    # Look in the signal engine directory relative to this file
    path = os.path.join(os.path.dirname(__file__), "..", "..", "aureus-signal", "symbols.json")
    if not os.path.exists(path):
        # Fallback for Docker or other environments
        path = os.getenv("SYMBOLS_CONFIG_PATH", "symbols.json")
    
    try:
        if os.path.exists(path):
            with open(path, "r") as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"[GLOBAL] [load_symbols] Error: Failed to load symbols config: {e}")
    return {}

@app.get("/api/v1/symbols")
async def get_symbols():
    """Returns a list of symbols with their metadata (like digits).
    
    Primary source: symbols.json config file (always returns all symbols).
    Secondary: Redis state keys (for online/offline status enrichment).
    """
    configs = load_symbols()
    
    # Collect symbols that have active Redis state (for status enrichment)
    redis_symbols = set()
    try:
        for pattern in ["aureus:state:*", "aureus:latest:*:candle"]:
            cursor = 0
            while True:
                cursor, keys = await r.scan(cursor, match=pattern, count=100)
                for k in keys:
                    parts = k.split(":")
                    if pattern.startswith("aureus:state"):
                        redis_symbols.add(parts[-1])
                    else:
                        redis_symbols.add(parts[2])
                if cursor == 0: break
    except Exception as e:
        logger.warning(f"[GLOBAL] [get_symbols] Error: Redis scan for symbols failed (non-critical): {e}")
    
    # Build result from config file (primary source — always has all symbols)
    result = []
    if configs:
        for name, cfg in configs.items():
            result.append({
                "name": name,
                "digits": cfg.get("digits", 2),
                "description": cfg.get("description", ""),
                "online": name in redis_symbols
            })
    else:
        # Fallback: if config file not found, use Redis symbols
        for s in sorted(list(redis_symbols)):
            result.append({
                "name": s,
                "digits": 2,
                "description": "",
                "online": True
            })
    
    return sorted(result, key=lambda x: x["name"])

@app.get("/api/v1/state/{symbol}")
async def get_symbol_state(symbol: str):
    """Returns the latest SMA state (swing points, OBs) for a symbol."""
    data = await r.get(f"aureus:state:{symbol}")
    if not data:
        # Return a default empty state for symbols without Signal Engine processing yet
        return {
            "symbol": symbol,
            "obs": [],
            "fvgs": [],
            "swing_points": [],
            "signal_history": [],
            "active_orders": [],
            "closed_orders": [],
            "strategy_progress": {}
        }
    
    parsed = json.loads(data)
    last_sp_t = parsed.get('swing_points', [])[-1].get('t') if parsed.get('swing_points') else None
    logger.info(f"[{symbol}] [get_symbol_state] 1... Dashboard API retrieved {symbol} state, swing_points_count={len(parsed.get('swing_points', []))} last_sp_t={last_sp_t}")
    return parsed

@app.get("/api/v1/chart/{symbol}")
async def get_chart_data(symbol: str, limit: int = 1440, run_id: Optional[int] = None):
    """Fetches historical candles and swing points from TimescaleDB, merged with real-time Redis points.
    Supports Backtest isolation via run_id.
    """
    conn = await asyncpg.connect(POSTGRES_URL)
    try:
        # 1. Fetch Candles (Always from aureus_candles)
        query_candles = """
            SELECT time, open, high, low, close, volume 
            FROM aureus_candles 
            WHERE symbol = $1 AND timeframe = 'M1'
            ORDER BY time DESC 
            LIMIT $2
        """
        candle_rows = await conn.fetch(query_candles, symbol, limit)
        candles = []
        for row in reversed(candle_rows):
            candles.append({
                "time": int(row['time'].timestamp()),
                "open": row['open'],
                "high": row['high'],
                "low": row['low'],
                "close": row['close'],
                "value": row['volume']
            })
            
        first_candle_time = candles[0]['time'] if candles else 0

        swing_points = []
        signal_events = []
        trades = []
        equity_curve = []
        state_data = None
        
        if run_id:
            # --- BACKTEST MODE ---
            # 2. Fetch Backtest Snapshots (Pivots, Trends, OBs, Events)
            query_bt = """
                SELECT time, swing_points, obs, htf_trend, market_regime, session, events
                FROM aureus_backtest_snapshots
                WHERE run_id = $1 AND symbol = $2 AND time >= to_timestamp($3)
                ORDER BY time ASC
            """
            bt_rows = await conn.fetch(query_bt, run_id, symbol, first_candle_time)
            
            if bt_rows:
                # Latest row for OBs/Trend/Metadata
                latest_row = bt_rows[-1]
                
                # Update high-level state from latest snapshot
                if latest_row['swing_points']:
                    swing_points = json.loads(latest_row['swing_points']) if isinstance(latest_row['swing_points'], str) else latest_row['swing_points']
                
                if latest_row['obs']:
                    obs = json.loads(latest_row['obs']) if isinstance(latest_row['obs'], str) else latest_row['obs']
                
                htf_trend = latest_row['htf_trend']
                market_regime = latest_row['market_regime']
                current_session = latest_row['session']
                
                # Aggregate events from ALL snapshots in range
                for r_bt in bt_rows:
                    if r_bt['events']:
                        evs = json.loads(r_bt['events']) if isinstance(r_bt['events'], str) else r_bt['events']
                        for ev in evs:
                            signal_events.append({"time": int(r_bt['time'].timestamp()), **ev})

            # 4. Fetch trade history from runs table
            run_row = await conn.fetchrow("SELECT trades, equity_curve, stats FROM aureus_backtest_runs WHERE run_id = $1", run_id)
            
            if run_row:
                trades = json.loads(run_row['trades']) if run_row['trades'] else []
                equity_curve = json.loads(run_row['equity_curve']) if run_row['equity_curve'] else []
                strategy_progress = json.loads(run_row['stats']) if run_row['stats'] else {}
            
        else:
            # --- LIVE MODE ---
            # 2. Fetch Historical Swing Points (Stable)
            query_sp = """
                SELECT time, price, is_high, type
                FROM aureus_swing_points
                WHERE symbol = $1 AND time >= to_timestamp($2)
                ORDER BY time ASC
            """
            sp_rows = await conn.fetch(query_sp, symbol, first_candle_time)
            for row in sp_rows:
                swing_points.append({
                    "t": int(row['time'].timestamp()),
                    "price": row['price'],
                    "is_high": row['is_high'],
                    "type": row['type']
                })

            # 3. Pull from live Redis
            state_data = await r.get(f"aureus:state:{symbol}")

        # 4. Stitch Real-time/Volatile Data
        state = {}
        if state_data:
            state = json.loads(state_data)
            
            # A. Stitch newest candle if missing from DB
            last_c = state.get('last_candle')
            if last_c:
                c_time = int(last_c['t'])
                if not candles or c_time > candles[-1]['time']:
                    candles.append({
                        "time": c_time,
                        "open": float(last_c['o']),
                        "high": float(last_c['h']),
                        "low": float(last_c['l']),
                        "close": float(last_c['c']),
                        "value": float(last_c['v'])
                    })

            # B. Merge Swing Points (for Live mode, backtest already has full list in snapshot)
            if not run_id:
                redis_sp = state.get('swing_points', [])
                redis_sp_dict = {sp['t']: sp for sp in redis_sp}
                for i in range(len(swing_points)):
                    db_t = swing_points[i]['t']
                    if db_t in redis_sp_dict:
                        sp_mem = redis_sp_dict[db_t]
                        for key in ['is_choch', 'choch_type', 'is_bos', 'bos_type', 'breakout_t', 'broken']:
                            if key in sp_mem: swing_points[i][key] = sp_mem[key]

                last_db_time = swing_points[-1]['t'] if swing_points else 0
                for sp in redis_sp:
                    if sp['t'] > last_db_time: swing_points.append(sp)

        # Get symbol metadata
        configs = load_symbols()
        symbol_cfg = configs.get(symbol, configs.get("XAUUSD", {"digits": 2}))
        digits = symbol_cfg.get("digits", 2)

        return {
            "symbol": symbol,
            "digits": digits,
            "candles": candles,
            "swing_points": swing_points,
            "obs": state.get('obs', []),
            "htf_trend": state.get('htf_trend'),
            "market_regime": state.get('market_regime'),
            "signal_events": signal_events if run_id else list(state.get('transient_signals', {}).values()),
            "trades": trades if run_id else state.get('trades', []),
            "equity_curve": equity_curve if run_id else state.get('equity_curve', []),
            "active_orders": state.get('active_orders', []),
            "closed_orders": state.get('closed_orders', []),
            "strategy_progress": state.get('strategy_progress', {}),
            "candle_actors": state.get('candle_actors', {})
        }
    finally:
        await conn.close()

@app.get("/api/v1/strategies")
async def list_strategies():
    """List all strategy templates."""
    conn = await asyncpg.connect(POSTGRES_URL)
    try:
        query = """
            SELECT t.id, t.name, t.description, t.config, t.min_score, t.created_at,
                   array_agg(ss.symbol) FILTER (WHERE ss.symbol IS NOT NULL) as assigned_symbols
            FROM aureus_strategy_templates t
            LEFT JOIN aureus_symbol_strategies ss ON t.id = ss.strategy_id
            GROUP BY t.id
            ORDER BY t.id ASC
        """
        rows = await conn.fetch(query)
        logger.info("[GLOBAL] [list_strategies] 1... Listing all strategy templates")
        return [dict(r) for r in rows]
    finally:
        await conn.close()

@app.post("/api/v1/strategies")
async def create_strategy(strategy: StrategyCreate):
    """Create a new strategy template."""
    conn = await asyncpg.connect(POSTGRES_URL)
    try:
        async with conn.transaction():
            query = """
                INSERT INTO aureus_strategy_templates (name, description, config, min_score)
                VALUES ($1, $2, $3, $4)
                RETURNING id
            """
            strat_id = await conn.fetchval(query, strategy.name, strategy.description, strategy.config.json(), strategy.min_score)
            
            if strategy.symbols:
                for sym in strategy.symbols:
                    await conn.execute(
                        "INSERT INTO aureus_symbol_strategies (symbol, strategy_id, is_active) VALUES ($1, $2, true)",
                        sym, strat_id
                    )
            
            logger.info(f"[GLOBAL] [create_strategy] 1... Strategy {strat_id} ('{strategy.name}') created")
            return {"id": strat_id, "status": "created"}
    except asyncpg.UniqueViolationError:
        raise HTTPException(status_code=400, detail="Strategy name already exists")
    finally:
        await conn.close()

@app.put("/api/v1/strategies/{strategy_id}")
async def update_strategy(strategy_id: int, strategy: StrategyCreate):
    """Update an existing strategy template."""
    conn = await asyncpg.connect(POSTGRES_URL)
    try:
        async with conn.transaction():
            query = """
                UPDATE aureus_strategy_templates
                SET name = $1, description = $2, config = $3, min_score = $4
                WHERE id = $5
                RETURNING id
            """
            updated_id = await conn.fetchval(query, strategy.name, strategy.description, strategy.config.json(), strategy.min_score, strategy_id)
            if not updated_id:
                raise HTTPException(status_code=404, detail="Strategy not found")
            
            # Sync symbols
            await conn.execute("DELETE FROM aureus_symbol_strategies WHERE strategy_id = $1", strategy_id)
            if strategy.symbols:
                for sym in strategy.symbols:
                    await conn.execute(
                        "INSERT INTO aureus_symbol_strategies (symbol, strategy_id, is_active) VALUES ($1, $2, true)",
                        sym, strategy_id
                    )
                    
            await r.publish("aureus:cmd:refresh_strategies", "ALL")
            logger.info(f"[GLOBAL] [update_strategy] 1... Strategy {strategy_id} updated, refresh published")
            return {"id": updated_id, "status": "updated"}
    except asyncpg.UniqueViolationError:
        raise HTTPException(status_code=400, detail="Strategy name already exists")
    finally:
        await conn.close()

@app.delete("/api/v1/strategies/{strategy_id}")
async def delete_strategy(strategy_id: int):
    """Delete a strategy template."""
    conn = await asyncpg.connect(POSTGRES_URL)
    try:
        # First remove any symbol linking to this strategy
        await conn.execute("DELETE FROM aureus_symbol_strategies WHERE strategy_id = $1", strategy_id)
        
        # Then delete the strategy itself
        status = await conn.execute("DELETE FROM aureus_strategy_templates WHERE id = $1", strategy_id)
        if status == "DELETE 0":
            raise HTTPException(status_code=404, detail="Strategy not found")
            
        await r.publish("aureus:cmd:refresh_strategies", "ALL")
        logger.info(f"[GLOBAL] [delete_strategy] 1... Strategy {strategy_id} deleted")
        return {"status": "deleted"}
    finally:
        await conn.close()

@app.get("/api/v1/symbols/{symbol}/strategies")
async def get_symbol_strategies(symbol: str):
    """Get active strategies for a specific symbol."""
    conn = await asyncpg.connect(POSTGRES_URL)
    try:
        query = """
            SELECT t.id, t.name, t.config, t.min_score, COALESCE(ss_target.is_active, false) as is_active,
                   array_agg(ss_all.symbol) FILTER (WHERE ss_all.symbol IS NOT NULL) as assigned_symbols
            FROM aureus_strategy_templates t
            INNER JOIN aureus_symbol_strategies ss_target ON t.id = ss_target.strategy_id
            LEFT JOIN aureus_symbol_strategies ss_all ON t.id = ss_all.strategy_id
            WHERE ss_target.symbol = $1
            GROUP BY t.id, ss_target.is_active
            ORDER BY t.id ASC
        """
        rows = await conn.fetch(query, symbol)
        return [dict(r) for r in rows]
    finally:
        await conn.close()

@app.post("/api/v1/symbols/{symbol}/strategies/{strategy_id}/toggle")
async def toggle_symbol_strategy(symbol: str, strategy_id: int):
    """Toggle a strategy for a symbol."""
    conn = await asyncpg.connect(POSTGRES_URL)
    try:
        # Check if exists
        exists = await conn.fetchval("SELECT id FROM aureus_symbol_strategies WHERE symbol = $1 AND strategy_id = $2", symbol, strategy_id)
        if exists:
            await conn.execute("UPDATE aureus_symbol_strategies SET is_active = NOT is_active WHERE id = $1", exists)
        else:
            await conn.execute("INSERT INTO aureus_symbol_strategies (symbol, strategy_id, is_active) VALUES ($1, $2, true)", symbol, strategy_id)
        
        # Trigger a refresh notification for the signal engine via Redis
        await r.publish("aureus:cmd:refresh_strategies", symbol)
        logger.info(f"[{symbol}] [toggle_symbol_strategy] 1... Toggled strategy {strategy_id} for {symbol}")
        
        return {"status": "ok"}
    finally:
        await conn.close()

@app.post("/api/v1/symbols/{symbol}/recover")
async def force_symbol_recovery(symbol: str):
    """Force a 60-candle backfill and signal recalculation for a symbol."""
    try:
        cmd = {
            "type": "REQUEST_BACKFILL_COUNT", 
            "symbol": symbol, 
            "count": 60
        }
        await r.publish("aureus:mt5:commands", json.dumps(cmd))
        logger.info(f"[{symbol}] [force_symbol_recovery] 1... Recovery requested (60 candles)")
        return {"status": "ok", "message": f"Recovery requested for {symbol} (60 candles)"}
    except Exception as e:
        logger.error(f"[{symbol}] [force_symbol_recovery] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/ai/health")
async def check_ai_health():
    """Checks the connectivity to the LLM (vLLM / DeepSeek)."""
    try:
        # vLLM/OpenAI health check usually involves calling /models or a simple completion
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get(f"{LLM_BASE_URL}/models")
            if response.status_code == 200:
                return {"status": "ONLINE", "model": "deepseek-r1", "url": LLM_BASE_URL}
            else:
                return {"status": "ERROR", "code": response.status_code, "url": LLM_BASE_URL}
    except Exception as e:
        return {"status": "OFFLINE", "error": str(e), "url": LLM_BASE_URL}

@app.get("/api/v1/ai/model")
async def get_ai_model():
    """Returns the currently active LLM model from Redis, or default."""
    try:
        model = await r.get("aureus:config:llm_model")
        if not model:
            model = "meta-llama/Llama-3.2-3B-Instruct" # Default
        return {"model": model}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class ModelUpdateRequest(BaseModel):
    model: str

@app.post("/api/v1/ai/model")
async def set_ai_model(request: ModelUpdateRequest):
    """Updates the active LLM model in Redis."""
    try:
        await r.set("aureus:config:llm_model", request.model)
        # Push global command unified through Redis Stream instead of PubSub
        await r.xadd("aureus:sys:config", {"type": "LLM_MODEL_CHANGED", "model": request.model})
        logger.info(f"[GLOBAL] [set_ai_model] 1... LLM model set to {request.model}")
        return {"status": "ok", "model": request.model}
    except Exception as e:
        logger.error(f"[GLOBAL] [set_ai_model] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/ai/all_latest")
async def get_all_latest_ai_analysis():
    """Returns the most recent AI market pulse analysis for all symbols."""
    cursor = 0
    results = {}
    while True:
        cursor, keys = await r.scan(cursor, match="aureus:ai:latest:*", count=100)
        for k in keys:
            symbol = k.split(":")[-1]
            data = await r.get(k)
            if data:
                results[symbol] = json.loads(data)
        if cursor == 0: break
    return results

@app.get("/api/v1/ai/history/{symbol}")
async def get_ai_history(symbol: str, limit: int = 10):
    """Returns historical AI analysis and audit logs from TimescaleDB."""
    conn = await asyncpg.connect(POSTGRES_URL)
    try:
        query = """
            SELECT time, symbol, aci, sentiment, narrative, debate_log,
                   analysis_type, decision, key_insight, trigger_id,
                   prompt_tokens, completion_tokens, llm_latency_ms, request_payload, response_payload,
                   algo_score, algo_breakdown, audit_source
            FROM aureus_ai_analysis
            WHERE symbol = $1
            ORDER BY time DESC
            LIMIT $2
        """
        rows = await conn.fetch(query, symbol, limit)
        results = []
        for r in rows:
            results.append({
                "time": int(r['time'].timestamp()),
                "symbol": r['symbol'],
                "aci": r['aci'],
                "sentiment": r['sentiment'],
                "narrative": r['narrative'],
                "debate_log": json.loads(r['debate_log']) if isinstance(r['debate_log'], str) else r['debate_log'],
                "analysis_type": r['analysis_type'],
                "decision": r['decision'],
                "key_insight": r['key_insight'],
                "trigger_id": r['trigger_id'],
                "prompt_tokens": r['prompt_tokens'],
                "completion_tokens": r['completion_tokens'],
                "llm_latency_ms": r['llm_latency_ms'],
                "request_payload": r['request_payload'],
                "response_payload": r['response_payload'],
                "algo_score": r['algo_score'],
                "algo_breakdown": json.loads(r['algo_breakdown']) if isinstance(r['algo_breakdown'], str) else r['algo_breakdown'],
                "audit_source": r.get('audit_source', 'AI')
            })
        logger.info(f"[{symbol}] [get_ai_history] 1... Found {len(results)} history entries")
        return results
    finally:
        await conn.close()

@app.get("/api/v1/ai/latest/{symbol}")
async def get_latest_ai_analysis(symbol: str):
    """Returns the most recent AI market pulse analysis for a symbol."""
    data = await r.get(f"aureus:ai:latest:{symbol}")
    if not data:
        return {
            "narrative": "No analysis available yet.",
            "sentiment": "NEUTRAL",
            "aci": 0,
            "timestamp": int(datetime.now().timestamp())
        }
    return json.loads(data)



# ============================================================
# Performance API — Helper Functions
# ============================================================


async def compute_basic_metrics(pool, symbol, strategy_id, start_dt, end_dt):
    """Compute basic metrics via SQL aggregation (PERF-02, PERF-03, PERF-05)."""
    query = """
    SELECT
        COUNT(*) as total_trades,
        COUNT(CASE WHEN profit > 0 THEN 1 END) as wins,
        COUNT(CASE WHEN profit <= 0 THEN 1 END) as losses,
        SUM(profit) as net_pnl,
        SUM(CASE WHEN profit > 0 THEN profit END) as gross_profit,
        ABS(SUM(CASE WHEN profit < 0 THEN profit END)) as gross_loss,
        AVG(
            CASE
                WHEN direction = 'BUY' THEN (exit_price - entry_price)
                WHEN direction = 'SELL' THEN (entry_price - exit_price)
                ELSE 0
            END / GREATEST(ABS(entry_price - sl), 0.01)
        ) as avg_rr,
        AVG(profit) as avg_profit
    FROM aureus_trades
    WHERE status = 'CLOSED'
      AND ($1::TEXT IS NULL OR symbol = $1)
      AND ($2::BIGINT IS NULL OR strategy_id = $2)
      AND ($3::TIMESTAMPTZ IS NULL OR filled_at >= $3)
      AND ($4::TIMESTAMPTZ IS NULL OR filled_at <= $4)
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, symbol, strategy_id, start_dt, end_dt)

    if row is None or row["total_trades"] == 0:
        return None

    total = row["total_trades"]
    wins = row["wins"]
    gross_profit = row["gross_profit"] or 0
    gross_loss = row["gross_loss"] or 0

    return {
        "total_trades": total,
        "wins": wins,
        "losses": row["losses"],
        "win_rate": round((wins / total) * 100, 2) if total > 0 else 0,
        "net_pnl": round(row["net_pnl"] or 0, 2),
        "profit_factor": round(gross_profit / gross_loss, 2) if gross_loss > 0 else 0,
        "avg_rr": round(row["avg_rr"] or 0, 2),
        "avg_profit": round(row["avg_profit"] or 0, 2),
    }


async def compute_complex_metrics(pool, symbol, strategy_id, start_dt, end_dt):
    """Compute max_drawdown and sharpe_ratio via in-memory calculation (PERF-04)."""
    # Fetch closed trades ordered by fill time
    query = """
    SELECT profit, filled_at
    FROM aureus_trades
    WHERE status = 'CLOSED'
      AND ($1::TEXT IS NULL OR symbol = $1)
      AND ($2::BIGINT IS NULL OR strategy_id = $2)
      AND ($3::TIMESTAMPTZ IS NULL OR filled_at >= $3)
      AND ($4::TIMESTAMPTZ IS NULL OR filled_at <= $4)
    ORDER BY filled_at ASC
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, symbol, strategy_id, start_dt, end_dt)

    if not rows:
        return {"max_drawdown": 0, "sharpe_ratio": 0}

    profits = [r["profit"] for r in rows]

    # Max Drawdown: cumulative equity → peak-to-trough
    equity = np.cumsum(profits)
    peaks = np.maximum.accumulate(equity)
    drawdowns = equity - peaks
    max_drawdown = float(abs(np.min(drawdowns)))

    # Sharpe Ratio: annualized, risk-free = 0
    # Assumes trades spread across ~252 trading days
    if len(profits) < 2:
        sharpe_ratio = 0
    else:
        returns = np.diff(equity) / np.where(equity[:-1] != 0, equity[:-1], 1)
        mean_return = np.mean(returns)
        std_return = np.std(returns)
        sharpe_ratio = float((mean_return / std_return) * np.sqrt(252)) if std_return > 0 else 0

    return {
        "max_drawdown": round(max_drawdown, 2),
        "sharpe_ratio": round(sharpe_ratio, 2),
    }


# ============================================================
# Performance API Endpoints
# ============================================================


VALID_STATUSES = ['CLOSED', 'FILLED', 'FAILED', 'CANCELLED', 'PENDING', 'SENT']
VALID_PAGE_SIZES = [10, 20, 50, 100]
VALID_TIMEFRAMES = ['M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'D1']


def _error_envelope(code: str, message: str, details: Optional[dict] = None):
    return {
        "error": message,
        "code": code,
        "details": details or {}
    }


def _parse_date_param(date_str: Optional[str]) -> tuple:
    """Parse and validate ISO 8601 date string. Returns (datetime_obj, error_response)."""
    if date_str is None:
        return None, None
    try:
        dt = datetime.fromisoformat(date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt, None
    except (ValueError, TypeError):
        return None, _error_envelope(
            "INVALID_DATE",
            f"Invalid ISO 8601 date format: {date_str}",
            {"field": "date", "value": date_str}
        )


def _normalize_performance_filters(
    symbol: Optional[str],
    strategy_id: Optional[int],
    start: Optional[str],
    end: Optional[str],
    timeframe: Optional[str] = None,
    status: Optional[str] = None,
    page: Optional[int] = None,
    page_size: Optional[int] = None,
):
    start_dt, err = _parse_date_param(start)
    if err:
        return None, err
    end_dt, err = _parse_date_param(end)
    if err:
        return None, err

    if start_dt and end_dt and start_dt > end_dt:
        return None, _error_envelope(
            "INVALID_DATE_RANGE",
            "start must be less than or equal to end",
            {"start": start, "end": end}
        )

    normalized_timeframe = timeframe
    if normalized_timeframe is not None and normalized_timeframe not in VALID_TIMEFRAMES:
        return None, _error_envelope(
            "INVALID_TIMEFRAME",
            f"Unsupported timeframe: {normalized_timeframe}",
            {"field": "timeframe", "value": normalized_timeframe, "allowed": VALID_TIMEFRAMES}
        )

    normalized_status = status
    if normalized_status is not None and normalized_status not in VALID_STATUSES:
        return None, _error_envelope(
            "INVALID_STATUS",
            f"Unsupported status: {normalized_status}",
            {"field": "status", "value": normalized_status, "allowed": VALID_STATUSES}
        )

    normalized_page = page
    if normalized_page is not None and normalized_page < 1:
        return None, _error_envelope(
            "INVALID_PAGE",
            "page must be >= 1",
            {"field": "page", "value": page}
        )

    normalized_page_size = page_size
    if normalized_page_size is not None and normalized_page_size not in VALID_PAGE_SIZES:
        return None, _error_envelope(
            "INVALID_PAGE_SIZE",
            f"page_size must be one of {VALID_PAGE_SIZES}",
            {"field": "page_size", "value": page_size, "allowed": VALID_PAGE_SIZES}
        )

    filters = {
        "symbol": symbol,
        "strategy_id": strategy_id,
        "timeframe": normalized_timeframe,
        "start": start_dt.isoformat() if start_dt else None,
        "end": end_dt.isoformat() if end_dt else None,
        "status": normalized_status,
    }

    return {
        "filters": filters,
        "start_dt": start_dt,
        "end_dt": end_dt,
        "status": normalized_status,
        "page": normalized_page,
        "page_size": normalized_page_size,
    }, None


def _performance_cache_key(prefix: str, filters: dict):
    return (
        f"perf:{prefix}:"
        f"symbol={filters.get('symbol') or 'all'}:"
        f"strategy={filters.get('strategy_id') or 'all'}:"
        f"timeframe={filters.get('timeframe') or 'all'}:"
        f"start={filters.get('start') or 'none'}:"
        f"end={filters.get('end') or 'none'}:"
        f"status={filters.get('status') or 'all'}"
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    if isinstance(exc.detail, dict) and {"error", "code", "details"}.issubset(exc.detail.keys()):
        payload = exc.detail
    else:
        payload = _error_envelope("HTTP_ERROR", str(exc.detail), {})
    return JSONResponse(status_code=exc.status_code, content=payload)


@app.exception_handler(Exception)
async def generic_exception_handler(request, exc: Exception):
    logger.error(f"[GLOBAL] [exception] Error: {exc}")
    payload = _error_envelope("INTERNAL_ERROR", "Internal server error", {})
    return JSONResponse(status_code=500, content=payload)


@app.get("/api/v1/performance/trades")
async def get_trades(
    symbol: Optional[str] = None,
    strategy_id: Optional[int] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
    timeframe: Optional[str] = None,
    status: Optional[str] = "CLOSED",
    page: int = 1,
    page_size: int = 20,
):
    """Get paginated trade list with filtering."""
    normalized, err = _normalize_performance_filters(
        symbol=symbol,
        strategy_id=strategy_id,
        start=start,
        end=end,
        timeframe=timeframe,
        status=status,
        page=page,
        page_size=page_size,
    )
    if err:
        raise HTTPException(status_code=400, detail=err)

    status = normalized["status"]
    start_dt = normalized["start_dt"]
    end_dt = normalized["end_dt"]
    page = normalized["page"]
    page_size = normalized["page_size"]
    filters = normalized["filters"]

    # COUNT query
    count_query = """
    SELECT COUNT(*) FROM aureus_trades
    WHERE status = $1
      AND ($2::TEXT IS NULL OR symbol = $2)
      AND ($3::BIGINT IS NULL OR strategy_id = $3)
      AND ($4::TIMESTAMPTZ IS NULL OR filled_at >= $4)
      AND ($5::TIMESTAMPTZ IS NULL OR filled_at <= $5)
    """

    # DATA query
    data_query = """
    SELECT id, trace_id, ticket, symbol, strategy_name, direction,
           entry_price, exit_price, sl, tp, volume,
           profit, commission, swap,
           filled_at, closed_at
    FROM aureus_trades
    WHERE status = $1
      AND ($2::TEXT IS NULL OR symbol = $2)
      AND ($3::BIGINT IS NULL OR strategy_id = $3)
      AND ($4::TIMESTAMPTZ IS NULL OR filled_at >= $4)
      AND ($5::TIMESTAMPTZ IS NULL OR filled_at <= $5)
    ORDER BY filled_at DESC, id DESC
    LIMIT $6 OFFSET ($7 - 1) * $6
    """

    async with app.state.pg_pool.acquire() as conn:
        total = await conn.fetchval(count_query, status, symbol, strategy_id, start_dt, end_dt)
        rows = await conn.fetch(data_query, status, symbol, strategy_id, start_dt, end_dt, page_size, page)

    total_pages = math.ceil(total / page_size) if total > 0 else 0

    trades = []
    for row in rows:
        trades.append({
            "id": row["id"],
            "trace_id": row["trace_id"],
            "ticket": row["ticket"],
            "symbol": row["symbol"],
            "strategy_name": row["strategy_name"],
            "direction": row["direction"],
            "entry_price": row["entry_price"],
            "exit_price": row["exit_price"],
            "sl": row["sl"],
            "tp": row["tp"],
            "volume": row["volume"],
            "profit": row["profit"],
            "commission": row["commission"],
            "swap": row["swap"],
            "filled_at": row["filled_at"].isoformat() if row["filled_at"] else None,
            "closed_at": row["closed_at"].isoformat() if row["closed_at"] else None,
        })

    return {
        "data": trades,
        "meta": {
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "filters": filters,
        }
    }

@app.get("/api/v1/performance/metrics")
async def get_metrics(
    symbol: Optional[str] = None,
    strategy_id: Optional[int] = None,
    timeframe: Optional[str] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
):
    """Get computed performance metrics with Redis caching (60s TTL)."""
    normalized, err = _normalize_performance_filters(
        symbol=symbol,
        strategy_id=strategy_id,
        timeframe=timeframe,
        start=start,
        end=end,
        status="CLOSED",
    )
    if err:
        raise HTTPException(status_code=400, detail=err)

    filters = normalized["filters"]
    start_dt = normalized["start_dt"]
    end_dt = normalized["end_dt"]

    cache_key = _performance_cache_key("metrics", filters)

    cached = await redis_client.get(cache_key)
    if cached:
        logger.info(f"[GLOBAL] [get_metrics] Cache HIT for {cache_key}")
        return json.loads(cached)

    t0 = time.time()

    basic = await compute_basic_metrics(app.state.pg_pool, symbol, strategy_id, start_dt, end_dt)
    if basic is None:
        result = {
            "metrics": {},
            "meta": {
                "filters": filters,
                "source": "live_trades",
                "note": "No closed trades found"
            }
        }
        return result

    complex_m = await compute_complex_metrics(app.state.pg_pool, symbol, strategy_id, start_dt, end_dt)
    metrics = {**basic, **complex_m}

    elapsed = time.time() - t0
    logger.info(f"[GLOBAL] [get_metrics] Computed in {elapsed:.3f}s")

    result = {
        "metrics": metrics,
        "meta": {
            "filters": filters,
            "source": "live_trades",
        }
    }

    await redis_client.setex(cache_key, 30, json.dumps(result, default=str))

    return result


@app.get("/api/v1/performance/equity-curve")
async def get_equity_curve(
    symbol: Optional[str] = None,
    strategy_id: Optional[int] = None,
    timeframe: Optional[str] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
    interval: Optional[str] = None,
):
    """Get equity curve time series with Redis caching (30s TTL)."""
    normalized, err = _normalize_performance_filters(
        symbol=symbol,
        strategy_id=strategy_id,
        timeframe=timeframe,
        start=start,
        end=end,
        status="CLOSED",
    )
    if err:
        raise HTTPException(status_code=400, detail=err)

    filters = normalized["filters"]
    start_dt = normalized["start_dt"]
    end_dt = normalized["end_dt"]

    cache_key = f"{_performance_cache_key('equity', filters)}:interval={interval or 'none'}"

    cached = await redis_client.get(cache_key)
    if cached:
        logger.info(f"[GLOBAL] [get_equity_curve] Cache HIT for {cache_key}")
        return json.loads(cached)

    t0 = time.time()

    snapshot_query = """
    SELECT event_time AS time, equity, realized_pnl, unrealized_pnl
    FROM aureus_account_snapshots
    WHERE ($1::TIMESTAMPTZ IS NULL OR event_time >= $1)
      AND ($2::TIMESTAMPTZ IS NULL OR event_time <= $2)
      AND ($3::TEXT IS NULL OR symbol = $3)
      AND ($4::BIGINT IS NULL OR strategy_id = $4)
      AND ($5::TEXT IS NULL OR timeframe = $5)
    ORDER BY event_time ASC
    """

    async with app.state.pg_pool.acquire() as conn:
        rows = await conn.fetch(snapshot_query, start_dt, end_dt, symbol, strategy_id, timeframe)

    if rows:
        data = [
            {
                "time": (r.get("time") or r.get("event_time")).isoformat(),
                "equity": r["equity"],
                "pnl": r["realized_pnl"],
            }
            for r in rows
        ]
        source = "account_snapshots"
    else:
        fallback_query = """
        SELECT filled_at AS time,
               SUM(profit) OVER (ORDER BY filled_at ASC) AS cumulative_pnl
        FROM aureus_trades
        WHERE status = 'CLOSED'
          AND ($1::TIMESTAMPTZ IS NULL OR filled_at >= $1)
          AND ($2::TIMESTAMPTZ IS NULL OR filled_at <= $2)
          AND ($3::TEXT IS NULL OR symbol = $3)
          AND ($4::BIGINT IS NULL OR strategy_id = $4)
          AND ($5::TEXT IS NULL OR timeframe = $5)
        ORDER BY filled_at ASC
        """
        async with app.state.pg_pool.acquire() as conn:
            rows = await conn.fetch(fallback_query, start_dt, end_dt, symbol, strategy_id, timeframe)

        data = [
            {
                "time": r["time"].isoformat(),
                "equity": r["cumulative_pnl"],
                "pnl": r["cumulative_pnl"],
            }
            for r in rows
        ]
        source = "trades_cumulative"

    elapsed = time.time() - t0
    logger.info(f"[GLOBAL] [get_equity_curve] Fetched {len(data)} points from {source} in {elapsed:.3f}s")

    result = {
        "data": data,
        "meta": {
            "filters": filters,
            "source": source,
            "points": len(data),
            "interval": interval,
        }
    }

    await redis_client.setex(cache_key, 30, json.dumps(result, default=str))

    return result


# legacy block removed


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
