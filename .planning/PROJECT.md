# PROJECT

## What This Is
A planning control document for Aureus milestone evolution. It captures shipped outcomes, active scope, and requirement sources used by the GSD workflow.

## Core Value
- Validate strategy behavior through deterministic, reproducible evidence.
- Keep signal/strategy contracts observable and stable before deeper integration.
- Leverage Nautilus execution infrastructure while minimizing custom execution complexity.
- Preserve clear milestone auditability (plans, summaries, and known gaps).

## Current Milestone: v1.6 Strategy Evaluation & Insight Delivery

**Goal:** Nâng cấp hệ thống để đánh giá strategy đa tiêu chí (không chỉ lợi nhuận), lưu đầy đủ dữ liệu ngữ cảnh vào DB, xuất report nhiều chiều và gửi Telegram insight chính xác.

**Target features:**
- Xây scoring framework đánh giá strategy theo profit, signal quality, timing, market session và volatility regime.
- Chấm điểm ở cả hai mức: per-trade và aggregate theo strategy/symbol/timeframe.
- Chuẩn hóa schema + pipeline lưu evaluation criteria vào DB để truy vấn và thống kê.
- Tạo report engine lọc/so sánh theo nhiều tiêu chí (strategy, symbol, timeframe, session, volatility).
- Gửi Telegram summary/insight dựa trên dữ liệu đánh giá đã chuẩn hóa.

## Current State
**Latest shipped:** v1.5 Signal Delivery & Trade Management (Shipped 2026-04-21)
- Included Phase 26 to 53.
- Milestone archived into `.planning/milestones/v1.5-ROADMAP.md` and `.planning/milestones/v1.5-REQUIREMENTS.md`.
- Signal → order execution runtime đã được chuẩn hóa và đóng vòng verification artifacts.
- Nyquist validation backfill cho v1.5 đã hoàn tất ở milestone closure.

**Current milestone status:** v1.6 Strategy Evaluation & Insight Delivery (Planning)
- Scope active: Phase 54 → 57.
- Trọng tâm: scoring framework đa tiêu chí, evaluation data model/pipeline, reporting engine, Telegram insight.
- Chưa có phase nào của v1.6 được execute tại thời điểm cập nhật này.

**Existing infra (live):**
- `aureus-signal` — signal engine with provider abstraction, strategy evaluation, CircuitBreaker
- `aureus-gateway` — TCP listener nhận market data từ MT5
- `AureusProvider.mq5` — MT5 EA streaming market data (ticks + candles) qua TCP
- `aureus-dashboard` — React + FastAPI web dashboard
- `aureus-nautilus-node` — AureusMarketDataClient (Redis→Bar), AureusExecutionClient (orders→Nautilus)
- `aureus-nautilus-bridge` — order routing + execution reconciliation
- `aureus-bridge-metrics-exporter` — Prometheus metrics

## Requirements
### Validated
- ✓ v1.3 requirement archive exists: `.planning/milestones/v1.3-REQUIREMENTS.md`
- ✓ v1.4 requirement archive exists: `.planning/milestones/v1.4-REQUIREMENTS.md`
- ✓ Define provider abstraction contract and maintain backward-compatible runtime fallback to Redis. *(v1.4)*
- ✓ Implement TradingAgents adapter mapping/cache/error handling and test shadow-mode evaluation capability. *(v1.4)*
- ✓ CircuitBreaker and telemetry offloading implementation *(v1.4)*

### Active
- [ ] Build strategy scoring framework đa tiêu chí (SCOR-01→04).
- [ ] Chuẩn hóa evaluation data model + pipeline persist/recompute (EVAL-01→04).
- [ ] Xây report engine đa chiều cho per-trade + aggregate analytics (RPT-01→05).
- [ ] Hoàn thiện Telegram insight delivery có context/traceability (TEL-EVAL-01→04).
- [ ] Đạt acceptance bắt buộc của v1.6 (ACC-01→03).

### Out of Scope
- Direct cutover to TradingAgents as production primary before shadow validation gates pass.
- Expanding strategy logic or execution semantics unrelated to signal delivery and trade management.
- Mobile app hoặc native notification ngoài Telegram.

## Archived Milestones
- **v1.4 TradingAgents Market Data Integration** (Shipped 2026-04-05, Known testing gaps)
- **v1.3 Backtesting & Measurement Engine** (Shipped 2026-04-03, Proceed anyway with known gaps)
- **v1.2 Strategy Sequence Engine** (Shipped 2026-03-22)
- **v1.1 Signal Optimization** (Shipped 2026-03-22)

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition:**
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone:**
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

_Last updated: 2026-04-21 after v1.6 milestone rebaseline_
