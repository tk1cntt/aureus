# ROADMAP

## Archived Milestones

| Version | Name | Phases | Status |
|---------|------|--------|--------|
| v1.1 | Signal Optimization | 07-13 | ✅ Shipped 2026-03-22 |
| v1.2 | Strategy Sequence Engine | 14-15 | ✅ Shipped 2026-03-22 |
| v1.3 | Backtesting & Measurement Engine | 15.5-20 | ✅ Closed 2026-04-03 (known gaps logged) |
| v1.4 | TradingAgents Market Data Integration | 21-25 | ✅ Closed 2026-04-05 (known gaps logged) |

---

## Current Milestone: v1.5 Signal Delivery & Trade Management

**Goal:** Xây dựng pipeline hoàn chỉnh từ signal → notification → order execution → result tracking, với dashboard thống kê performance.

**Phases:** 8

| Phase | Name | Requirements | Status |
|---|---|---|---|
| 26 | Signal Event Pipeline & Strategy Contract | NOTIF-01, STRAT-01→04 | ✅ DONE |
| 27 | Telegram Notification Service | NOTIF-02→06 | ✅ DONE |
| 28 | AureusProvider.mq5 Bidirectional Extension | ORDER-04→06 | ✅ DONE |
| 29 | MT5 Order Execution Service | ORDER-01→03, ORDER-07 | ✅ DONE |
| 30 | Trade State Management | TRADE-01→02, TRADE-05 | ✅ DONE 2026-04-06 |
| 31 | MT5 History Sync | TRADE-03→04 | ✅ DONE 2026-04-07 |
| 32 | Trade Performance API | PERF-01→07 | ✅ DONE 2026-04-07 |
| 33 | Performance Dashboard UI | PERF-08 | ✅ DONE 2026-04-07 |
| 35 | MT5 Order Status Reporter | PERF-09 | ✅ DONE 2026-04-07 |
| 36.1 | Fix BUY/SELL Direction from Strategy Settings | — | ✅ DONE 2026-04-08 |
| 37 | Trade Execution Journal (INSERTED) | TBJ-01→05 | Not planned |
| 39 | Fix strategy service crash from unhandled exceptions | — | Not planned |
| 40 | Signal Classification: Indicator + Event-based with Telegram snapshot | SIG-01→04 | Planned |

---

## Phase 26: Signal Event Pipeline & Strategy Contract

**Requirements:** NOTIF-01, STRAT-01, STRAT-02, STRAT-03, STRAT-04
**Goal:** Thiết lập foundation: signal engine publish events qua Redis pub/sub và mở rộng strategy contract với trade parameters.

**Success Criteria:**
1. Signal engine phát signal events lên Redis pub/sub channel khi có signal mới
2. Strategy output chứa entry_type (market/limit/stop), SL, TP, lot_size
3. Existing strategies tiếp tục hoạt động bình thường (backward compatible)
4. Magic number được assign per strategy trong config
5. Unit tests xác nhận contract mới và backward compatibility

---

## Phase 27: Telegram Notification Service

**Requirements:** NOTIF-02, NOTIF-03, NOTIF-04, NOTIF-05, NOTIF-06
**Goal:** Xây dựng aureus-notifier service nhận events từ Redis và gửi thông báo lên Telegram.

**Success Criteria:**
1. ✅ Service aureus-notifier chạy trong Docker, subscribe Redis channels
2. ✅ Signal alerts gửi lên Telegram với format đầy đủ (symbol, signal type, value)
3. ✅ Strategy match alerts gửi với entry details (direction, entry, SL/TP)
4. ✅ Filter config cho phép bật/tắt từng loại signal
5. ✅ Rate limiting hoạt động (1 msg/2s per chat, queue max 100)
6. ✅ Multi-channel support hoạt động

**Implementation:**
- 6 source files + 3 test files (34 tests, all passing)
- `aureus-notifier-dev` service in docker-compose.dev.yml
- HTML-formatted messages with emoji (📊 SIGNAL ALERT, 🎯 STRATEGY MATCH)
- Per-chat rate limiting via asyncio.Queue, exponential backoff retry
- Runtime config reload via Redis pub/sub

---

## Phase 28: AureusProvider.mq5 Bidirectional Extension

**Requirements:** ORDER-04, ORDER-05, ORDER-06
**Status:** ✅ DONE

**Results:**
- EA nhận và parse order commands (OPEN_ORDER, CLOSE_ORDER) qua TCP
- EA execute OrderSend() cho market và pending orders
- EA push order events (ORDER_OPENED, ORDER_CLOSED, ORDER_FAILED) về server
- ACK/NACK protocol hoạt động cho mỗi command
- Heartbeat và reconnect logic vẫn hoạt động bình thường

---

## Phase 29: MT5 Order Execution Service

**Requirements:** ORDER-01, ORDER-02, ORDER-03, ORDER-07
**Status:** ✅ DONE

