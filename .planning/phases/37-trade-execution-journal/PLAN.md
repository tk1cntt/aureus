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

### Unit Tests
- `services/aureus-trader/tests/test_journal.py`
  - Test `on_strategy_match` tạo entry với đúng fields
  - Test `on_order_opened` update ticket, entry_price
  - Test `on_order_closed` tính toán duration, result, pnl_pips
  - Test GIN index cho active_signals và context_filters

### Integration Tests
- E2E test: strategy match → journal entry created → ORDER_OPENED → journal updated → ORDER_CLOSED → journal finalized
- Verify jsonb queries hoạt động đúng với GIN indexes

### API Tests
- Test `/api/v1/journal` với various filters
- Test pagination và stats aggregation

---

## Verification
- Migration chạy thành công trên TimescaleDB dev
- Journal entries được tạo khi strategy match được emit
- Journal được update khi ORDER_OPENED/ORDER_CLOSED events được published
- API trả về data chính xác với filters
