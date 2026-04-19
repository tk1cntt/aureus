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
- [x] **PH45-04**: Strategy executor chỉ xử lý khi snapshot cùng candle (strict consistency)
- [x] **PH45-05**: Idempotency strict theo `trace_id` cho `symbol + strategy + origin_timestamp`
- [x] **PH45-06**: Circuit-breaker + backlog threshold hoạt động độc lập theo từng symbol
- [x] **PH45-07**: Rollout Shadow -> Canary -> Full với auto-rollback theo SLO per-symbol

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

### Phase 46: Strategy Seed Sync (PH46)

- [x] **PH46-01**: Seed chiến lược từ source code được đồng bộ deterministic vào `aureus_strategy_templates` bằng upsert theo `name`
- [x] **PH46-02**: Assignment `symbol↔strategy` reconcile theo `is_active` (không delete cứng) để rollback nhanh
- [x] **PH46-03**: Runtime startup/reload luôn sync trước khi load strategy active-only
- [x] **PH46-04**: Dry-run seed sync chạy trong cùng transaction boundary và không persist mutation sau rollback
- [x] **PH46-05**: Có rollback script + runbook vận hành để khôi phục trạng thái `is_active` từ snapshot

### PH45 Gap-Closure Architecture Decision Record (2026-04-18)

**Mục tiêu:** đóng 3 gap runtime đã xác nhận ở `45-VERIFICATION.md`:
1) `PerSymbolWorkerRuntime` chưa nằm trên production path của `run_signal_engine`
2) FIFO/drop policy chưa là enforcement path runtime thật
3) health/rollout chưa wire end-to-end cho cả signal + strategy

**Bước 1 — Neutral listing (phương án kỹ thuật):**
- **PA-A: Main-loop orchestration + per-symbol lock (incremental patch)**
  - Giữ luồng xử lý chính trong `live_engine.run_signal_engine`
  - Duy trì lock/guard ở main loop, chỉ gọi helper từ `symbol_runtime`
  - Không đổi mạnh đường chạy strategy executor
- **PA-B: PerSymbolWorkerRuntime là execution backbone (in-process actor per symbol)**
  - `live_engine` chỉ route stream entry -> `PerSymbolWorkerRuntime.enqueue(...)`
  - FIFO/drop enforcement đặt 1 nguồn sự thật trong worker runtime
  - `SymbolRuntimeHealthManager` resolve mode per-symbol cho signal và strategy path
- **PA-C: Tách thành runtime service riêng (out-of-process worker pool / message bus)**
  - Tách processing runtime khỏi `live_engine` sang service độc lập
  - Đồng bộ bằng Redis/Kafka/NATS event contracts
  - Health/rollout điều phối qua control-plane riêng

**Bước 2 — Attribute mapping:**
- **Mạnh nhất về hiệu năng/throughput ngắn hạn:** PA-B (isolation per symbol, giảm contention trong process hiện tại, không tốn overhead network hop như PA-C)
- **Mạnh nhất về bảo trì/khả năng mở rộng dài hạn:** PA-C (service boundary rõ, scale độc lập)
- **Mạnh nhất về tốc độ triển khai an toàn theo codebase hiện tại:** PA-B

**Trade-off chính:**
- Chọn **PA-B thay PA-A**: mất lợi thế thay đổi siêu nhỏ của PA-A, nhưng đổi lại có enforcement path rõ ràng và giảm dual-path drift.
- Chọn **PA-B thay PA-C**: mất lợi thế scale độc lập theo service của PA-C, nhưng tránh migration cost lớn, tránh đổi contract/liên dịch vụ trong scope phase 45.
- Chọn **PA-A thay PA-B**: giữ patch nhỏ nhưng rủi ro cao về policy split-brain (main-loop guard vs worker guard), khó chứng minh runtime truth.

**Bước 3 — Contextual recommendation (khuyến nghị chính thức):**
- **Chọn PA-B làm chuẩn thực thi cho Phase 45 gap-closure.**
- Context áp dụng:
  - Code hiện hữu đã có `PerSymbolWorkerRuntime` + test contracts (45-01..45-03) nhưng chưa wire production
  - Constraint phase: phải đóng gap nhanh, giữ compatibility, không mở rộng scope sang redesign service
  - Yêu cầu ổn định: rollback/hysteresis per-symbol phải có hiệu lực runtime thật, không chỉ artifact-level
- Vì vậy PA-B cho tỷ lệ **đóng gap/chi phí thay đổi** tối ưu nhất trong mốc hiện tại.

**Bước 4 — Adversarial mode (Devil’s Advocate cho PA-B):**
- **Fail scenario 1:** `live_engine` còn giữ đường xử lý cũ song song với `enqueue`, dẫn đến dual-path execution và duplicate processing.
- **Fail scenario 2:** health manager chỉ được cập nhật ở signal path nhưng strategy path không consume mode, gây rollback “nửa vời”.
- **Fail scenario 3:** ack/exception flow trong worker không cân bằng (`task_done`, retry, xack) tạo backlog ảo hoặc deadlock queue accounting.
- **Rủi ro kiến trúc dễ bị bỏ qua:**
  - Split-brain state giữa `state.tracking_vars` và worker-local state theo symbol.
  - Độ trễ mode transition (shadow/canary/full/fallback_serial) không đồng bộ giữa signal và strategy loops.
  - Test pass ở unit-level nhưng không chứng minh production call path đã đi qua worker runtime thật.

**Tiêu chí bắt buộc để chấp nhận closure 3 gaps (execution gate):**
- `run_signal_engine` có instantiate + route qua `PerSymbolWorkerRuntime` (không còn nhánh xử lý trực tiếp gây dual-path)
- Out-of-order guard `ts_unix <= last_executed_candle_t` được enforce từ worker runtime trên production path
- Strategy executor dùng thật `SymbolRuntimeHealthManager` (không còn unused import), mode enforcement chạy per-symbol
- Rollback per-symbol được chứng minh cross-path (signal + strategy), không có global rollback
- Baseline test bundle pass:
  - `test_per_symbol_worker_runtime.py`
  - `test_out_of_order_drop_policy.py`
  - `test_strategy_trigger_lifecycle.py`
  - `unittest/test_orders_events.py`
  - `test_symbol_slo_rollback.py`
  - `test_live_engine_shadow_mode.py`
  - `test_multi_symbol.py`

**PH45 traceability source:** `.planning/phases/45-h-tr-x-ly-song-song-signal-strategy-cho-nhi-u-symbol-m-t-/45-CONTEXT.md`

**Status:** Planned (gap-closure replanned 45-04/45-05)

**Last updated:** 2026-04-18 (architecture review + gap-closure decision)

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
| PH46-01 | Phase 46 | Complete |
| PH46-02 | Phase 46 | Complete |
| PH46-03 | Phase 46 | Complete |
| PH46-04 | Phase 46 | Complete |
| PH46-05 | Phase 46 | Complete |

**Coverage:**
- v1.5 requirements: 37 total
- Mapped to phases: 37
- Unmapped: 0 ✓

---
*Requirements defined: 2026-04-05*
*Last updated: 2026-04-18 after Phase 45 planning review*
