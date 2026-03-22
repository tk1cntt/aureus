# ROADMAP

## Overview
**Milestone:** v1.2 Strategy Sequence Engine
**Goal:** Migrate Aureus strategy logic to a unified, production-ready sequence evaluation engine.
**Phases:** 2

| Phase | Name | Requirements | Status |
|---|---|---|---|
| 14 | Sequence Engine Foundation | SEQ-01, SEQ-02 | NOT STARTED |
| 15 | Strategy Migration & Unification | SEQ-03, SEQ-04 | NOT STARTED |

---

## Phase 14: Sequence Engine Foundation
**Requirements:** SEQ-01, SEQ-02
**Goal:** Build a robust, test-backed sequence evaluator in `TemplateStrategy` capable of handling time waits, strict ordering, and resetting context.

**Success Criteria:**
1. `TemplateStrategy._evaluate_sequence` accurately tracks matched steps without using simulated pointers.
2. `max_wait` correctly expires waiting steps if the candle difference is too large.
3. `reset_signals` correctly resets the sequence state if a counter-signal is detected.
4. Unit tests cover at least 5 complex sequence edge cases (e.g., partial match -> timeout, partial match -> reset).

---

## Phase 15: Strategy Migration & Unification
**Requirements:** SEQ-03, SEQ-04
**Goal:** Deprecate the legacy "coded" strategy classes and unify all evaluations under the config-driven engine in `StrategyRegistry`.

**Success Criteria:**
1. `TrendContinuationStrategy` and `OrderFlowDominanceStrategy` code are deprecated/removed.
2. Equivalent strategy configs using `sequence` are established in DB seeds.
3. `StrategyRegistry` only runs sequences and handles rejection tracking cleanly, bypassing class-specific overrides.
