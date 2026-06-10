# PROJECT

## What This Is
A planning control document for Aureus milestone evolution. It captures shipped outcomes, active scope, and requirement sources used by the GSD workflow.

## Core Value
- Validate strategy behavior through deterministic, reproducible evidence.
- Keep signal/strategy contracts observable and stable before deeper integration.
- Leverage Nautilus execution infrastructure while minimizing custom execution complexity.
- Preserve clear milestone auditability (plans, summaries, and known gaps).

## Current Milestone: v1.7 (Planning)

**Goal:** Define next milestone scope with deferred requirements from v1.6

## Current State
**Latest shipped:** v1.6 Strategy Evaluation & Insight Delivery (Shipped 2026-06-10)
- Phase 54-58 completed
- Milestone archived into `.planning/milestones/v1.6-ROADMAP.md` and `.planning/milestones/v1.6-REQUIREMENTS.md`

**Completed in v1.6:**
- Strategy scoring framework (two-stage gate + weighted-sum)
- Evaluation data model + pipeline (journal-linked schema)
- TPO and FZ_CONT strategy fixes (8 strategies verified)

**Deferred to v1.7:**
- Phase 55.1: Restore evaluation pipeline
- Phase 56: Multi-Dimensional Reporting Engine
- Phase 57: Telegram Insight Delivery

**Existing infra (live):**
- `aureus-signal` — signal engine with provider abstraction, strategy evaluation, CircuitBreaker
- `aureus-gateway` — TCP listener nhận market data từ MT5
- `AureusProvider.mq5` — MT5 EA streaming market data (ticks + candles) qua TCP
- `AureusProvider_v2.mq5` — MT5 EA với strategy-aware position management, DCA, OpenAlgo integration
- `aureus-dashboard` — React + FastAPI web dashboard
- `aureus-nautilus-node` — AureusMarketDataClient (Redis→Bar), AureusExecutionClient (orders→Nautilus)
- `aureus-nautilus-bridge` — order routing + execution reconciliation
- `aureus-bridge-metrics-exporter` — Prometheus metrics

## Requirements
### Validated
- ✓ v1.4 requirement archive exists: `.planning/milestones/v1.4-REQUIREMENTS.md`
- ✓ v1.5 requirement archive exists: `.planning/milestones/v1.5-REQUIREMENTS.md`
- ✓ v1.6 requirement archive exists: `.planning/milestones/v1.6-REQUIREMENTS.md`
- ✓ Strategy scoring framework with immutable versioning (v1.6 Phase 54)
- ✓ Evaluation data model + signal snapshot hybrid storage (v1.6 Phase 55)
- ✓ TPO and FZ_CONT strategy pipeline fixes (v1.6 Phase 58)

### Active
- [ ] Restore evaluation pipeline (Phase 55.1)
- [ ] Multi-dimensional reporting engine (RPT-01→05)
- [ ] Telegram insight delivery (TEL-EVAL-01→04)

### Out of Scope
- Direct cutover to TradingAgents as production primary before shadow validation gates pass.
- Expanding strategy logic or execution semantics unrelated to evaluation/reporting.
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

_Last updated: 2026-06-10 after v1.6 milestone closure_
