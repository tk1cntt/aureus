# Requirements: Aureus

**Defined:** 2026-04-05
**Core Value:** Validate strategy behavior through deterministic, reproducible evidence — then deliver actionable signals to production trading.

## v1.5 Requirements

Requirements for Signal Delivery & Trade Management milestone. Each maps to roadmap phases.

### Telegram Notification (NOTIF)

- [ ] **NOTIF-01**: Signal engine publishes signal events qua Redis pub/sub khi có signal mới
- [x] **NOTIF-02**: aureus-notifier service nhận signal events và gửi lên Telegram
- [x] **NOTIF-03**: Cấu hình filter signal (chọn signal nào được phép gửi Telegram)
- [x] **NOTIF-04**: Gửi strategy match alert lên Telegram khi strategy khớp (symbol, direction, entry, SL/TP)
- [x] **NOTIF-05**: Rate limiting và error recovery cho Telegram API (retry + queue)
- [x] **NOTIF-06**: Hỗ trợ gửi nhiều chat/channel

### Strategy Enhancement (STRAT)

- [ ] **STRAT-01**: Strategy contract bổ sung entry_type (market/limit/stop)
- [ ] **STRAT-02**: Strategy output chứa SL/TP values
- [ ] **STRAT-03**: Strategy output chứa lot size / risk percentage
- [ ] **STRAT-04**: Magic number per strategy cho MT5 order tracking

### MT5 Order Execution (ORDER)

- [ ] **ORDER-01**: aureus-trader service nhận strategy match từ Redis pub/sub
- [ ] **ORDER-02**: Tạo và gửi market order xuống MT5 qua TCP
- [ ] **ORDER-03**: Tạo và gửi pending order (limit/stop) xuống MT5 qua TCP
- [ ] **ORDER-04**: Mở rộng AureusProvider.mq5 nhận order commands và execute OrderSend()
- [ ] **ORDER-05**: AureusProvider.mq5 push order events (opened/closed/failed) về aureus-trader
- [ ] **ORDER-06**: Order acknowledgement protocol (ACK/NACK với ticket number)
- [ ] **ORDER-07**: Idempotency key để chống duplicate order execution

### Trade Management (TRADE)

- [x] **TRADE-01**: Order state machine tracking (pending → sent → filled → closed)
- [x] **TRADE-02**: Lưu trade records vào PostgreSQL/TimescaleDB
- [ ] **TRADE-03**: MT5 history push events (real-time order close notification)
- [ ] **TRADE-04**: MT5 history poll reconciliation (fallback mỗi 30-60s)
- [x] **TRADE-05**: Magic number filter phân biệt bot orders vs manual trades

### Performance Dashboard (PERF)

- [ ] **PERF-01**: API endpoint trả danh sách trades với entry/exit details
- [ ] **PERF-02**: Tính toán Win rate
- [ ] **PERF-03**: Tính toán Profit factor
- [ ] **PERF-04**: Tính toán Max drawdown
- [ ] **PERF-05**: Tính toán Average R:R (Risk-Reward ratio)
- [ ] **PERF-06**: Equity curve chart
- [ ] **PERF-07**: Filter theo symbol, strategy, timeframe
- [ ] **PERF-08**: Trang trade history trên aureus-dashboard

### Runtime Parallelization (PH45)

- [x] **PH45-01**: Signal engine hỗ trợ per-symbol worker (1 worker/symbol active)
- [x] **PH45-02**: FIFO strict theo candle `t` trong từng symbol
- [x] **PH45-03**: Out-of-order candle bị drop theo policy `ts_unix <= last_executed_candle_t`
- [ ] **PH45-04**: Strategy executor chỉ xử lý khi snapshot cùng candle (strict consistency)
- [ ] **PH45-05**: Idempotency strict theo `trace_id` cho `symbol + strategy + origin_timestamp`
- [ ] **PH45-06**: Circuit-breaker + backlog threshold hoạt động độc lập theo từng symbol
- [ ] **PH45-07**: Rollout Shadow -> Canary -> Full với auto-rollback theo SLO per-symbol

**PH45 verification baseline (execution gate):**
- `python3 -m pytest /d/Aureus/services/aureus-signal/tests/test_per_symbol_worker_runtime.py -q`
- `python3 -m pytest /d/Aureus/services/aureus-signal/tests/test_out_of_order_drop_policy.py -q`
- `python3 -m pytest /d/Aureus/services/aureus-signal/tests/test_strategy_trigger_lifecycle.py -q`
- `python3 -m pytest /d/Aureus/services/aureus-signal/unittest/test_orders_events.py -q`
- `python3 -m pytest /d/Aureus/services/aureus-signal/tests/test_symbol_slo_rollback.py -q`
- `python3 -m pytest /d/Aureus/services/aureus-signal/tests/test_live_engine_shadow_mode.py -q`
- `python3 -m pytest /d/Aureus/services/aureus-signal/tests/test_multi_symbol.py -q`

