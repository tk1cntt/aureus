---
phase: 32
plan: 01
type: execute
wave: 1
depends_on:
  - 30-01
files_modified:
  - services/aureus-dashboard/api/main.py
  - services/aureus-dashboard/api/requirements.txt
autonomous: true
requirements:
  - PERF-01
  - PERF-02
  - PERF-03
  - PERF-04
  - PERF-05
  - PERF-06
  - PERF-07

must_haves:
  truths:
    - "API /api/v1/performance/trades returns paginated trade list with filters"
    - "API /api/v1/performance/metrics returns computed metrics (win rate, PF, drawdown, R:R, Sharpe)"
    - "API /api/v1/performance/equity-curve returns equity time series data"
    - "Metrics response cached in Redis with 60s TTL"
    - "Equity curve response cached in Redis with 30s TTL"
    - "Connection pooling active (app.state.pg_pool) instead of per-request connect/close"
    - "Filter parameters (symbol, strategy_id, start, end) work across all endpoints"
  artifacts:
    - path: "services/aureus-dashboard/api/main.py"
      provides: "Performance endpoints with connection pooling"
      contains: "asyncpg.create_pool"
      exports:
        - "/api/v1/performance/trades"
        - "/api/v1/performance/metrics"
        - "/api/v1/performance/equity-curve"
    - path: "services/aureus-dashboard/api/requirements.txt"
      provides: "numpy dependency for metrics computation"
      contains: "numpy"
  key_links:
    - from: "services/aureus-dashboard/api/main.py"
      to: "aureus_trades table"
      via: "asyncpg pool queries"
      pattern: "SELECT.*FROM aureus_trades"
    - from: "services/aureus-dashboard/api/main.py"
      to: "aureus_account_snapshots table"
      via: "equity curve primary query"
      pattern: "SELECT.*FROM aureus_account_snapshots"
    - from: "services/aureus-dashboard/api/main.py"
      to: "Redis cache"
      via: "redis.asyncio setex/get for metrics caching"
      pattern: "redis.*setex|redis.*get"

---

<objective>
Add 3 performance endpoints to existing FastAPI dashboard app with connection pooling, Redis caching, and hybrid SQL+Python metrics computation.

Purpose: Provide trade performance data (trade list, metrics, equity curve) for Phase 33 Dashboard UI.
Output: /api/v1/performance/trades, /metrics, /equity-curve endpoints with pooling + caching
</objective>

<execution_context>
@D:/Aureus/.qwen/get-shit-done/workflows/execute-plan.md
@D:/Aureus/.qwen/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/32-trade-performance-api/32-CONTEXT.md
@.planning/phases/30-trade-state-management/30-01-PLAN.md
@.planning/phases/30-trade-state-management/30-01-SUMMARY.md
@services/aureus-dashboard/api/main.py
@services/aureus-db-writer/schema.sql
@services/aureus-db-writer/state_machine.py

<interfaces>
<!-- Key types and contracts the executor needs. Extracted from codebase. -->

From services/aureus-dashboard/api/main.py — Current app pattern:
```python
# Current: per-request connection (MUST upgrade to pooling)
conn = await asyncpg.connect(POSTGRES_URL)
try:
    rows = await conn.fetch(query, *params)
finally:
    await conn.close()

# NEW: Connection pool on startup
@app.on_event("startup")
async def startup():
    app.state.pg_pool = await asyncpg.create_pool(
        DATABASE_URL, min_size=2, max_size=10
    )

# Usage in endpoints
async with app.state.pg_pool.acquire() as conn:
    rows = await conn.fetch(query, *params)
```

From services/aureus-dashboard/api/main.py — Current Redis pattern:
```python
r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
# Usage: data = await r.get("key") / await r.setex("key", 60, "value")
```

