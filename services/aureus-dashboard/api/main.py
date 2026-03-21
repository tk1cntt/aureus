from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import logging

logger = logging.getLogger("aureus-dashboard-api")
import redis.asyncio as redis
import os
import json
import asyncpg
import httpx
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
import os

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

r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
