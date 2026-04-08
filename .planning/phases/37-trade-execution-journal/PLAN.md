# Implementation Plan: Phase 37 — Trade Execution Journal

## Overview
Trade Execution Journal — lưu nhật ký thực thi trade từ lúc strategy trigger → MT5 order execution → order close. Mục tiêu: phân tích được hiệu quả của từng chiến lược, pattern, signal sequence.

## Architecture

### Data Flow
```
Strategy Match Event (Redis) → aureus-trader → CREATE journal entry (DB)
                                              → Send order to MT5
ORDER_OPENED (Redis event)   → aureus-trader → UPDATE journal with ticket, entry_price
ORDER_CLOSED (Redis event)   → aureus-trader → UPDATE journal with exit_price, pnl, duration
```

### Design Decisions
- **Tích hợp vào aureus-trader** vì service này đã consume cả strategy match queue và mt5:events
- **DB writes trực tiếp** thông qua asyncpg connection pool trong trader service
- **trade_plan_id** làm khóa liên kết — mỗi journal entry tạo trước khi order dispatch
- **Status machine**: PENDING → TRIGGERED → EXECUTED → CLOSED
  (không track FAILED ở đây vì đã có aureus_trades)

---

## Wave 1: Database Schema

### [NEW] `services/aureus-db-writer/migrations/add_trade_journal.sql`
```sql
-- Phase 37: Trade Execution Journal
-- Tracks full lifecycle: strategy trigger → MT5 order → close for analysis

CREATE TABLE IF NOT EXISTS aureus_trade_journal (
    id              SERIAL PRIMARY KEY,
    trace_id        TEXT NOT NULL REFERENCES aureus_trades(trace_id) ON DELETE CASCADE,
    
    -- Trade plan (created at strategy match time)
    status          VARCHAR(30) DEFAULT 'TRIGGERED',
    strategy_name   TEXT NOT NULL,
    strategy_id     BIGINT,
    direction       VARCHAR(10) NOT NULL CHECK (direction IN ('BUY', 'SELL')),
    symbol          TEXT NOT NULL,
    score           DOUBLE PRECISION,
    
    -- Signal context (why this trade was triggered)
    active_signals  JSONB,          -- [{tag, weight, status, time}, ...]
    context_filters JSONB,          -- {htf_trend, session, ob_alignment, ema_trend}
    origin_timestamp TIMESTAMP WITH TIME ZONE,
    
    -- Order details (filled at MT5 execution)
    ticket          BIGINT,
    entry_price     DOUBLE PRECISION,
    entry_time      TIMESTAMP WITH TIME ZONE,
    position_id     BIGINT,
    lot_size        DOUBLE PRECISION,
    sl_initial      DOUBLE PRECISION,
    tp_initial      DOUBLE PRECISION,
    
    -- Exit details (filled at MT5 close)
    exit_price      DOUBLE PRECISION,
    exit_time       TIMESTAMP WITH TIME ZONE,
    exit_reason     VARCHAR(50),    -- TP_HIT, SL_HIT, TRAILING_STOP, MANUAL_CLOSE, SIGNAL_EXIT
    duration_seconds BIGINT,        -- computed: exit_time - entry_time
    pnl             DOUBLE PRECISION,
    pnl_pips        DOUBLE PRECISION,
    commission      DOUBLE PRECISION DEFAULT 0,
    swap            DOUBLE PRECISION DEFAULT 0,
    
    -- Computed analysis fields
    result          VARCHAR(10),    -- WIN / LOSS / BE (breakeven)
    
    -- Metadata
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT now(),
    updated_at      TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- Indexes for analysis queries
CREATE INDEX idx_journal_strategy ON aureus_trade_journal(strategy_id, direction);
CREATE INDEX idx_journal_symbol ON aureus_trade_journal(symbol);
CREATE INDEX idx_journal_status ON aureus_trade_journal(status);
CREATE INDEX idx_journal_created_at ON aureus_trade_journal(created_at DESC);
CREATE INDEX idx_journal_result ON aureus_trade_journal(result);

-- JSONB indexes for signal analysis
CREATE INDEX idx_journal_active_signals ON aureus_trade_journal USING GIN(active_signals);
CREATE INDEX idx_journal_context_filters ON aureus_trade_journal USING GIN(context_filters);

COMMENT ON TABLE aureus_trade_journal IS 'Trade execution journal for strategy analysis';
COMMENT ON COLUMN aureus_trade_journal.active_signals IS 'Sequence of signals that triggered the trade';
COMMENT ON COLUMN aureus_trade_journal.context_filters IS 'Market conditions at entry (HTF trend, session, OB, EMA)';
COMMENT ON COLUMN aureus_trade_journal.exit_reason IS 'Why the trade was closed: TP_HIT, SL_HIT, TRAILING_STOP, MANUAL_CLOSE, SIGNAL_EXIT';
```

