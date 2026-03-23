# PROJECT

## What This Is
A planning control document for the current Aureus milestone. It defines the active objective, expected value, and requirement sources used by the GSD workflow.

## Core Value
- Validate strategy effectiveness through deterministic, reproducible backtesting.
- Leverage NautilusTrader's production-grade execution engine instead of building custom.
- Maximize reporting value with minimal effort — Grafana for monitoring, Custom UI for interaction.
- Prevent regression through parity validation between backtest and live signal pipelines.

## Current Milestone: v1.3 Backtesting & Measurement Engine

**Goal:** Integrate NautilusTrader BacktestEngine with Aureus signal pipeline. Aureus signals run via `AureusSignalActor` (Nautilus Actor), strategies wrapped by `AureusStrategyAdapter` (Nautilus Strategy). Nautilus handles order execution, SL/TP matching, fill simulation. Results persist to TimescaleDB → Custom UI + Grafana.

**Target features:**
- Strategy quality validation (independent of Nautilus) — scenario tests + replay baselines
- Nautilus BacktestEngine with bar-based execution (O→H→L→C, adaptive ordering)
- `AureusSignalActor` — runs all 18 signals per bar inside Nautilus
- `AureusStrategyAdapter` — wraps any BaseStrategy for Nautilus order submission
- Performance metrics: Win Rate, PnL, Drawdown, Sharpe, Profit Factor, Avg R:R
- Signal Quality Calculator per signal tag
- Custom UI: backtest runner, candlestick chart with overlays, equity curve
- Grafana: supplementary dashboards for aggregate stats and monitoring
- Parity validation: backtest signals === live signals on same data

**Key architecture decision:** Strategy quality must be validated independently (Phase 15.5) before Nautilus integration, so poor backtest results can be attributed correctly. Nautilus handles execution/fills, Aureus owns signal logic. Same strategy codebase for live and backtest.

## Current State
**Latest shipped:** v1.2 Strategy Sequence Engine (2026-03-22)

All strategy evaluation now runs through `TemplateStrategy` with JSON-driven config (context_filters, sequence, trade_execution). Legacy hardcoded strategies fully deprecated.

**Existing Nautilus infra (live):**
- `aureus-nautilus-node` — AureusMarketDataClient (Redis→Bar), AureusExecutionClient (orders→Nautilus)
- `aureus-nautilus-bridge` — order routing + execution reconciliation
- `aureus-bridge-metrics-exporter` — Prometheus metrics
- Grafana dashboard: `aureus_nautilus_flow.json` (orders, latency, PnL, SLO signals)
- Docker services: nautilus_trader-dev, aureus-nautilus-node-dev, aureus-nautilus-bridge-dev

## Archived Milestones

**v1.2 Strategy Sequence Engine (Shipped 2026-03-22)**
- O(1) state machine sequence engine in TemplateStrategy
- 3-pillar strategy framework (What/When/How)
- Legacy strategy deprecation and registry unification

<details>
<summary><b>Archived: v1.1 Signal Optimization</b></summary>

**Goal:** Improve signal decision accuracy and deterministic behavior first, then optimize performance without changing trading intent.

**Target features:**
- Deterministic signal parity hardening across key signal modules
- Correctness-first validation for structure/OB/FVG/sweep/trend outputs
- Performance-safe optimization guarded by parity and regression checks
</details>

## Requirements
- Source of truth: `.planning/REQUIREMENTS.md`
- Roadmap and phase mapping: `.planning/ROADMAP.md`
- Integration plan: conversation artifact `implementation_plan.md`
- Nautilus research: conversation artifact `nautilus_research.md`

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

_Last updated: 2026-03-23_
