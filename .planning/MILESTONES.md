# Milestones

## v1.5 Signal Delivery & Trade Management (Shipped: 2026-04-21)

**Phases completed:** 30 phases, 53 plans, 70 tasks

**Key accomplishments:**

- One-liner:
- Phase:
- Extended AureusProvider.mq5 from unidirectional market data streamer to bidirectional order execution engine with ACK/NACK protocol and automatic position close detection
- Phase:
- MT5 order execution microservice that converts STRATEGY_MATCH events into OPEN_ORDER commands with validation, deduplication, persistent queuing, and selective retry logic
- Phase:
- One-liner:
- One-liner:
- 1. [Rule 3 - Blocking] Fixed redis import aliasing conflict
- Status:
- One-liner:
- Status:
- Status:
- Status:
- One-liner:
- Status:
- Status:
- Status:
- Status:
- Status:
- Files modified (17):
- Files created (2):
- Files modified (2):
- Plan:
- Giảm default RR ratio fallback từ 2.0 xuống 1.5 trong simulated_orders.py, đảm bảo consistency với 16 seed strategies đã có value=1.5
- One-liner:
- Đã khóa contract helper MTF cho candle color/last-closed/BB bằng bộ test pass đầy đủ theo D-01..D-10 trong phạm vi plan 01.
- Cơ chế runtime safety mode cho structure parity đã được bổ sung cùng bộ contract test để đảm bảo fallback an toàn khi old/new mismatch.
- Đã triển khai tối ưu A-first cho StructureSignal và bổ sung replay regression gate để khóa cả parity lẫn mục tiêu hiệu năng giảm tối thiểu 40%.
- Runtime per-symbol worker queue cho signal engine được khóa bằng TDD contracts về isolation đa symbol, FIFO strict và out-of-order drop+ack.
- Strategy executor được khóa consistency snapshot cùng candle và idempotency trace_id strict để ngăn trigger/order sai khi replay hoặc payload lệch thời điểm.
- Per-symbol breaker/backlog/SLO guards with staged shadow→canary→full rollout and isolated fallback rollback per violating symbol.
- Live signal engine đã route candle vào PerSymbolWorkerRuntime queue, áp chính sách FIFO/drop trong worker path, và wire health/rollout hooks theo từng symbol trong runtime xử lý thực tế.
- Strategy executor nay đã wire health/rollout per-symbol end-to-end với enforcement mode thực tế, giữ nguyên snapshot gate + trace dedupe invariants khi chuyển mode runtime.
- Deterministic strategy seed synchronization with rollback-friendly is_active reconciliation and runtime sync-before-reload ordering.
- Bổ sung bộ công cụ dry-run/rollback và regression tests để rollout strategy seed sync có thể preview, apply, và rollback an toàn theo command chuẩn.
- Khóa transaction boundary cho dry-run seed sync bằng single-connection contract và hoàn tất registry PH46-01..PH46-05 để verifier traceability pass.
- Backfill hoàn chỉnh chứng cứ requirement-level cho NOTIF/STRAT/ORDER bằng 3 artifact verification độc lập, đủ để audit truy vết trực tiếp thay vì dựa summary-only.
- Đồng bộ closure trạng thái requirement phase 47 bằng evidence VERIFICATION thực tế, đồng thời chuẩn hóa audit baseline để tách rõ passed và human_needed cho các gate MT5 runtime.
- Chuẩn hóa contract API performance với filter semantics thống nhất, lỗi 4xx có cấu trúc, và deterministic pagination/order để dashboard đọc dữ liệu nhất quán giữa metrics, trades, equity.
- Performance page `/performance` đã được nối đúng contract API phase 48 với test contract success/error và cơ chế hiển thị lỗi invalid-filter rõ ràng, không rơi vào render số liệu sai.
- Đồng bộ filter semantics cho equity runtime path và chuẩn hóa web error parsing theo backend envelope thật để đóng trực tiếp PERF-06/07/08.
- ORDER_OPEN consume path đã được khóa contract-first với reason code deterministic, hỗ trợ alias quantity->qty không false reject, và giữ strict idempotency cho duplicate trace_id.
- Execution client poll runtime chuyển sang discover multi-stream thực tế theo whitelist và khóa reject mismatch symbol giữa stream/payload bằng reason code ổn định.
- Bridge mapper đã canonical hóa quantity với alias qty và lifecycle report giữ được strategy/correlation lineage xuyên pending-intent merge cho multi-symbol execution path.

---

## v1.4 TradingAgents Market Data Integration (Shipped: 2026-04-05)

**Phases completed:** 7 phases, 9 plans, 0 tasks

**Key accomplishments:**

- Validated compatibility of TradingAgents data feeds in isolated WSL environment to establish integration feasibility.
- Extracted legacy signal behavior into a robust Provider Abstraction Interface with canonical payload consistency.
- Implemented a resilience-first TradingAgents Adapter with cache TTL and robust exception backoff.
- Integrated a shadow-mode Live Engine pulse flow that allows background AI processing without interrupting primary Redis routines.
- Introduced a CircuitBreaker Gate utility with TimescaleDB asynchronous drift telemetry offloading to ensure safe rollout fallbacks.

### Known Gaps (User approved Proceed anyway)

Milestone was closed with incomplete requirements:

- `TEST-01`, `TEST-02`, `TEST-03`, `TEST-04` (Verification and automated tests pending)

---

## v1.3 Backtesting & Measurement Engine (Shipped: 2026-04-03)

**Phases completed:** 14 phases, 18 plans, 3 tasks

**Key accomplishments:**

- Stabilized sweep lifecycle verification and confirmed canonical event policy without additional runtime drift.
- Completed no-entry diagnosis map for strategy pipeline checkpoints A→D with prioritized failure ladder.
- Standardized phase artifacts for semantic `signal_history` and contract-reconciliation tracks (context/research/validation/plan/summary).
- Preserved reopened execution context for Phase 15.10 with verified quick regression baseline (`19 passed`).

### Known Gaps (User approved Proceed anyway)

Milestone was closed with incomplete requirements and active execution still in progress. Major unmet areas at close time:

- `STRATQA-01→05` (strategy QA baseline not fully delivered)
- `SCHEMA-01→04` (schema/data-loader not started)
- `NAUTILUS-01→06`, `PARITY-01→03` (core Nautilus integration pending)
- `METRIC-01→08`, `QUALITY-01`, `MEASURE-01→03` (metrics/persistence pending)
- `UI-01→08`, `API-01→06`, `GRAFANA-01→03`, `LIVE-01→03`, `RECOV-01→03` (delivery layers pending)

---
