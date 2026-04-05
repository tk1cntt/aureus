# PROJECT

## What This Is
A planning control document for Aureus milestone evolution. It captures shipped outcomes, active scope, and requirement sources used by the GSD workflow.

## Core Value
- Validate strategy behavior through deterministic, reproducible evidence.
- Keep signal/strategy contracts observable and stable before deeper integration.
- Leverage Nautilus execution infrastructure while minimizing custom execution complexity.
- Preserve clear milestone auditability (plans, summaries, and known gaps).

## Current Milestone: v1.5 Signal Delivery & Trade Management

**Goal:** Xây dựng pipeline hoàn chỉnh từ signal → notification → order execution → result tracking, với dashboard thống kê performance.

**Target features:**
- Service `aureus-notifier`: Telegram notification cho signals và strategy matches, cấu hình filter signal.
- Service `aureus-trader`: MT5 order management (market/pending), order state tracking, hybrid history sync (push + poll).
- Mở rộng `AureusProvider.mq5` để nhận order commands và push order events.
- Cải tiến strategy contract để quy định loại order (entry type, SL, TP).
- Performance dashboard tích hợp `aureus-dashboard`: win rate, profit factor, drawdown, Sharpe ratio.

## Current State
**Latest shipped:** v1.4 TradingAgents Market Data Integration (Closed with known testing gaps, 2026-04-05)
- Included Phase 21 to 25.
- Milestone archived into `.planning/milestones/v1.4-ROADMAP.md` and `.planning/milestones/v1.4-REQUIREMENTS.md`.
- Legacy signal behavior successfully extracted into Provider Abstraction.
- TradingAgents integration implemented with symbol mapping, connection fallback, and asynchronous TimescaleDB telemetry offloading.
- CircuitBreaker pattern embedded for safe evaluation paths.
- Pending tests and shadow-mode evidence checklist remain open for next iterations.

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
- [ ] Telegram notification service cho signal events và strategy matches.
- [ ] MT5 order execution pipeline (strategy → order → MT5).
- [ ] Order state management và MT5 history sync.
- [ ] Performance dashboard thống kê (win rate, profit factor, drawdown, ...).
- [ ] Strategy contract enhancement (entry type, SL, TP specification).
- [ ] Mở rộng AureusProvider.mq5 cho bidirectional communication.

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

_Last updated: 2026-04-05 after v1.5 milestone start_
