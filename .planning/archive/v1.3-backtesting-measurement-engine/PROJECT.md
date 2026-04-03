# PROJECT

## What This Is
A planning control document for Aureus milestone evolution. It captures shipped outcomes, active scope, and requirement sources used by the GSD workflow.

## Core Value
- Validate strategy behavior through deterministic, reproducible evidence.
- Keep signal/strategy contracts observable and stable before deeper integration.
- Leverage Nautilus execution infrastructure while minimizing custom execution complexity.
- Preserve clear milestone auditability (plans, summaries, and known gaps).

## Current Milestone
**Status:** Milestone planning reset required for next version (`/gsd-new-milestone`).

## Current State
**Latest shipped:** v1.3 Backtesting & Measurement Engine (closed as Proceed anyway, 2026-04-03)

- Milestone archived into `.planning/milestones/v1.3-ROADMAP.md` and `.planning/milestones/v1.3-REQUIREMENTS.md`.
- Core progress in this cycle concentrated on stabilization/diagnosis artifacts (15.6, 15.7, 15.9, 15.10).
- Several v1.3 requirement groups remained incomplete at close time and are tracked in `.planning/MILESTONES.md` under **Known Gaps**.

**Existing Nautilus infra (live):**
- `aureus-nautilus-node` — AureusMarketDataClient (Redis→Bar), AureusExecutionClient (orders→Nautilus)
- `aureus-nautilus-bridge` — order routing + execution reconciliation
- `aureus-bridge-metrics-exporter` — Prometheus metrics
- Grafana dashboard: `aureus_nautilus_flow.json` (orders, latency, PnL, SLO signals)

## Archived Milestones

- **v1.3 Backtesting & Measurement Engine** (Shipped 2026-04-03, Proceed anyway with known gaps)
- **v1.2 Strategy Sequence Engine** (Shipped 2026-03-22)
- **v1.1 Signal Optimization** (Shipped 2026-03-22)

## Requirements
- v1.3 requirement archive: `.planning/milestones/v1.3-REQUIREMENTS.md`
- v1.3 roadmap archive: `.planning/milestones/v1.3-ROADMAP.md`
- Next milestone requirements will be created via `/gsd-new-milestone`

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition:**
1. Move validated requirements to shipped context.
2. Record new constraints/decisions.
3. Update technical debt and active blockers.

**After each milestone:**
1. Archive roadmap + requirements.
2. Log known gaps (if any) explicitly in `MILESTONES.md`.
3. Reset active milestone scope.

_Last updated: 2026-04-03 after v1.3 milestone closure_
