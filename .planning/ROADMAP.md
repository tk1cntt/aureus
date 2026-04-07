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
| 28 | AureusProvider.mq5 Bidirectional Extension | ORDER-04→06 | PLANNED |
| 29 | MT5 Order Execution Service | ORDER-01→03, ORDER-07 | PLANNED |
| 30 | Trade State Management | TRADE-01→02, TRADE-05 | 1/1 Complete 2026-04-06 |
| 31 | MT5 History Sync | TRADE-03→04 | PLANNED |
| 32 | Trade Performance API | PERF-01→07 | 1 plan |
| 33 | Performance Dashboard UI | PERF-08 | 1 plan |

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
**Goal:** Mở rộng MT5 EA để nhận order commands từ Aureus và push order events ngược lại.

**Success Criteria:**
1. EA nhận và parse order commands (OPEN_ORDER, CLOSE_ORDER) qua TCP
2. EA execute OrderSend() cho market và pending orders
3. EA push order events (ORDER_OPENED, ORDER_CLOSED, ORDER_FAILED) về server
4. ACK/NACK protocol hoạt động cho mỗi command
5. Heartbeat và reconnect logic vẫn hoạt động bình thường

---

## Phase 29: MT5 Order Execution Service

**Requirements:** ORDER-01, ORDER-02, ORDER-03, ORDER-07
**Goal:** Xây dựng aureus-trader service nhận strategy matches và gửi orders xuống MT5.

**Success Criteria:**
1. Service aureus-trader chạy trong Docker, subscribe Redis strategy:matches channel
2. Tạo và gửi market order xuống MT5 qua TCP
3. Tạo và gửi pending order (limit/stop) xuống MT5 qua TCP
4. Idempotency key chống duplicate execution
5. Order queue persist pending orders khi MT5 disconnect

---

## Phase 30: Trade State Management

**Requirements:** TRADE-01, TRADE-02, TRADE-05
**Goal:** Quản lý vòng đời order với state machine và persistent storage.

**Plans:** 1/1 plans complete

**Plans:**
- [x] 30-01-PLAN.md — Trade state management: aureus_trades hypertable, 5-state machine, order_buffer, magic number filters

**Success Criteria:**
1. Order state machine tracking (pending → sent → filled → closed) hoạt động
2. Trade records lưu vào PostgreSQL/TimescaleDB
3. Magic number filter phân biệt bot vs manual trades
4. DB schema bao gồm: ticket, symbol, direction, entry_price, sl, tp, lot, status, profit, timestamps

---

## Phase 31: MT5 History Sync

**Requirements:** TRADE-03, TRADE-04
**Goal:** Hybrid sync: push events real-time + poll reconciliation fallback.

**Plans:** 1 plan

**Plans:**
- [ ] 31-01-PLAN.md — MT5 history sync: XPENDING recovery, REQUEST_TRADE_HISTORY EA command, reconciliation loop, RECONCILED status, audit logging

**Success Criteria:**
1. Push events từ MT5 EA cập nhật trade records real-time
2. Poll reconciliation chạy mỗi 30s (configurable), phát hiện và fill gaps
3. Không mất trade data dù có disconnect hay EA restart
4. Reconciliation log ghi nhận mọi discrepancy được sửa

---

## Phase 32: Trade Performance API

**Requirements:** PERF-01, PERF-02, PERF-03, PERF-04, PERF-05, PERF-06, PERF-07
**Goal:** API endpoints tính toán và trả về performance metrics.

**Plans:** 1 plan

**Plans:**
- [ ] 32-01-PLAN.md — Performance API: connection pooling, /trades (pagination), /metrics (SQL+Python), /equity-curve, Redis cache

**Success Criteria:**
1. API `/api/v1/performance/trades` trả danh sách trades với pagination và filtering
2. Win rate, Profit factor, Max drawdown, Average R:R, Sharpe ratio tính chính xác
3. Equity curve data trả về time series từ `aureus_account_snapshots` với fallback `aureus_trades`
4. Filter hoạt động: symbol, strategy_id, date range, status
5. API response time < 500ms cho dataset up to 10k trades (pooling + caching)
6. Connection pooling giảm connection overhead
7. Redis cache cho metrics endpoints với 60s TTL

---

## Phase 33: Performance Dashboard UI

**Requirements:** PERF-08
**Goal:** Trang web thống kê performance tích hợp vào aureus-dashboard.

**Plans:** 1 plan

**Plans:**
- [ ] 33-01-PLAN.md — Performance Dashboard UI: /performance page, MetricCard, FilterBar, EquityChart (lightweight-charts), PerformanceTable, URL params filtering

**Success Criteria:**
1. Trang `/performance` hiển thị với đầy đủ 4 sections (FilterBar → MetricCards → EquityChart → TradeTable)
2. 6 metric cards hiển thị data từ API (Win Rate, Net PnL, Profit Factor, Max DD, Avg R:R, Sharpe)
3. Equity curve chart render bằng lightweight-charts v5.1.0 AreaSeries
4. Filters hoạt động: symbol, strategy, date range (URL search params)
5. Trade table pagination 20 rows/page
6. Responsive design: 3-col → 2-col → 1-col

### Phase 34: Fix SL TP calculation decimals and MT5 comment strategy name

**Goal:** Fix MT5 EA hardcoded stops and volume issues, add dynamic multiplier parsing for exact broker precision (with future Digits sync backlog).
**Requirements**: N/A
**Status:** ✅ DONE

Plans:
- [x] 34-01-PLAN.md — Executed via direct implementation by AI

## Phase 35: MT5 Order Status Reporter

**Goal:** Gửi thông tin order MT5 hiện tại lên Telegram mỗi phút qua bot. Bao gồm: (1) order đang chạy (open positions) và (2) order đã close trong vòng 1 phút gần nhất (closed history).
**Requirements**: TBD
**Depends on:** Phase 28, Phase 29

**Success Criteria:**
1. Mỗi 1 phút tự động gửi danh sách open positions lên Telegram
2. Nếu trong vòng 1 phút có order vừa close → gửi thông tin order đó (profit/loss, thời gian giữ, entry/exit price)
3. Sử dụng bot token `8650116511:AAE25Gqc9WSVuZ53qrKp_l6b81_TTOVrjFk`
4. Format message rõ ràng, dễ đọc

Plans:
- [ ] TBD (run /gsd-plan-phase 35 to break down)

## Phase 36: Fix BUY/SELL direction from strategy settings not name

**Goal:** Xử lý vào lệnh BUY/SELL dựa trên thông tin setting của Strategy chứ không phải dựa trên tên BULL hay BEAR.
**Requirements**: TBD
**Depends on:** Phase 35
**Plans:** 0 plans

Plans:
- [ ] TBD (run /gsd-discuss-phase 36 to break down)

---

## Next Up

**Phase 28: AureusProvider.mq5 Bidirectional Extension** — mở rộng MT5 EA để nhận order commands.

`/gsd-discuss-phase 28`

<sub>`/clear` first → fresh context window</sub>

## Backlog

### Phase 999.1: Sync MT5 Symbol Metadata Digits (BACKLOG)

**Goal:** Fetch real `SymbolInfoInteger(SYMBOL_DIGITS)` and `SYMBOL_POINT` dynamically from the MT5 broker when initializing the connection, sending it to the backend so the signal engine uses 100% accurate point-size multipliers instead of hardcoded Python fallbacks per symbol.
**Requirements:** TBD
**Plans:** 0 plans

Plans:
- [ ] TBD (promote with /gsd-review-backlog when ready)
