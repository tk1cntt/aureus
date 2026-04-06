# Phase 32 — Trade Performance API

## CONTEXT

**Phase:** 32
**Requirements:** PERF-01, PERF-02, PERF-03, PERF-04, PERF-05, PERF-06, PERF-07
**Goal:** API endpoints tính toán và trả về performance metrics.

---

## Decisions

### D1: API Location — Extend `aureus-dashboard-api`

**Decision:** Thêm performance endpoints vào **existing FastAPI app** (`services/aureus-dashboard/api/main.py`), nâng cấp lên connection pooling.

**New endpoints:**
```
GET /api/v1/performance/trades          — Trade list với pagination
GET /api/v1/performance/metrics         — Win rate, PF, drawdown, Sharpe, R:R
GET /api/v1/performance/equity-curve    — Equity time series
```

**Connection pool upgrade:**
```python
# Startup event
@app.on_event("startup")
async def startup():
    app.state.pg_pool = await asyncpg.create_pool(
        DATABASE_URL, min_size=2, max_size=10
    )

# Usage
async with app.state.pg_pool.acquire() as conn:
    rows = await conn.fetch(query, *params)
```

**Rationale:**
- PERF-01→07 yêu cầu API endpoints — FastAPI đã running, không cần service mới
- Shared codebase với existing `/api/v1/chart/{symbol}` (cũng trả trade data)
- Connection pooling giảm latency từ ~50ms (connect/close) → ~5ms (acquire/release)
- Đơn giản deploy: chỉ cần restart 1 service thay vì thêm service mới

**Canonical refs:**
- `services/aureus-dashboard/api/main.py` — Existing FastAPI app, CORS, endpoints
- `services/aureus-db-writer/schema.sql` — `aureus_trades`, `aureus_account_snapshots` tables

---

### D2: Hybrid Metrics — SQL cho Basic, Python cho Complex

**Decision:** Tính metrics ở **2 layers**:

**Layer 1: SQL (Basic Metrics)** — 1 query duy nhất
```sql
SELECT
    COUNT(*) as total_trades,
    COUNT(CASE WHEN profit > 0 THEN 1 END) as wins,
    COUNT(CASE WHEN profit <= 0 THEN 1 END) as losses,
    SUM(profit) as net_pnl,
    SUM(CASE WHEN profit > 0 THEN profit END) as gross_profit,
    ABS(SUM(CASE WHEN profit < 0 THEN profit END)) as gross_loss,
    AVG((exit_price - entry_price) / GREATEST(ABS(entry_price - sl), 0.01)) as avg_rr,
    AVG(profit) as avg_profit
FROM aureus_trades
WHERE status = 'CLOSED'
  AND magic_number IN (SELECT magic_number FROM aureus_strategy_templates WHERE magic_number IS NOT NULL)
  -- Optional filters
  AND ($1::TEXT IS NULL OR symbol = $1)
  AND ($2::BIGINT IS NULL OR strategy_id = $2)
  AND ($3::TIMESTAMPTZ IS NULL OR filled_at >= $3)
  AND ($4::TIMESTAMPTZ IS NULL OR filled_at <= $4)
```

**Computed from SQL results:**
- `win_rate = wins / total_trades * 100`
- `profit_factor = gross_profit / gross_loss` (handle division by zero → 0)

**Layer 2: Python (Complex Metrics)** — Fetch trade list, compute in memory
```python
# Max Drawdown
equity = np.cumsum([t['profit'] for t in trades])
peaks = np.maximum.accumulate(equity)
drawdowns = equity - peaks
max_drawdown = abs(np.min(drawdowns))

# Sharpe Ratio (annualized, risk-free = 0)
returns = np.diff(equity) / equity[:-1]
sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252 * 24 * 60)  # M1 data
```

**Rationale:**
- SQL nhanh cho aggregations (COUNT, SUM, AVG) — DB đã có indexes
- Python linh hoạt cho sequential calculations (drawdown, Sharpe)
- 1 SQL query cho basic metrics → 1 round-trip, <100ms cho 10k trades
- Python computation trong-memory → không có DB load thêm

---

### D3: Equity Curve — `aureus_account_snapshots` với Trade Fallback

**Decision:** Equity curve lấy từ **`aureus_account_snapshots`** (primary), fallback sang cumulative PnL từ `aureus_trades` nếu snapshots thiếu.

**Primary query:**
```sql
SELECT event_time AS time, equity, realized_pnl, unrealized_pnl
FROM aureus_account_snapshots
WHERE event_time >= $1 AND event_time <= $2
ORDER BY event_time
```