### [MODIFY] `services/aureus-db-writer/db_writer.py`
- Thêm hàm `save_trade_journal_entry(journal_data: dict)` — INSERT hoặc UPDATE tùy status
- Thêm hàm `update_journal_on_open(event: dict)` — extract ticket, entry_price, time từ ORDER_OPENED
- Thêm hàm `update_journal_on_close(event: dict)` — extract exit_price, pnl, exit_reason từ ORDER_CLOSED

---

## Wave 2: Trader Service Integration

### [MODIFY] `services/aureus-trader/main.py`
- Kết nối DB pool cho journal writes (reuse existing db-writer connection hoặc tạo mới)
- Khởi tạo JournalManager từ `services/aureus-trader/journal.py`

### [NEW] `services/aureus-trader/journal.py`
```python
"""
Trade Journal — captures strategy match context and updates trade lifecycle events.
Creates entry on strategy match → updates on ORDER_OPENED → updates on ORDER_CLOSED.
"""

class TradeJournalManager:
    def __init__(self, redis_client, db_pool):
        self.redis = redis_client
        self.db = db_pool
    
    async def on_strategy_match(self, match_event: dict):
        """Ghi journal entry khi strategy match được consume từ Redis queue."""
        # Extract: strategy_name, direction, symbol, score, active_signals,
        #   context_filters, origin_timestamp, trace_id
        # INSERT INTO aureus_trade_journal
    
    async def on_order_opened(self, order_opened_event: dict):
        """Update journal khi EA báo ORDER_OPENED."""
        # Extract: ticket, entry_price, open_time, sl, tp, volume
        # WHERE trace_id = match trace_id
        # UPDATE SET status='EXECUTED', ticket=..., entry_price=...
    
    async def on_order_closed(self, order_closed_event: dict):
        """Update journal khi EA báo ORDER_CLOSED."""
        # Extract: close_price, profit, commission, swap, close_time, ticket
        # duration = close_time - entry_time
        # result = WIN if profit > 0, LOSS if profit < 0, BE otherwise
        # UPDATE SET status='CLOSED', exit_price=..., pnl=..., result=...
```

### [MODIFY] `services/aureus-trader/dispatcher.py`
- Inject TradeJournalManager vào OrderDispatcher
- Sau khi consume strategy match từ queue → call `journal.on_strategy_match()` trước khi dispatch
- Trong event_listener → khi nhận ORDER_OPENED → call `journal.on_order_opened()`
- Trong event_listener → khi nhận ORDER_CLOSED → call `journal.on_order_closed()`

---

## Wave 3: API Endpoint

### [NEW] `services/aureus-api/api/routes/journal.py`
- Endpoint: `GET /api/v1/journal` với query parameters:
  - `strategy` — filter theo strategy name
  - `direction` — BUY/SELL
  - `result` — WIN/LOSS/BE
  - `symbol` — filter theo symbol
  - `date_from` / `date_to` — date range
  - `page` / `limit` — pagination