From services/aureus-db-writer/schema.sql — aureus_trades columns:
```sql
-- Key columns for performance queries:
-- id, trace_id, ticket, symbol, magic_number, strategy_id, strategy_name
-- direction (BUY/SELL), entry_type, status (PENDING/SENT/FILLED/CLOSED/FAILED/CANCELLED)
-- entry_price, exit_price, sl, tp, volume, commission, swap, profit
-- created_at, updated_at, filled_at, closed_at, payload (JSONB)
```

From services/aureus-db-writer/schema.sql — aureus_account_snapshots:
```sql
CREATE TABLE aureus_account_snapshots (
    event_time        TIMESTAMPTZ NOT NULL,
    account_id        TEXT NOT NULL,
    equity            DOUBLE PRECISION,
    balance           DOUBLE PRECISION,
    margin_used       DOUBLE PRECISION,
    margin_free       DOUBLE PRECISION,
    unrealized_pnl    DOUBLE PRECISION,
    realized_pnl      DOUBLE PRECISION,
    payload           JSONB NOT NULL,
    UNIQUE (account_id, event_time)
);
```

From services/aureus-db-writer/schema.sql — aureus_strategy_templates:
```sql
-- magic_number column exists for bot trade filtering
ALTER TABLE aureus_strategy_templates ADD COLUMN IF NOT EXISTS magic_number BIGINT;
```

From 32-CONTEXT.md D4 — Response envelope format:
```json
{
  "data": [...],
  "meta": {"total": 150, "page": 1, "page_size": 20, "total_pages": 8, "filters": {...}},
  "metrics": {...}
}
```
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add numpy dependency and upgrade to connection pooling</name>
  <files>
    services/aureus-dashboard/api/main.py
    services/aureus-dashboard/api/requirements.txt
  </files>
  <read_first>
    - services/aureus-dashboard/api/main.py
    - services/aureus-dashboard/api/requirements.txt
    - services/aureus-dashboard/api/Dockerfile (if exists)
  </read_first>
  <action>
1. **Add numpy to requirements.txt**: Append `numpy>=1.24.0` to the file. This is needed for max drawdown and Sharpe ratio computation (Task 3).

2. **Add DATABASE_URL env var** to main.py imports (reuse existing POSTGRES_URL pattern, but name it consistently):
   ```python
   DATABASE_URL = os.getenv("DATABASE_URL", POSTGRES_URL)
   ```

3. **Add startup event for connection pooling** — Insert BEFORE existing endpoints:
   ```python
   @app.on_event("startup")
   async def startup():
       # Connection pool for PostgreSQL
       app.state.pg_pool = await asyncpg.create_pool(
           DATABASE_URL,
           min_size=2,
           max_size=10,
       )
       logger.info("[GLOBAL] [startup] PostgreSQL connection pool created (min=2, max=10)")
   ```

4. **Add shutdown event** for clean pool closure:
   ```python
   @app.on_event("shutdown")
   async def shutdown():
       if hasattr(app.state, 'pg_pool'):
           await app.state.pg_pool.close()
           logger.info("[GLOBAL] [shutdown] PostgreSQL connection pool closed")
   ```

5. **Upgrade Redis instance to async** — Replace the sync Redis usage for the new performance endpoints. The existing `r = redis.Redis(...)` stays for backward compat, but add an async version:
   ```python
   redis_client = redis.asyncio.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
   ```
   This `redis_client` will be used for cache operations in Tasks 2-3.

6. **Do NOT modify existing endpoints** — They continue using `asyncpg.connect()` / `conn.close()`. Only NEW performance endpoints use `app.state.pg_pool`.

7. **Add math import** at top: `import math` and `import numpy as np` (for Task 3).
  </action>
  <verify>
    <automated>cd services/aureus-dashboard/api && python -c "import main; print('Imports OK')"</automated>
  </verify>
  <done>
    - requirements.txt contains numpy>=1.24.0
    - main.py has startup/shutdown events for pg_pool
    - main.py has redis_client (async) alongside existing r (sync)
    - main.py imports numpy and math
    - Existing endpoints unchanged (still use asyncpg.connect/close)
    - `python -c "import main"` runs without errors
  </done>
</task>