**PH45 SLO mặc định để rollback tự động (canary/full):**
- `lag_p95_ms > 2000` liên tiếp 3 phút, hoặc
- `queue_depth > 200` liên tiếp 3 phút, hoặc
- `error_rate > 5%` liên tiếp 3 phút.

Thoát fallback khi cả 3 chỉ số dưới 50% ngưỡng trong 5 phút liên tiếp (hysteresis).
**Lưu ý:** ngưỡng này là baseline vận hành cho Phase 45, có thể tinh chỉnh bằng dữ liệu thực tế sau canary nhưng phải cập nhật lại mục này trước khi promote full.

**PH45 architecture guardrails (không được vi phạm):**
- Không dùng global queue/global lock làm serialize toàn bộ symbols.
- Không dùng reorder window cho out-of-order candle trong phase này.
- Không rollback global khi một symbol vi phạm SLO.
- Không mở rộng scope sang cleanup logic tín hiệu ngoài D-01..D-12.

**PH45 traceability source:** `.planning/phases/45-h-tr-x-ly-song-song-signal-strategy-cho-nhi-u-symbol-m-t-/45-CONTEXT.md`

**Status:** Planned (chưa execute)

**Last updated:** 2026-04-18

---

## Future Requirements

### Performance Analytics Extended

- **PERF-F01**: Sharpe ratio calculation
- **PERF-F02**: Daily/weekly/monthly P&L breakdown
- **PERF-F03**: Export trades to CSV

### Order Management Extended

- **ORDER-F01**: Order modification (update SL/TP after entry)
- **ORDER-F02**: Partial close support

## Out of Scope

| Feature | Reason |
|---------|--------|
| Mobile app push notifications | Telegram đủ cho v1, mobile app là scope riêng |
| MetaTrader5 Python lib integration | Không phù hợp kiến trúc Docker — dùng TCP socket |
| Automated lot sizing based on Kelly criterion | Phức tạp, defer to future |
| Multi-broker support | Chỉ hỗ trợ 1 MT5 terminal cho v1 |
| Web-based order placement | Chỉ auto-execute từ strategy, không manual order qua web |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| NOTIF-01 | Phase 26 | Pending |
| NOTIF-02 | Phase 27 | ✅ Done |
| NOTIF-03 | Phase 27 | ✅ Done |
| NOTIF-04 | Phase 27 | ✅ Done |
| NOTIF-05 | Phase 27 | ✅ Done |
| NOTIF-06 | Phase 27 | ✅ Done |
| STRAT-01 | Phase 26 | Pending |
| STRAT-02 | Phase 26 | Pending |
| STRAT-03 | Phase 26 | Pending |
| STRAT-04 | Phase 26 | Pending |
| ORDER-01 | Phase 29 | Pending |
| ORDER-02 | Phase 29 | Pending |
| ORDER-03 | Phase 29 | Pending |
| ORDER-04 | Phase 28 | Pending |
| ORDER-05 | Phase 28 | Pending |
| ORDER-06 | Phase 28 | Pending |
| ORDER-07 | Phase 29 | Pending |
| TRADE-01 | Phase 30 | Complete |
| TRADE-02 | Phase 30 | Complete |
| TRADE-03 | Phase 31 | Pending |
| TRADE-04 | Phase 31 | Pending |
| TRADE-05 | Phase 30 | Complete |
| PERF-01 | Phase 32 | Pending |
| PERF-02 | Phase 32 | Pending |
| PERF-03 | Phase 32 | Pending |
| PERF-04 | Phase 32 | Pending |
| PERF-05 | Phase 32 | Pending |
| PERF-06 | Phase 32 | Pending |
| PERF-07 | Phase 32 | Pending |
| PERF-08 | Phase 33 | Pending |
| PH45-01 | Phase 45 | Planned |
| PH45-02 | Phase 45 | Planned |
| PH45-03 | Phase 45 | Planned |
| PH45-04 | Phase 45 | Planned |
| PH45-05 | Phase 45 | Planned |
| PH45-06 | Phase 45 | Planned |
| PH45-07 | Phase 45 | Planned |

**Coverage:**
- v1.5 requirements: 37 total
- Mapped to phases: 37
- Unmapped: 0 ✓

---
*Requirements defined: 2026-04-05*
*Last updated: 2026-04-18 after Phase 45 planning review*