- Response: `{trades: [...], total: N, stats: {...}}`
- Stats includes: win_rate, avg_pnl, avg_duration, total_trades per filter

### [MODIFY] `services/aureus-api/api/main.py`
- Import và register journal router

---

## Testing Strategy

### Test Architecture
- **Framework**: pytest + pytest-asyncio + fakeredis (reuse từ existing test patterns)
- **Mock approach**: FakeRedisMock (tái chế từ test_dispatcher.py) + asyncpg mock pool cho DB
- **Coverage target**: **100% line coverage** + ≥95% branch coverage trên `journal.py`
- **Test files**:
  - `services/aureus-trader/tests/conftest.py` — FIXTURES: mock_redis, mock_db_pool, journal_manager
  - `services/aureus-trader/tests/test_journal.py` — Unit tests (inbound, outbound, white-box, abnormal)
  - `services/aureus-trader/tests/test_journal_integration.py` — dispatcher + journal integration
  - `services/aureus-trader/tests/test_journal_e2e.py` — E2E lifecycle (inspired by test_e2e_mt5_orders.py)
  - `services/aureus-api/tests/test_journal_api.py` — API endpoint black-box tests

---

### Pillar 1: Inbound Tests — Data Input Validation (13 tests)
**White-box: `test_journal.py`**
- **TJ-IN-01**: Valid strategy match → INSERT success với status=TRIGGERED ✓
- **TJ-IN-02**: Missing `trace_id` → RAISE ValueError("trace_id is required") ✓
- **TJ-IN-03**: Missing `strategy_name` → RAISE ValueError("strategy_name is required") ✓
- **TJ-IN-04**: Missing `direction` or direction != BUY/SELL → RAISE ValueError ✓
- **TJ-IN-05**: Missing `symbol` → RAISE ValueError("symbol is required") ✓
- **TJ-IN-06**: `score` là string "abc" → RAISE ValueError("score must be numeric") ✓
- **TJ-IN-07**: `active_signals` không phải list → RAISE TypeError ✓
- **TJ-IN-08**: `origin_timestamp` Unix int → convert sang datetime thành công ✓
- **TJ-IN-09**: Missing `ticket` trong ORDER_OPENED → RAISE ValueError ✓
- **TJ-IN-10**: `entry_price` <= 0 → RAISE ValueError("entry_price must be positive") ✓
- **TJ-IN-11**: Missing `close_price` trong ORDER_CLOSED → RAISE ValueError ✓
- **TJ-IN-12**: `close_time` < `entry_time` → RAISE ValueError ✓
- **TJ-IN-13**: Exit reason invalid ("MAGIC") → RAISE ValueError; valid (TP_HIT, SL_HIT, etc.) → PASS ✓

### Pillar 2: Outbound Tests — Data Output Verification (9 tests)
**White-box: `test_journal.py`**
- **TJ-OUT-01**: on_strategy_match() → INSERT với đầy đủ fields: status=TRIGGERED, strategy_name, direction, symbol, score, active_signals (JSONB), context_filters (JSONB), origin_timestamp ✓
- **TJ-OUT-02**: on_order_opened() → UPDATE: status=EXECUTED, ticket, entry_price, entry_time, sl_initial, tp_initial, updated_at ✓
- **TJ-OUT-03**: on_order_closed() → UPDATE: status=CLOSED, exit_price, exit_time, pnl, commission, swap ✓
- **TJ-OUT-04**: duration_seconds = (exit_time - entry_time).total_seconds() ✓
- **TJ-OUT-05**: result = WIN khi pnl > 0 ✓
- **TJ-OUT-06**: result = LOSS khi pnl < 0 ✓
- **TJ-OUT-07**: result = BE khi pnl == 0 (tolerance ±0.01) ✓
- **TJ-OUT-08**: active_signals và context_filters KHÔNG bị modify sau khi close ✓
- **TJ-OUT-09**: Multiple UPDATEs → verify only target columns change, others preserved ✓