**Results:**
- Service aureus-trader chạy trong Docker, subscribe Redis strategy:matches channel
- Tạo và gửi market order/pending order xuống MT5 qua TCP
- Idempotency key chống duplicate execution
- Order queue persist pending orders khi MT5 disconnect

---

## Phase 30: Trade State Management

**Requirements:** TRADE-01, TRADE-02, TRADE-05
**Status:** ✅ DONE 2026-04-06

**Plans:**
- [x] 30-01-PLAN.md — Trade state management: aureus_trades hypertable, 6-state machine, order_buffer, magic number filters
- [x] 30-01-SUMMARY.md — 66 tests passed, 3 commits: 2b6b0f6, 428bc20, f21447d

**Results:**
- State machine 6 states: PENDING→SENT→FILLED→CLOSED/FAILED/CANCELLED
- order_buffer trong DB writer với Redis stream consumer
- Magic number filter SQL queries phân biệt bot vs manual trades
- Validation direction BUI/SELL, entry_type MARKET/LIMIT/STOP

---

## Phase 31: MT5 History Sync

**Requirements:** TRADE-03, TRADE-04
**Status:** ✅ DONE 2026-04-07

**Plans:**
- [x] 31-01-PLAN.md — Hybrid sync: XPENDING recovery, REQUEST_TRADE_HISTORY, reconciliation loop
- [x] 31-01-SUMMARY.md — 3 commits: 484e1c0, 000a66d, 98bd363

**Results:**
- REQUEST_TRADE_HISTORY command handler trong MT5 EA
- XPENDING recovery trên startup của DB writer
- Reconciliation loop (configurable interval, default 30s) phát hiện và tự sửa missing trades
- `aureus_reconciliation_log` table cho audit

---

## Phase 32: Trade Performance API

**Requirements:** PERF-01, PERF-02, PERF-03, PERF-04, PERF-05, PERF-06, PERF-07
**Status:** ✅ DONE 2026-04-07

**Results:**
- 3 endpoints: /trades (paginated), /metrics (Redis cache 60s), /equity-curve (Redis cache 30s)
- PostgreSQL connection pooling (asyncpg, min=2, max=10)
- Hybrid metrics: SQL aggregation + numpy (drawdown, sharpe)
- Consistent filtering: symbol, strategy_id, start, end
- Commit: 98781cd

---

## Phase 33: Performance Dashboard UI

**Requirements:** PERF-08
**Status:** ✅ DONE 2026-04-07

**Results:**
- Trang `/performance` với 6 metric cards, FilterBar, EquityChart, PerformanceTable
- lightweight-charts v5.1.0 AreaSeries cho equity curve
- URL search params cho filter state
- 5 component files mới + Sidebar navigation
- TypeScript zero errors, Commit: 4f0633c

---

## Phase 35: MT5 Order Status Reporter

**Goal:** Gửi thông tin order MT5 hiện tại lên Telegram mỗi phút qua bot. Bao gồm open positions và recently closed trades.
**Status:** ✅ DONE 2026-04-07

**Results:**
- REQUEST_POSITIONS command trong MT5 EA
- BuildPositionsJSON() với pips calculation từ SYMBOL_DIGITS
- OrderStatusReporter class trong aureus-notifier
- Polling mỗi 60s, gửi báo cáo open positions + closed trades lên Telegram
- 19 tests pass (9 gateway + 10 notifier)

Plans:
- [x] 35-01-PLAN.md — Executed
- [x] 35-02-PLAN.md — Pips accuracy fix
- [x] 35-VERIFICATION.md — ✅ PASS

---

## Phase 36: Fix BUY/SELL Direction from Strategy Settings (Not Name)

**Goal:** Bỏ fallback direction từ tên strategy, bắt buộc cấu hình rõ ràng trong trade_execution.
**Status:** ✅ DONE 2026-04-08

**Results:**
- TemplateStrategy.__init__ validate direction từ trade_execution (line 39-45)
- Không còn fallback "BEAR"/"BULL" vào tên strategy
- Raise ValueError nếu thiếu hoặc sai direction
- 6 seed strategies đều có direction trong trade_execution
- DB xác nhận 6 rows đều có direction đúng
- 16 tests pass (có 3 tests mới: direction_required, invalid_value, case_insensitive)

Plans:
- [x] 36-01-PLAN.md — Executed

---

## Phase 37: Trade Execution Journal (INSERTED)

**Goal:** Lưu nhật ký thực thi trade từ lúc strategy trigger → order tạo → order close trên MT5. Bảng ghi đủ thông tin để phân tích hiệu quả strategy, lý do vào lệnh, signal active, kết quả PnL.

