# PROJECT

## What This Is
A planning control document for Aureus milestone evolution. It captures shipped outcomes, active scope, and requirement sources used by the GSD workflow.

## Core Value
- Validate strategy behavior through deterministic, reproducible evidence.
- Keep signal/strategy contracts observable and stable before deeper integration.
- Leverage Nautilus execution infrastructure while minimizing custom execution complexity.
- Preserve clear milestone auditability (plans, summaries, and known gaps).

## Current Milestone: v1.4 TradingAgents Market Data Integration

**Goal:** Integrate TradingAgents market data into `aureus-nautilus-node` via provider abstraction and shadow rollout without breaking the current Redis ingest pipeline.

**Target features:**
- Provider abstraction layer in `aureus-nautilus-node` to decouple Redis-only data access.
- TradingAgents adapter with symbol mapping and cache/rate-limit protection.
- Runtime provider routing (`redis`, `shadow`, `tradingagents`) with safe defaults.
- Shadow drift observability and rollout gates before any live promotion.
- Regression-safe test coverage for provider contract, adapter, and gate logic.

## Current State
**Latest shipped:** v1.3 Backtesting & Measurement Engine (closed as Proceed anyway, 2026-04-03)

- Milestone archived into `.planning/milestones/v1.3-ROADMAP.md` and `.planning/milestones/v1.3-REQUIREMENTS.md`.
- Core progress in the previous cycle concentrated on stabilization/diagnosis artifacts (15.6, 15.7, 15.9, 15.10).
- v1.4 focuses on market-data provider architecture and controlled integration safety.

**Existing Nautilus infra (live):**
- `aureus-nautilus-node` — AureusMarketDataClient (Redis→Bar), AureusExecutionClient (orders→Nautilus)
- `aureus-nautilus-bridge` — order routing + execution reconciliation
- `aureus-bridge-metrics-exporter` — Prometheus metrics
- Grafana dashboard: `aureus_nautilus_flow.json` (orders, latency, PnL, SLO signals)

## Requirements
### Validated
- ✓ v1.3 requirement archive exists: `.planning/milestones/v1.3-REQUIREMENTS.md`

### Active
- [ ] Define provider abstraction contract for market data ingestion in `aureus-nautilus-node`.
- [ ] Validate TradingAgents symbol/data compatibility for Aureus symbols (FX/metal/crypto).
- [ ] Implement shadow-mode comparison and drift gates before enabling TradingAgents as primary.
- [ ] Ensure backward-compatible runtime configuration and safe fallback to Redis.
- [ ] Verify end-to-end via adapter/provider/gate test coverage and shadow validation.

### Out of Scope
- Direct cutover to TradingAgents as production primary before shadow validation gates pass.
- Expanding strategy logic or execution semantics unrelated to market-data provider integration.

## Archived Milestones
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

_Last updated: 2026-04-03 after starting milestone v1.4_