**Fallback (if no snapshots):**
```sql
SELECT filled_at AS time,
       SUM(profit) OVER (ORDER BY filled_at) AS cumulative_pnl
FROM aureus_trades
WHERE status = 'CLOSED'
  AND filled_at >= $1 AND filled_at <= $2
ORDER BY filled_at
```

**Response format:**
```json
{
  "data": [
    {"time": "2026-04-06T10:00:00Z", "equity": 10000.0, "pnl": 0.0},
    {"time": "2026-04-06T10:05:00Z", "equity": 10150.0, "pnl": 150.0}
  ],
  "meta": {"source": "account_snapshots", "points": 288}
}
```

**Rationale:**
- Account snapshots capture real equity including deposits, withdrawals, margin changes
- Per-trade profit không account cho account-level changes
- Snapshot frequency đủ dense (từ db-writer) cho smooth equity curve
- Fallback đảm bảo luôn có data dù snapshots chưa có

---

### D4: Response Envelope with Metadata

**Decision:** Tất cả performance endpoints trả về **envelope format** với `data`, `meta`, và `metrics` sections.

**Trade list response:**
```json
{
  "data": [
    {"ticket": 123456, "symbol": "XAUUSD", "direction": "BUY", "entry_price": 2665.5, "exit_price": 2670.0, "profit": 45.0, "filled_at": "...", "closed_at": "..."}
  ],
  "meta": {
    "total": 150,
    "page": 1,
    "page_size": 20,
    "total_pages": 8,
    "filters": {"symbol": "XAUUSD", "strategy_id": 10, "start": "...", "end": "..."}
  }
}
```

**Metrics response:**
```json
{
  "metrics": {
    "total_trades": 150,
    "wins": 98,
    "losses": 52,
    "win_rate": 65.33,
    "net_pnl": 2450.00,
    "profit_factor": 1.85,
    "max_drawdown": 320.00,
    "avg_rr": 1.5,
    "avg_profit": 16.33,
    "sharpe_ratio": 1.25
  },
  "meta": {
    "symbol": "XAUUSD",
    "strategy_id": 10,
    "start": "2026-04-01T00:00:00Z",
    "end": "2026-04-06T17:00:00Z",
    "source": "live_trades"
  }
}
```

**Pagination SQL:**
```sql
-- Count query (fast, indexed)
SELECT COUNT(*) FROM aureus_trades WHERE ... -- same WHERE clause

-- Data query
SELECT * FROM aureus_trades WHERE ...
ORDER BY filled_at DESC
LIMIT $5 OFFSET ($6 - 1) * $5
```

**Rationale:**
- Dashboard UI (Phase 33) cần pagination info để render table controls
- Metrics trong response riêng giúp frontend cache riêng
- Envelope format standard cho REST APIs — dễ integrate với frontend
- Separate count query fast vì dùng index-only scan

---

### D5: Connection Pooling + Redis Cache cho Metrics

**Decision:** **Connection pooling** cho tất cả queries (mandatory), **Redis cache** cho metrics endpoints (60s TTL).

**Connection pool setup:**
```python
@app.on_event("startup")
async def startup():
    app.state.pg_pool = await asyncpg.create_pool(
        DATABASE_URL,
        min_size=2,   # Always have 2 connections ready
        max_size=10,  # Max concurrent connections
    )
    app.state.redis = redis.asyncio.Redis(host="redis-dev", port=6379, decode_responses=True)
```

**Metrics endpoint với cache:**
```python
@app.get("/api/v1/performance/metrics")
async def get_metrics(
    symbol: str = None,
    strategy_id: int = None,
    start: str = None,
    end: str = None
):
    # Build cache key from filters
    cache_key = f"perf:metrics:s={symbol or 'all'}:st={strategy_id or 'all'}:{start}:{end}"
    
    # Check cache
    cached = await app.state.redis.get(cache_key)
    if cached:
        return json.loads(cached)
    
    # Compute metrics
    metrics = await compute_metrics(app.state.pg_pool, symbol, strategy_id, start, end)
    
    # Cache for 60s
    await app.state.redis.setex(cache_key, 60, json.dumps(metrics))
    
    return {"metrics": metrics, "meta": {...}}
```

**Cache strategy:**

| Endpoint | Cache | TTL | Reason |
|----------|-------|-----|--------|
| `/metrics` | ✅ Redis | 60s | Computed, expensive, changes slowly |
| `/equity-curve` | ✅ Redis | 30s | Time series, large, changes slowly |
| `/trades` | ❌ No cache | N/A | Paginated, user expects fresh data |