**Requirements:**
- **TBJ-01:** Bảng `aureus_trade_journal` với schema đầy đủ
- **TBJ-02:** Signal Service ghi entry khi trade plan được generate (strategy, direction, score, active signals, context)
- **TBJ-03:** Trader Service update order_id, position_id, entry_price, entry_time khi MT5 execute
- **TBJ-04:** Gateway/EA update exit_price, exit_time, exit_reason, pnl, duration khi MT5 close
- **TBJ-05:** API endpoint `/api/v1/journal` để query, filter, phân tích

**Schema proposed:**
```sql
CREATE TABLE aureus_trade_journal (
    id SERIAL PRIMARY KEY,
    -- Strategy context
    strategy_name VARCHAR(100),
    strategy_id INT,
    direction VARCHAR(4),
    score NUMERIC,
    -- Entry details
    order_id VARCHAR(50),
    position_id BIGINT,
    entry_price NUMERIC,
    entry_time TIMESTAMPTZ,
    sl NUMERIC,
    tp NUMERIC,
    lot_size NUMERIC,
    -- Exit details
    exit_price NUMERIC,
    exit_time TIMESTAMPTZ,
    exit_reason VARCHAR(50),
    pnl NUMERIC,
    pnl_pips NUMERIC,
    duration_seconds INT,
    -- Signal context
    active_signals JSONB,
    context_filters JSONB,
    magic_number INT,
    comment VARCHAR(255),
    -- Meta
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

**Depends on:** Phase 26 (Signal Contract), Phase 29 (Order Execution), Phase 30 (Trade State)
**All:** ✅ DONE

Plans:
- [ ] 37-01-PLAN.md — Trade journal DB + signal service integration + trader service update + API

### Phase 39: Fix strategy service crash from unhandled exceptions

**Goal:** [Urgent work - to be planned]
**Requirements**: TBD
**Depends on:** Phase 38
**Plans:** 0 plans

Plans:
- [ ] TBD (run /gsd-plan-phase 39 to break down)

### Phase 40: Signal Classification — Indicator vs Event-based với Telegram Snapshot

**Goal:** Phân loại signal thành 2 loại: (1) indicator-based signal (EMA, RSI, v.v.) có giá trị liên tục theo từng nến, (2) event-based signal cần trigger/event mới xảy ra. Khi có event trigger, bổ sung snapshot giá trị của các indicator signal vào thông báo Telegram.

**Requirements:**
- **SIG-01:** Phân loại signal thành indicator vs event-based trong hệ thống
- **SIG-02:** Khi có event trigger, thu thập giá trị hiện tại của tất cả indicator signals
- **SIG-03:** Tích hợp snapshot giá trị indicator vào message Telegram notification
- **SIG-04:** Đảm bảo backward compatible với notification format hiện tại

**Depends on:** Phase 26 (Signal Contract), Phase 27 (Telegram Notification)
**Plans:** 3 plans

Plans:
- [ ] 40-01-PLAN.md — SignalType enum + classify all 15 signal classes (SIG-01)
- [ ] 40-02-PLAN.md — indicator_snapshot.py helper + tests (SIG-02)
- [ ] 40-03-PLAN.md — live_engine hook + Telegram formatter + tests (SIG-03, SIG-04)

---

## Next Up

**Phase 36.1** — Trade Execution Journal *(urgent insertion)*

<sub>`/clear` first → fresh context window</sub>

## Backlog

### Phase 38: Fix DB writer order payload parsing for wrapped data to unblock trade journal FK (INSERTED)

**Goal:** [Urgent work - to be planned]
**Requirements**: TBD
**Depends on:** Phase 37
**Plans:** 0 plans

Plans:
- [ ] TBD (run /gsd-plan-phase 38 to break down)

### Phase 34: Fix SL TP calculation decimals and MT5 comment strategy name

**Goal:** Sửa lỗi tính toán SL/TP bị sai decimal và thêm tên strategy vào MT5 comment.
**Status:** ✅ DONE 2026-04-07

**Plans:**
- [ ] 34-01-PLAN.md — Fix SL/TP decimal precision and MT5 comment strategy name

---

### Phase 38: Fix DB writer order payload parsing for wrapped data to unblock trade journal FK (INSERTED)

**Goal:** Sửa aureus-db-writer để parse đúng order events dạng wrapped payload (`type` + `data`) từ Redis stream, đảm bảo ghi dữ liệu trade nhất quán cho trade journal FK.
**Requirements**: TBD
**Depends on:** Phase 37
**Plans:** 0 plans

Plans:
- [ ] TBD (run /gsd-plan-phase 38 to break down)

### Phase 999.1: Sync MT5 Symbol Metadata Digits (BACKLOG)

**Goal:** Fetch real `SymbolInfoInteger(SYMBOL_DIGITS)` and `SYMBOL_POINT` dynamically from the MT5 broker when initializing the connection, sending it to the backend so the signal engine uses 100% accurate point-size multipliers instead of hardcoded Python fallbacks per symbol.
**Requirements:** TBD
**Plans:** 0 plans

Plans:
- [ ] TBD (promote with /gsd-review-backlog when ready)
