# Phase 30 — Trade State Management

## CONTEXT

**Phase:** 30
**Requirements:** TRADE-01, TRADE-02, TRADE-05
**Goal:** Quản lý vòng đời order với state machine và persistent storage.

---

## Decisions

### D1: Trade Table Schema — Hypertable with JSONB Payload

**Decision:** Tạo **`aureus_trades`** hypertable trong `schema.sql` với columns cơ bản + JSONB payload cho full event data.

**Schema:**
```sql
CREATE TABLE IF NOT EXISTS aureus_trades (
    id                  BIGSERIAL PRIMARY KEY,
    trace_id            TEXT NOT NULL,              -- Unique trade identifier (cmd_id from trader)
    ticket              BIGINT,                      -- MT5 order ticket (NULL until filled)
    symbol              TEXT NOT NULL,
    magic_number        BIGINT,                      -- For filtering bot vs manual trades
    strategy_id         BIGINT,
    strategy_name       TEXT,
    direction           TEXT NOT NULL,               -- BUY / SELL
    entry_type          TEXT NOT NULL,               -- MARKET / LIMIT / STOP
    status              TEXT NOT NULL DEFAULT 'PENDING',
    entry_price         DOUBLE PRECISION,
    exit_price          DOUBLE PRECISION,
    sl                  DOUBLE PRECISION,
    tp                  DOUBLE PRECISION,
    volume              DOUBLE PRECISION,
    commission          DOUBLE PRECISION DEFAULT 0,
    swap                DOUBLE PRECISION DEFAULT 0,
    profit              DOUBLE PRECISION DEFAULT 0,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    filled_at           TIMESTAMPTZ,
    closed_at           TIMESTAMPTZ,
    payload             JSONB                        -- Full event data for debugging
);

-- Hypertable conversion for time-series queries
SELECT create_hypertable('aureus_trades', 'created_at', if_not_exists => TRUE);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_trades_symbol ON aureus_trades(symbol);
CREATE INDEX IF NOT EXISTS idx_trades_status ON aureus_trades(status);
CREATE INDEX IF NOT EXISTS idx_trades_magic ON aureus_trades(magic_number);
CREATE INDEX IF NOT EXISTS idx_trades_ticket ON aureus_trades(ticket);
CREATE INDEX IF NOT EXISTS idx_trades_strategy ON aureus_trades(strategy_id);
```

**Rationale:**
- TRADE-02: "Trade records lưu vào PostgreSQL/TimescaleDB" → cần table mới
- Hypertable cho phép time-range queries hiệu quả (Phase 32 performance API)
- JSONB payload lưu full event data cho debug/replay mà không cần thêm columns
- `trace_id` link với `cmd_id` từ Phase 29 (idempotency key)
- `magic_number` filter cho TRADE-05: phân biệt bot vs manual trades

**Canonical refs:**
- `services/aureus-db-writer/schema.sql` — Existing schema (append here)
- `services/aureus-db-writer/main.py` — DB writer pattern (asyncpg bulk insert)

---

### D2: Order State Machine — 5-Status Lifecycle

**Decision:** Implement **5-state machine**: `PENDING → SENT → FILLED → CLOSED` với các terminal states `FAILED`, `CANCELLED`.

**State transitions:**
```
PENDING ──→ SENT ──→ FILLED ──→ CLOSED
   │         │         │
   ↓         ↓         ↓
FAILED    FAILED    FAILED
            │
            ↓
         CANCELLED
```

**Status definitions:**
| Status | Meaning | Trigger |
|--------|---------|---------|
| PENDING | Order validated, queued in Redis | Trader receives STRATEGY_MATCH |
| SENT | Command published to `aureus:mt5:commands` | Trader publishes OPEN_ORDER |
| FILLED | MT5 executed OrderSend() successfully | ACK received with ticket number |
| CLOSED | Position closed (SL/TP/manual) | ORDER_CLOSED event from EA |
| FAILED | Order rejected or execution error | NACK received |
| CANCELLED | Order cancelled before fill | Explicit CLOSE_ORDER before FILLED |

**Implementation:** Stateless validation function trong `services/aureus-trader/dispatcher.py` — không cần separate state machine class.

**Rationale:**
- TRADE-01: "Order state machine tracking (pending → sent → filled → closed)"
- Reuse existing Nautilus bridge state machine pattern (`ALLOWED_TRANSITIONS` dict)
- Simple dict-based transitions đủ cho v1, không cần复杂 state machine library
- Terminal states (FAILED, CANCELLED) không cho phép transition tiếp

**Canonical refs:**
- `services/aureus-nautilus-bridge/reconciliation.py` — `ALLOWED_TRANSITIONS` dict pattern
- `services/aureus-trader/dispatcher.py` — Existing order dispatch logic (extend here)

---

### D3: Magic Number Filter — WHERE Clause trên DB Queries

**Decision:** TRADE-05 ("Magic number filter phân biệt bot vs manual trades") implement ở **DB query layer**, không phải ở EA hay trader.

**Implementation:**
```sql
-- Query bot trades only
SELECT * FROM aureus_trades WHERE magic_number IN (
    SELECT magic_number FROM aureus_strategy_templates
)
AND status = 'CLOSED';

-- Query manual trades (no matching magic_number in strategy_templates)
SELECT * FROM aureus_trades WHERE magic_number NOT IN (
    SELECT magic_number FROM aureus_strategy_templates
)
AND magic_number IS NOT NULL;
```

**EA behavior:** EA push TẤT CẢ order events (kể cả manual) với `magic_number` field. DB writer lưu tất cả. Filter áp dụng khi query.

