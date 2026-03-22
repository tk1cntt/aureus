# PROJECT

## What This Is
A planning control document for the current Aureus milestone. It defines the active objective, expected value, and requirement sources used by the GSD workflow.

## Core Value
- Improve signal decision quality with deterministic, testable behavior.
- Prevent regression through explicit integration contracts and layered tests.
- Optimize performance only after correctness parity is preserved.

## Current Milestone: v1.3 Backtesting & Measurement Engine

**Goal:** Build a backtesting engine to simulate strategy execution on historical data, validate SL/TP logic against candle H/L, and output measurable performance metrics (Win Rate, PnL, Drawdown).

**Target features:**
- Historical candle simulation engine
- Mock order execution with SL/TP/trailing evaluation
- Strategy performance reports (Win Rate, PnL, Drawdown, Sharpe)
- Integration with existing TemplateStrategy pipeline

## Current State
**Latest shipped:** v1.2 Strategy Sequence Engine (2026-03-22)

All strategy evaluation now runs through `TemplateStrategy` with JSON-driven config (context_filters, sequence, trade_execution). Legacy hardcoded strategies are fully deprecated.

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

_Last updated: 2026-03-22_