### Pillar 3: Black-box Tests — External API Contract (13 tests)
**`test_journal_api.py`**
- **TJ-BB-01**: GET /api/v1/journal → 200, {trades: [], total: 0} ✓
- **TJ-BB-02**: `?strategy=chandelier_breakout` → filtered correct ✓
- **TJ-BB-03**: `?direction=BUY` → only BUY trades ✓
- **TJ-BB-04**: `?direction=SELL` → only SELL trades ✓
- **TJ-BB-05**: `?result=WIN` → only WIN trades ✓
- **TJ-BB-06**: `?symbol=XAUUSD` → only XAUUSD ✓
- **TJ-BB-07**: `?date_from=...&date_to=...` → date range filter ✓
- **TJ-BB-08**: `?page=1&limit=10` → correct pagination format ✓
- **TJ-BB-09**: `?page=0` → 400 Bad Request ✓
- **TJ-BB-10**: stats.response có win_rate, avg_pnl, avg_duration, total_trades ✓
- **TJ-BB-11**: active_signals, context_filters parseable JSON objects ✓
- **TJ-BB-12**: `?strategy=nonexistent` → 200, empty trades [] ✓
- **TJ-BB-13**: Multiple filters combined → correct intersection ✓

### Pillar 4: White-box Tests — Internal Logic (13 tests)
**`test_journal.py` + `test_journal_integration.py`**
- **TJ-WB-01**: __init__ với valid redis + db → TradeJournalManager created ✓
- **TJ-WB-02**: INSERT SQL query đúng syntax cho tất cả columns ✓
- **TJ-WB-03**: UPDATE SQL cho ORDER_OPENED đúng columns ✓
- **TJ-WB-04**: UPDATE SQL cho ORDER_CLOSED đúng columns ✓
- **TJ-WB-05**: JSONB serialize: active_signals = json.dumps() trước INSERT ✓
- **TJ-WB-06**: JSONB deserialize: fetch → json.loads() ✓
- **TJ-WB-07**: Timezone: entry_time/exit_time phải UTC-aware ✓
- **TJ-WB-08**: pnl_pips = abs(exit - entry) / pip_value (XAUUSD=0.01, EURUSD=0.0001) ✓
- **TJ-WB-09**: JournalManager inject vào OrderDispatcher lúc khởi tạo ✓
- **TJ-WB-10**: on_strategy_match() gọi TRƯỚC khi dispatch_order() ✓
- **TJ-WB-11**: event_listener() → ORDER_OPENED → on_order_opened() ✓
- **TJ-WB-12**: event_listener() → ORDER_CLOSED → on_order_closed() ✓
- **TJ-WB-13**: ORDER_FAILED → KHÔNG gọi journal methods (trade chưa thành công) ✓