<task type="auto">
  <name>Task 2: Create /api/v1/performance/trades endpoint with pagination and filtering</name>
  <files>
    services/aureus-dashboard/api/main.py
  </files>
  <read_first>
    - services/aureus-dashboard/api/main.py
    - services/aureus-db-writer/schema.sql
  </read_first>
  <action>
1. **Add Pydantic models** for request/response — Place after existing models (after ModelUpdateRequest):

   ```python
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
   ```

2. **Add GET /api/v1/performance/trades endpoint** — After existing `/api/v1/ai/*` endpoints:

   ```python
   @app.get("/api/v1/performance/trades")
   async def get_trades(
       symbol: Optional[str] = None,
       strategy_id: Optional[int] = None,
       start: Optional[str] = None,
       end: Optional[str] = None,
       status: Optional[str] = "CLOSED",
       page: int = 1,
       page_size: int = 20,
   ):
   ```

3. **Implement parameter validation**:
   - `page`: Must be >= 1, default to 1 if < 1
   - `page_size`: Must be in [10, 20, 50, 100], default to 20 if not in list
   - `status`: Must be in ['CLOSED', 'FILLED', 'FAILED', 'CANCELLED', 'PENDING', 'SENT'], default 'CLOSED'
   - `start`/`end`: If provided, validate ISO 8601 format with `datetime.fromisoformat()`. Return 400 if invalid.
   - `symbol`: Optional, no validation needed (SQL parameterized)

4. **Build SQL queries** — Two queries (COUNT + DATA):

   **COUNT query** (for pagination meta):
   ```sql
   SELECT COUNT(*) FROM aureus_trades
   WHERE status = $1
     AND ($2::TEXT IS NULL OR symbol = $2)
     AND ($3::BIGINT IS NULL OR strategy_id = $3)
     AND ($4::TIMESTAMPTZ IS NULL OR filled_at >= $4)
     AND ($5::TIMESTAMPTZ IS NULL OR filled_at <= $5)
   ```

   **DATA query** (paginated trade list):
   ```sql
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
   ORDER BY filled_at DESC
   LIMIT $6 OFFSET ($7 - 1) * $6
   ```

5. **Execute with connection pool**:
   ```python
   async with app.state.pg_pool.acquire() as conn:
       total = await conn.fetchval(count_query, status, symbol, strategy_id, start_dt, end_dt)
       rows = await conn.fetch(data_query, status, symbol, strategy_id, start_dt, end_dt, page_size, page)
   ```

6. **Build response envelope** (per D4):
   ```python
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
           "filters": {
               "symbol": symbol,
               "strategy_id": strategy_id,
               "start": start,
               "end": end,
               "status": status,
           }
       }
   }
   ```

7. **Add error handling** — Wrap in try/except, return 500 with error detail if query fails. Log errors with logger.

8. **DO NOT cache this endpoint** — Per D5, trade list is paginated and user expects fresh data.
  </action>
  <verify>
    <automated>cd services/aureus-dashboard/api && python -c "from main import app; routes = [r.path for r in app.routes]; assert '/api/v1/performance/trades' in routes; print('Route registered OK')"</automated>
  </verify>
  <done>
    - GET /api/v1/performance/trades endpoint exists and registered
    - Pagination works: page, page_size, total, total_pages in response meta
    - Filtering works: symbol, strategy_id, start, end, status parameters
    - Response envelope: {"data": [...], "meta": {...}}
    - page_size capped to [10, 20, 50, 100]
    - Connection pool used (app.state.pg_pool.acquire())
    - No Redis caching for this endpoint
    - Invalid date params return 400
  </done>
</task>

<task type="auto">
  <name>Task 3: Create /api/v1/performance/metrics and /api/v1/performance/equity-curve endpoints with Redis caching</name>
  <files>
    services/aureus-dashboard/api/main.py
  </files>
  <read_first>
    - services/aureus-dashboard/api/main.py
    - services/aureus-db-writer/schema.sql
  </read_first>
  <action>