**Rationale:**
- TRADE-05: "Magic number filter phân biệt bot vs manual trades"
- EA không cần biết order nào là bot/manual — chỉ cần report đúng magic_number
- Filter ở query layer linh hoạt hơn (có thể change logic không cần redeploy EA)
- `aureus_strategy_templates.magic_number` (Phase 26) là source of truth cho bot magic numbers

**Canonical refs:**
- `services/aureus-signal/engine/strategy_executor.py` — magic_number in STRATEGY_MATCH payload
- Phase 26 CONTEXT.md D3: `magic_number` static mapping trong DB

---

### D4: DB Writer Integration — New `order` Buffer Type

**Decision:** Extend `aureus-db-writer/main.py` với **new `order_buffer`** consume từ Redis stream `aureus:stream:{symbol}:orders`.

**Stream pattern:** Subscribe `aureus:stream:*:orders` (wildcard for all symbols)

**Buffer flush logic:**
```python
# In process_batch():
if buffer_type == 'order':
    await conn.executemany("""
        INSERT INTO aureus_trades (
            trace_id, ticket, symbol, magic_number, strategy_id, strategy_name,
            direction, entry_type, status, entry_price, exit_price,
            sl, tp, volume, commission, swap, profit,
            filled_at, closed_at, payload
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20)
        ON CONFLICT (trace_id) DO UPDATE SET
            ticket = EXCLUDED.ticket,
            status = EXCLUDED.status,
            exit_price = EXCLUDED.exit_price,
            profit = EXCLUDED.profit,
            closed_at = EXCLUDED.closed_at,
            updated_at = NOW(),
            payload = aureus_trades.payload || EXCLUDED.payload
    """, batch)
```

**Conflict resolution:** `ON CONFLICT (trace_id) DO UPDATE` — merge fields khi có event mới (ví dụ: PENDING → FILLED update ticket, FILLED → CLOSED update profit)

**Payload merge:** `payload || EXCLUDED.payload` — JSONB merge để giữ history của tất cả events

**Rationale:**
- Reuse existing DB writer pattern (tick, candle, execution buffers)
- Redis stream `aureus:stream:{symbol}:orders` đã tồn tại từ SimulatedTradeManager
- `ON CONFLICT` đảm bảo idempotent writes ( Phase 29 idempotency key = trace_id)
- JSONB merge cho phép incremental updates mà không mất data cũ

**Canonical refs:**
- `services/aureus-db-writer/main.py` — Existing buffer patterns (lines 100-200)
- `services/aureus-signal/engine/orders.py` — Redis stream writes for orders

---

## Reusable Assets

### EXISTS (can reuse):
- ✅ DB schema: `services/aureus-db-writer/schema.sql` — append `aureus_trades` table
- ✅ DB writer pattern: `services/aureus-db-writer/main.py` — `process_batch()`, buffer system
- ✅ State machine pattern: `services/aureus-nautilus-bridge/reconciliation.py` — `ALLOWED_TRANSITIONS`
- ✅ Redis stream: `aureus:stream:{symbol}:orders` — already written by SimulatedTradeManager
- ✅ Magic number source: `aureus_strategy_templates.magic_number` (Phase 26)
- ✅ asyncpg connection setup: DB writer `create_pool()` pattern
- ✅ Order structure: `services/aureus-signal/engine/orders.py` — order dict schema

### MUST BUILD:
- ❌ `aureus_trades` table in `schema.sql`
- ❌ `order_buffer` in DB writer main.py
- ❌ State transition validation in trader dispatcher
- ❌ Magic number filter queries for Phase 32 API

## Carry-forward from prior phases

| Source | Decision | Relevance |
|--------|----------|-----------|
| Phase 26 | `magic_number` in `aureus_strategy_templates` | Source of truth for bot magic numbers |
| Phase 26 | STRATEGY_MATCH payload includes `magic_number` | Used in trade record |
| Phase 28 | EA pushes ORDER_OPENED/CLOSED/FAILED events | Trigger state transitions |
| Phase 29 | `cmd_id` idempotency key | Maps to `trace_id` in DB |
| Phase 29 | Order queue in Redis List | PENDING state storage |

## Requirements Detail

### TRADE-01: Order state machine tracking
- [ ] Implement 5-state machine (PENDING, SENT, FILLED, CLOSED, FAILED)
- [ ] Validate transitions before state change
- [ ] Store state in DB with timestamps
- [ ] Query current state by trace_id or ticket

### TRADE-02: Trade records in TimescaleDB
- [ ] Create `aureus_trades` hypertable
- [ ] DB writer consumes `aureus:stream:*:orders`
- [ ] Upsert with `ON CONFLICT (trace_id)`
- [ ] JSONB payload merge for incremental updates

### TRADE-05: Magic number filter
- [ ] Query bot trades: `magic_number IN (SELECT magic_number FROM aureus_strategy_templates)`
- [ ] Query manual trades: `magic_number NOT IN (...)`
- [ ] Index on `magic_number` column for performance

## Success Criteria (Updated)

1. ✅ Order state machine tracking hoạt động (5 states, validated transitions)
2. ✅ Trade records lưu vào TimescaleDB via DB writer buffer
3. ✅ Magic number filter phân biệt bot vs manual trades qua SQL queries
4. ✅ DB schema: trace_id, ticket, symbol, direction, entry_price, sl, tp, volume, status, profit, timestamps
5. ✅ Idempotent writes via `ON CONFLICT (trace_id) DO UPDATE`
6. ✅ JSONB payload lưu full event history cho debugging

---
*Context created: 2026-04-06*
*Ready for planning*
