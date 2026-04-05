# PROJECT

## What This Is
A planning control document for Aureus milestone evolution. It captures shipped outcomes, active scope, and requirement sources used by the GSD workflow.

## Core Value
- Validate strategy behavior through deterministic, reproducible evidence.
- Keep signal/strategy contracts observable and stable before deeper integration.
- Leverage Nautilus execution infrastructure while minimizing custom execution complexity.
- Preserve clear milestone auditability (plans, summaries, and known gaps).

## Current Milestone: v1.5 Next Actions

**Goal:** Close the testing and primary cutover gap for TradingAgents and start execution measurements.

**Target features:**
- Completion of provider integration automated testing.
- Activation of Prometheus metrics observability pipelines.

## Current State
**Latest shipped:** v1.4 TradingAgents Market Data Integration (Closed with known testing gaps, 2026-04-05)
- Included Phase 21 to 25.
- Milestone archived into `.planning/milestones/v1.4-ROADMAP.md` and `.planning/milestones/v1.4-REQUIREMENTS.md`.
- Legacy signal behavior successfully extracted into Provider Abstraction.
- TradingAgents integration implemented with symbol mapping, connection fallback, and asynchronous TimescaleDB telemetry offloading.
- CircuitBreaker pattern embedded for safe evaluation paths.
- Pending tests and shadow-mode evidence checklist remain open for next iterations.

**Existing Nautilus infra (live):**
- `aureus-nautilus-node` — AureusMarketDataClient (Redis→Bar), AureusExecutionClient (orders→Nautilus)
- `aureus-nautilus-bridge` — order routing + execution reconciliation
- `aureus-bridge-metrics-exporter` — Prometheus metrics
- Grafana dashboard: `aureus_nautilus_flow.json` (orders, latency, PnL, SLO signals)

## Requirements
### Validated
- ✓ v1.3 requirement archive exists: `.planning/milestones/v1.3-REQUIREMENTS.md`
- ✓ v1.4 requirement archive exists: `.planning/milestones/v1.4-REQUIREMENTS.md`
- ✓ Define provider abstraction contract and maintain backward-compatible runtime fallback to Redis. *(v1.4)*
- ✓ Implement TradingAgents adapter mapping/cache/error handling and test shadow-mode evaluation capability. *(v1.4)*
- ✓ CircuitBreaker and telemetry offloading implementation *(v1.4)*

### Active
- [ ] Verify end-to-end via adapter/provider/gate test coverage and shadow validation.

### Out of Scope
- Direct cutover to TradingAgents as production primary before shadow validation gates pass.
- Expanding strategy logic or execution semantics unrelated to market-data provider integration.

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

_Last updated: 2026-04-05 after v1.4 milestone completion_
