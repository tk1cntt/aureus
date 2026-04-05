# Requirements: Aureus

**Defined:** 2026-04-05
**Core Value:** Validate strategy behavior through deterministic, reproducible evidence — then deliver actionable signals to production trading.

## v1.5 Requirements

Requirements for Signal Delivery & Trade Management milestone. Each maps to roadmap phases.

### Telegram Notification (NOTIF)

- [ ] **NOTIF-01**: Signal engine publishes signal events qua Redis pub/sub khi có signal mới
- [ ] **NOTIF-02**: aureus-notifier service nhận signal events và gửi lên Telegram
- [ ] **NOTIF-03**: Cấu hình filter signal (chọn signal nào được phép gửi Telegram)
- [ ] **NOTIF-04**: Gửi strategy match alert lên Telegram khi strategy khớp (symbol, direction, entry, SL/TP)
- [ ] **NOTIF-05**: Rate limiting và error recovery cho Telegram API (retry + queue)
- [ ] **NOTIF-06**: Hỗ trợ gửi nhiều chat/channel

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

- [ ] **TRADE-01**: Order state machine tracking (pending → sent → filled → closed)
- [ ] **TRADE-02**: Lưu trade records vào PostgreSQL/TimescaleDB
- [ ] **TRADE-03**: MT5 history push events (real-time order close notification)
- [ ] **TRADE-04**: MT5 history poll reconciliation (fallback mỗi 30-60s)
- [ ] **TRADE-05**: Magic number filter phân biệt bot orders vs manual trades

### Performance Dashboard (PERF)

- [ ] **PERF-01**: API endpoint trả danh sách trades với entry/exit details
- [ ] **PERF-02**: Tính toán Win rate
- [ ] **PERF-03**: Tính toán Profit factor
- [ ] **PERF-04**: Tính toán Max drawdown
- [ ] **PERF-05**: Tính toán Average R:R (Risk-Reward ratio)
- [ ] **PERF-06**: Equity curve chart
- [ ] **PERF-07**: Filter theo symbol, strategy, timeframe
- [ ] **PERF-08**: Trang trade history trên aureus-dashboard

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
| NOTIF-02 | Phase 27 | Pending |
| NOTIF-03 | Phase 27 | Pending |
| NOTIF-04 | Phase 27 | Pending |
| NOTIF-05 | Phase 27 | Pending |
| NOTIF-06 | Phase 27 | Pending |
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
| TRADE-01 | Phase 30 | Pending |
| TRADE-02 | Phase 30 | Pending |
| TRADE-03 | Phase 31 | Pending |
| TRADE-04 | Phase 31 | Pending |
| TRADE-05 | Phase 30 | Pending |
| PERF-01 | Phase 32 | Pending |
| PERF-02 | Phase 32 | Pending |
| PERF-03 | Phase 32 | Pending |
| PERF-04 | Phase 32 | Pending |
| PERF-05 | Phase 32 | Pending |
| PERF-06 | Phase 32 | Pending |
| PERF-07 | Phase 32 | Pending |
| PERF-08 | Phase 33 | Pending |

**Coverage:**
- v1.5 requirements: 30 total
- Mapped to phases: 30
- Unmapped: 0 ✓

---
*Requirements defined: 2026-04-05*
*Last updated: 2026-04-05 after initial definition*