**Why 60s TTL for metrics:**
- Trade đóng không xảy ra thường xuyên (phút → giờ)
- 60s đủ fresh cho real-time monitoring
- Giảm DB load 95% cho repeated requests
- Auto-invalidated khi TTL expire

**Performance targets:**
| Endpoint | Target | How |
|----------|--------|-----|
| `/metrics` (cached) | <50ms | Redis GET + JSON parse |
| `/metrics` (uncached) | <500ms | 1 SQL query + Python computation |
| `/equity-curve` (cached) | <50ms | Redis GET |
| `/equity-curve` (uncached) | <300ms | 1 SQL query, ~1000 points |
| `/trades` (page 1) | <200ms | COUNT + SELECT LIMIT/OFFSET |

**Rationale:**
- PERF-07: "API response time < 500ms cho dataset up to 10k trades"
- Connection pooling giảm connection overhead từ ~50ms → ~5ms
- Redis cache cho metrics endpoints giảm DB load đáng kể
- No cache cho trade list — user expects fresh paginated data

---

## Reusable Assets

### EXISTS (can reuse):
- ✅ FastAPI app: `services/aureus-dashboard/api/main.py` — CORS, routes, Redis/Postgres connections
- ✅ `aureus_trades` table — Primary data source với đầy đủ columns + indexes
- ✅ `aureus_account_snapshots` table — Equity curve source
- ✅ `aureus_position_snapshots` table — Per-position PnL data
- ✅ Magic number filter SQL: `services/aureus-db-writer/queries/magic_number_filters.sql`
- ✅ asyncpg parameterized query style ($1, $2) — Standard pattern
- ✅ Trade state machine: `services/aureus-db-writer/state_machine.py` — Filter terminal statuses
- ✅ Basic stats pattern: `services/aureus-signal/engine/simulated_orders.py` — Win rate, net PnL
- ✅ BacktestRequest model — Date range filtering pattern

### MUST BUILD:
- ❌ Connection pooling (`asyncpg.create_pool`)
- ❌ Performance endpoints (`/trades`, `/metrics`, `/equity-curve`)
- ❌ Metrics computation functions (SQL + Python hybrid)
- ❌ Pagination logic (LIMIT/OFFSET + COUNT)
- ❌ Redis caching layer cho metrics
- ❌ Response envelope with metadata

## Carry-forward from prior phases

| Source | Decision | Relevance |
|--------|----------|-----------|
| Phase 26 | `magic_number` per strategy | Filter bot trades vs manual trades |
| Phase 30 | `aureus_trades` table with UNIQUE(trace_id) | Primary data source for metrics |
| Phase 30 | `aureus_reconciliation_log` table | Audit trail for reconciled trades |
| Phase 31 | XPENDING recovery + reconciliation loop | Ensure data completeness for metrics |

## Requirements Detail

### PERF-01: API `/api/trades` trả danh sách trades
- [ ] Pagination (page, page_size, total, total_pages)
- [ ] Filtering: symbol, strategy_id, date range, status
- [ ] Response envelope with metadata

### PERF-02: Win rate calculation
- [ ] SQL: `COUNT(wins) / COUNT(*) * 100`
- [ ] Filter: CLOSED trades only

### PERF-03: Profit factor calculation
- [ ] SQL: `SUM(gross_profit) / ABS(SUM(gross_loss))`

### PERF-04: Max drawdown calculation
- [ ] Python: cumulative equity → peak-to-trough → max drawdown

### PERF-05: Average R:R calculation
- [ ] SQL: `AVG((exit_price - entry_price) / ABS(entry_price - sl))` với direction check

### PERF-06: Equity curve time series
- [ ] Primary: `aureus_account_snapshots`
- [ ] Fallback: cumulative SUM from `aureus_trades`

### PERF-07: API response time < 500ms
- [ ] Connection pooling
- [ ] Redis cache cho metrics (60s TTL)
- [ ] Indexed queries (symbol, status, created_at)

## Success Criteria (Updated)

1. ✅ API `/api/v1/performance/trades` trả danh sách trades với pagination và filtering
2. ✅ Win rate, Profit factor, Max drawdown, Average R:R, Sharpe ratio tính chính xác
3. ✅ Equity curve data trả về time series (account snapshots với trade fallback)
4. ✅ Filter hoạt động: symbol, strategy_id, date range, status
5. ✅ API response time < 500ms cho dataset up to 10k trades (pooling + caching)
6. ✅ Connection pooling giảm connection overhead từ ~50ms → ~5ms
7. ✅ Redis cache cho metrics endpoints với 60s TTL

---
*Context created: 2026-04-06*
*Ready for planning*