### Pillar 5: Abnormal Case Tests — Error Handling & Resilience (18 tests)
**`test_journal.py` + `test_journal_integration.py`**
- **TJ-AB-01**: DB connection error on on_strategy_match() → LOG error, trade plan VẪN dispatch (journal KHÔNG block execution) ✓
- **TJ-AB-02**: DB connection error on on_order_opened() → LOG error + retry next event cycle ✓
- **TJ-AB-03**: DB connection error on on_order_closed() → LOG error + retry ✓
- **TJ-AB-04**: Redis connection loss during match consume → LOG error, event NOT retried (đã consumed) ✓
- **TJ-AB-05**: Duplicate ORDER_OPENED (EA gửi 2 lần) → UPDATE idempotent (không duplicate) ✓
- **TJ-AB-06**: on_order_closed() khi journal entry chưa tồn tại → LOG warning, KHÔNG crash ✓
- **TJ-AB-07**: trace_id không khớp → LOG warning "No journal entry", KHÔNG crash ✓
- **TJ-AB-08**: ORDER_CLOSED cho entry đã CLOSED → LOG warning "Already closed", KHÔNG update ✓
- **TJ-AB-09**: Database timeout (5s) → LOG error + retry with backoff ✓
- **TJ-AB-10**: JSONB quá lớn (10MB active_signals) → LOG warning + truncate ✓
- **TJ-AB-11**: Race condition: ORDER_OPENED đến TRƯỚC on_strategy_match() hoàn thành → retry 3 lần, 1s interval ✓
- **TJ-AB-12**: Concurrent strategy matches → entries KHÔNG overwritten (trace_id unique) ✓
- **TJ-AB-13**: Trader restart giữa chừng → entries KHÔNG mất (đã persist DB) ✓
- **TJ-AB-14**: E2E lifecycle: match → TRIGGERED → OPENED → EXECUTED → CLOSED → data integrity ✓
- **TJ-AB-15**: E2E: ORDER_FAILED → KHÔNG có journal entry (hoặc status=FAILED) ✓
- **TJ-AB-16**: E2E: verify active_signals = signal sequence từ strategy match ✓
- **TJ-AB-17**: E2E: verify context_filters = context filters từ match ✓
- **TJ-AB-18**: E2E: verify duration, result, pnl_pips calculation correctness ✓

### Pillar 6: Schema & Migration Tests (7 tests)
**Schema validation**
- **TJ-SCH-01**: Migration chạy thành công → bảng aureus_trade_journal tồn tại ✓
- **TJ-SCH-02**: Foreign key trace_id → CASCADE DELETE khi aureus_trades bị xóa ✓
- **TJ-SCH-03**: CHECK direction IN ('BUY', 'SELL') → INSERT 'HODL' → ERROR ✓
- **TJ-SCH-04**: NOT NULL strategy_name → INSERT NULL → ERROR ✓
- **TJ-SCH-05**: Indexes tồn tại: idx_journal_strategy, idx_journal_symbol, idx_journal_status, idx_journal_result ✓
- **TJ-SCH-06**: GIN indexes: active_signals, context_filters → JSONB containment queries ✓
- **TJ-SCH-07**: DEFAULT: status='TRIGGERED', commission=0, swap=0, created_at=now() ✓

---

## Test Coverage Requirement
| Metric | Target | Measurement |
|--------|--------|-------------|
| Line coverage (journal.py) | **100%** | `pytest --cov=journal --cov-report=term-missing` |
| Branch coverage (journal.py) | ≥ 95% | `pytest --cov=journal --cov-branch --cov-report=term-missing` |

---

## Verification Commands (HOW TO RUN)

### 1. Unit Tests
```bash
cd services/aureus-trader
pytest tests/test_journal.py -v --cov=journal --cov-report=term-missing
```

### 2. Integration Tests
```bash
cd services/aureus-trader
pytest tests/test_journal_integration.py -v
```

### 3. E2E Tests (need running Redis + MT5 + Gateway)
```bash
cd services/aureus-trader
pytest tests/test_journal_e2e.py -v -s
```

### 4. API Tests
```bash
cd services/aureus-api
pytest tests/test_journal_api.py -v
```

### 5. Schema/Migration Validation
```bash
# Run migration
wsl -d Aureus -e bash -lc "docker exec -i aureus_timescaledb_dev psql -U aureus -d aureus -f /mnt/d/Aureus/services/aureus-db-writer/migrations/add_trade_journal.sql"

# Verify schema
wsl -d Aureus -e bash -lc "docker exec -i aureus_timescaledb_dev psql -U aureus -d aureus -c '\d aureus_trade_journal'"
```

### 6. Full Coverage Report
```bash
cd services/aureus-trader
pytest tests/test_journal*.py --cov=journal --cov-report=term-missing --cov-report=html
# Verify htmlcov/index.html shows 100% line coverage and ≥95% branch coverage
```