1. **Add helper function `compute_basic_metrics`** — Place before the endpoint definitions. This runs a single SQL query and computes win_rate + profit_factor:

   ```python
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
   ```

2. **Add helper function `compute_complex_metrics`** — Python-based computation for max_drawdown and sharpe_ratio (PERF-04):

   ```python
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
   ```

3. **Add GET /api/v1/performance/metrics endpoint** — With Redis caching (60s TTL):

   ```python
   @app.get("/api/v1/performance/metrics")
   async def get_metrics(
       symbol: Optional[str] = None,
       strategy_id: Optional[int] = None,
       start: Optional[str] = None,
       end: Optional[str] = None,
   ):
   ```

   **Implementation**:
   a. Parse and validate date params (same as Task 2)
   b. Build cache key: `f"perf:metrics:s={symbol or 'all'}:st={strategy_id or 'all'}:{start}:{end}"`
   c. Check cache: `cached = await redis_client.get(cache_key)` → if found, return `json.loads(cached)`
   d. Compute metrics:
      ```python
      basic = await compute_basic_metrics(app.state.pg_pool, symbol, strategy_id, start_dt, end_dt)
      if basic is None:
          result = {"metrics": {}, "meta": {"symbol": symbol, "strategy_id": strategy_id, "start": start, "end": end, "source": "live_trades", "note": "No closed trades found"}}
          return result

      complex_m = await compute_complex_metrics(app.state.pg_pool, symbol, strategy_id, start_dt, end_dt)
      metrics = {**basic, **complex_m}
      ```
   e. Build response:
      ```python
      result = {
          "metrics": metrics,
          "meta": {
              "symbol": symbol,
              "strategy_id": strategy_id,
              "start": start,
              "end": end,
              "source": "live_trades",
          }
      }
      ```
   f. Cache result: `await redis_client.setex(cache_key, 60, json.dumps(result))`
   g. Return result

4. **Add GET /api/v1/performance/equity-curve endpoint** — With Redis caching (30s TTL):

   ```python
   @app.get("/api/v1/performance/equity-curve")
   async def get_equity_curve(
       start: Optional[str] = None,
       end: Optional[str] = None,
       interval: Optional[str] = None,  # "1h", "4h", "1d" — optional aggregation
   ):
   ```

   **Implementation**:
   a. Parse dates — default to last 7 days if not provided
   b. Build cache key: `f"perf:equity:{start}:{end}:{interval}"`
   c. Check cache → return if found
   d. **Primary query** — `aureus_account_snapshots`:
      ```sql
      SELECT event_time AS time, equity, realized_pnl, unrealized_pnl
      FROM aureus_account_snapshots
      WHERE ($1::TIMESTAMPTZ IS NULL OR event_time >= $1)
        AND ($2::TIMESTAMPTZ IS NULL OR event_time <= $2)
      ORDER BY event_time ASC
      ```
   e. **Check result count** — If 0 rows, use **fallback query** from `aureus_trades`:
      ```sql
      SELECT filled_at AS time,
             SUM(profit) OVER (ORDER BY filled_at ASC) AS cumulative_pnl
      FROM aureus_trades
      WHERE status = 'CLOSED'
        AND ($1::TIMESTAMPTZ IS NULL OR filled_at >= $1)
        AND ($2::TIMESTAMPTZ IS NULL OR filled_at <= $2)
      ORDER BY filled_at ASC
      ```
   f. **Build response** — Format based on source:
      ```python
      # From snapshots
      data = [{"time": r["time"].isoformat(), "equity": r["equity"], "pnl": r["realized_pnl"]} for r in rows]
      source = "account_snapshots"

      # OR from trades fallback
      data = [{"time": r["time"].isoformat(), "equity": r["cumulative_pnl"], "pnl": r["cumulative_pnl"]} for r in rows]
      source = "trades_cumulative"
      ```
   g. Cache with 30s TTL: `await redis_client.setex(cache_key, 30, json.dumps(result))`
   h. Return: `{"data": data, "meta": {"source": source, "points": len(data)}}`

