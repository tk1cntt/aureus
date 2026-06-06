# ROADMAP

## Archived Milestones

| Version | Name | Phases | Status |
|---------|------|--------|--------|
| v1.1 | Signal Optimization | 07-13 | ✅ Shipped 2026-03-22 |
| v1.2 | Strategy Sequence Engine | 14-15 | ✅ Shipped 2026-03-22 |
| v1.3 | Backtesting & Measurement Engine | 15.5-20 | ✅ Closed 2026-04-03 (known gaps logged) |
| v1.4 | TradingAgents Market Data Integration | 21-25 | ✅ Closed 2026-04-05 (known gaps logged) |
| v1.5 | Signal Delivery & Trade Management | 26-53 | ✅ Shipped 2026-04-21 |

---

## Current Milestone: v1.6 Strategy Evaluation & Insight Delivery

**Goal:** Xây hệ thống đánh giá hiệu quả strategy đa tiêu chí, có scoring framework chuẩn, lưu dữ liệu chuẩn hóa vào DB, hỗ trợ report nhiều chiều và gửi Telegram insight đầy đủ ngữ cảnh.

**Phases:** 5 (planned)

| Phase | Name | Requirements | Status |
|---|---|---|---|
| 54 | Strategy Scoring Framework | SCOR-01→04, ACC-01 | Planned |
| 55 | 7/7 | Complete    | 2026-04-23 |
| 56 | Multi-Dimensional Reporting Engine | RPT-01→05, ACC-03 | Planned |
| 57 | Telegram Insight Delivery | TEL-EVAL-01→04, ACC-02 | Planned |
| 58 | Fix inactive trading strategies | — | Planning |

---

## Phase 54: Strategy Scoring Framework

**Requirements:** SCOR-01, SCOR-02, SCOR-03, SCOR-04, ACC-01  
**Goal:** Chốt scoring framework đa tiêu chí cho strategy và chạy được end-to-end trước các phần mở rộng khác.
**Plans:** 2 plans

Plans:
- [ ] 54-01-PLAN.md — Xây two-stage scoring core (gate + weighted-sum), score versioning immutable và breakdown contract có missing-data policy.
- [ ] 54-02-PLAN.md — Wiring scoring vào strategy executor để tạo per-trade + aggregate output theo strategy/symbol/timeframe và khóa e2e verification.

**Success Criteria:**
1. Có công thức scoring đa tiêu chí rõ ràng (profit, signal quality, timing, volatility/session context).
2. Có hỗ trợ trọng số theo version để tái lập kết quả.
3. Tính được cả per-trade score và aggregate score.
4. Persist được breakdown từng tiêu chí (không chỉ final score).

---

## Phase 55: Evaluation Data Model & Pipeline

**Requirements:** EVAL-01, EVAL-02, EVAL-03, EVAL-04  
**Goal:** Chuẩn hóa schema và pipeline lưu dữ liệu đánh giá strategy vào DB để truy vấn thống kê ổn định.
**Plans:** 7/7 plans complete

> Mở rộng từ 3 lên 6 plans để tách rõ runtime-parity gate (EVAL-RUNTIME-01→04) và storage policy gate SIGNAL-SNAPSHOT-01, tránh false-positive completion khi chỉ pass unit/migration.

Plans:
- [x] 55-01-PLAN.md — Chốt evaluation schema journal-linked và guardrails DB-level (unique/FK/check) cho dữ liệu scoring.
- [x] 55-02-PLAN.md — Wiring ingestion/compute/persist vào trigger ORDER_OPENED để ghi evaluation records đầy đủ và traceable.
- [x] 55-03-PLAN.md — Xây backfill/recompute append-version theo score_version, giữ history và idempotent rerun.
- [x] 55-04-PLAN.md — Khóa runtime schema parity và migration compatibility trên PostgreSQL runtime trước khi sign-off phase.
- [x] 55-05-PLAN.md — Ổn định runtime recompute + sign-off evidence gate (schema/index/latest rows) để loại false completion.
- [x] 55-06-PLAN.md — Tối ưu signal snapshot hybrid storage (full raw JSONB + canonical typed hot columns + retention/archive) và DB E2E proof.

**Success Criteria:**
1. Schema DB chuẩn hóa cho evaluation records được áp dụng.
2. Pipeline compute/persist tạo đầy đủ evaluation record theo từng trade.
3. Có backfill/recompute theo score version, không mất lịch sử cũ.
4. Có guardrails dữ liệu (idempotency, uniqueness, null/constraint checks).

---

## Phase 56: Multi-Dimensional Reporting Engine

**Requirements:** RPT-01, RPT-02, RPT-03, RPT-04, RPT-05, ACC-03  
**Goal:** Cung cấp report engine vừa drill-down per-trade vừa aggregate đa chiều để hỗ trợ quyết định.

**Success Criteria:**
1. Report per-trade hiển thị score breakdown + context đầy đủ.
2. Report aggregate theo strategy/symbol/timeframe.
3. Lọc được theo market session và volatility regime.
4. Hỗ trợ thêm tiêu chí mở rộng mà không phá schema hiện tại.

---

## Phase 57: Telegram Insight Delivery

**Requirements:** TEL-EVAL-01, TEL-EVAL-02, TEL-EVAL-03, TEL-EVAL-04, ACC-02  
**Goal:** Gửi Telegram insight đánh giá chính xác và đủ ngữ cảnh dựa trên dữ liệu chuẩn hóa trong DB.

**Success Criteria:**
1. Telegram per-trade insight có score tổng + breakdown tiêu chí chính.
2. Telegram aggregate insight theo strategy/symbol/timeframe hoạt động định kỳ.
3. Insight có market session + volatility regime + quality/confidence flags.
4. Insight tham chiếu được evaluation record id/version để traceability.

---

## Phase 58: Fix inactive trading strategies

**Goal:** Verify rằng 8 strategies không bao giờ trigger (0 lệnh) có thể emit signals end-to-end trên live runtime. Mỗi strategy phải đi qua đầy đủ pipeline: detector -> signal bridge -> context filter -> sequence matching.
**Plans:** 2 plans

Plans:
- [ ] 58-01-PLAN.md — Verify 6 TPO strategies (TPO_VA_REJECTION_BULL/BEAR, TPO_VA_BREAKOUT_BULL/BEAR, TPO_TREND_PULLBACK_BULL/BEAR) through Stage A-D pipeline via unit/integration tests.
- [ ] 58-02-PLAN.md — Verify FZ_CONT_BULL và FZ_CONT_BEAR strategies qua choch->bos sequence matching, bos_up/bos_down emission, và LIMIT entry type.

**Success Criteria:**
1. 6 TPO strategies: detector -> candidate -> bridge -> context filter -> sequence matching verified via tests.
2. 2 FZ_CONT strategies: bos_up/bos_down emission -> transient -> sequence matching verified via tests.
3. All existing tests pass (no regression).
4. Evidence: signal tag appears in Redis event stream or sequence match occurs.

**Pre-fixed Issues (NOT implementing again):**
- 260602-pvk: `_maybe_emit_tpo_strategy_tags()` already maps tags to candle record events
- 260602-pvk: `tpo_context` handler already added in template.py
- 260602-riq: `bos_up`/`bos_down` already implemented in structure.py
- 260602-riq: BOSUpSignal/BOSDownSignal consumers already registered in factory
