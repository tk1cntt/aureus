# PROJECT

## What This Is
A planning control document for the current Aureus milestone. It defines the active objective, expected value, and requirement sources used by the GSD workflow.

## Core Value
- Improve signal decision quality with deterministic, testable behavior.
- Prevent regression through explicit integration contracts and layered tests.
- Optimize performance only after correctness parity is preserved.

## Current State
**Latest shipped:** v1.2 Strategy Sequence Engine (2026-03-22)

All strategy evaluation now runs through `TemplateStrategy` with JSON-driven config (context_filters, sequence, trade_execution). Legacy hardcoded strategies are fully deprecated.

## Next Milestone Goals
_To be defined via `/gsd-new-milestone`._

Candidates from deferred ideas:
- **Backtesting & Measurement Engine** — Simulate historical data, mock order execution, output performance reports

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
- Source of truth: `.planning/REQUIREMENTS.md` (created per milestone)
- Roadmap and phase mapping: `.planning/ROADMAP.md`

## Notes
- This milestone was initialized from a research-first pass over `services/aureus-signal/engine/signals/*` and current signal tests.
- Existing `.planning` directory had spec files but no prior milestone lifecycle documents.

_Last updated: 2026-03-22_