5. **Add logging** — Log query execution time for each endpoint:
   ```python
   import time
   t0 = time.time()
   # ... query execution ...
   logger.info(f"[GLOBAL] [get_metrics] Computed in {time.time()-t0:.3f}s")
   ```

6. **IMPORTANT: Direction-aware R:R calculation** — In `compute_basic_metrics`, the avg_rr formula MUST account for direction:
   - BUY: `(exit_price - entry_price) / ABS(entry_price - sl)`
   - SELL: `(entry_price - exit_price) / ABS(entry_price - sl)`
   - This ensures positive R:R for winning trades regardless of direction
  </action>
  <verify>
    <automated>cd services/aureus-dashboard/api && python -c "from main import app; routes = [r.path for r in app.routes]; assert '/api/v1/performance/metrics' in routes; assert '/api/v1/performance/equity-curve' in routes; print('Both routes registered OK')"</automated>
  </verify>
  <done>
    - GET /api/v1/performance/metrics endpoint exists with Redis cache (60s TTL)
    - GET /api/v1/performance/equity-curve endpoint exists with Redis cache (30s TTL)
    - Metrics response: {"metrics": {win_rate, profit_factor, max_drawdown, avg_rr, sharpe_ratio, ...}, "meta": {...}}
    - Equity curve response: {"data": [{time, equity, pnl}], "meta": {source, points}}
    - Basic metrics computed via single SQL aggregation query
    - Max drawdown computed via numpy cumulative equity method
    - Sharpe ratio computed via numpy returns method (annualized)
    - Equity curve uses aureus_account_snapshots (primary) with aureus_trades fallback
    - Cache keys include filter parameters
    - Empty result returns empty metrics/note, not error
  </done>
</task>

</tasks>

<verification>
## Phase-Level Verification

1. **Connection Pooling**: `app.state.pg_pool` exists after startup, min_size=2, max_size=10
2. **Trade List**: GET /api/v1/performance/trades returns paginated results with correct envelope format
3. **Metrics**: Win rate = wins/total*100, Profit factor = gross_profit/gross_loss, avg_rr direction-aware
4. **Max Drawdown**: Computed via cumulative equity → peak-to-trough → abs(min(drawdowns))
5. **Sharpe Ratio**: Computed via returns std, annualized with sqrt(252)
6. **Equity Curve**: Returns time series from account_snapshots or trades fallback
7. **Caching**: Metrics cached 60s, equity-curve cached 30s — verified via Redis CLI
8. **Filters**: symbol, strategy_id, start, end work across all 3 endpoints
9. **Response Time**: <500ms for datasets up to 10k trades (pooling + SQL aggregation ensures this)
10. **No Breaking Changes**: Existing endpoints (/api/v1/chart, /api/v1/strategies, etc.) still functional
</verification>

<success_criteria>
1. ✅ API `/api/v1/performance/trades` trả danh sách trades với pagination (page, page_size, total, total_pages) và filtering (symbol, strategy_id, date range, status)
2. ✅ Win rate, Profit factor, Max drawdown, Average R:R, Sharpe ratio tính chính xác qua hybrid SQL+Python
3. ✅ Equity curve data trả về time series từ `aureus_account_snapshots` với fallback `aureus_trades`
4. ✅ Filter hoạt động trên tất cả endpoints: symbol, strategy_id, start date, end date
5. ✅ API response time < 500ms cho dataset up to 10k trades (connection pooling + SQL aggregation)
6. ✅ Connection pooling active: `asyncpg.create_pool(min_size=2, max_size=10)` thay vì per-request connect/close
7. ✅ Redis cache: /metrics (60s TTL), /equity-curve (30s TTL), /trades (no cache)
8. ✅ Response envelope format: `{"data": [...], "meta": {...}}` consistent across endpoints
9. ✅ Existing endpoints không bị ảnh hưởng (backward compatible)
</success_criteria>

<output>
After completion, create `.planning/phases/32-trade-performance-api/32-01-SUMMARY.md`
</output>
