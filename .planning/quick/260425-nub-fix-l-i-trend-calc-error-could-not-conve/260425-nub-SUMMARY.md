---
phase: 260425-nub-fix-l-i-trend-calc-error-could-not-conve
plan: 01
subsystem: aureus-signal trend calculation
tags: [quick-fix, trend, regression]
dependency_graph:
  requires: [services/aureus-signal/engine/signals/trend.py]
  provides: [safe categorical LOW handling in trend numeric conversion and order-block scoring]
  affects: [TrendSignal.calculate, TrendSignal._ema_value, TrendSignal._ema_score, TrendSignal._ob_score]
tech_stack:
  added: []
  patterns: [pandas numeric coercion]
key_files:
  created:
    - services/aureus-signal/tests/test_trend_categorical_values.py
  modified:
    - services/aureus-signal/engine/signals/trend.py
    - services/aureus-signal/tests/test_trend_categorical_values.py
decisions:
  - Categorical order-block quality values are not treated as numeric; non-numeric quality/body_ratio values fall back to the existing neutral 0.5 score default.
metrics:
  completed_date: 2026-04-25T00:00:00Z
  tasks_completed: 3
  tests_run: 11
---

# Quick Task 260425-nub Summary

Fixed the trend calculation `LOW` conversion failure by guarding numeric conversion boundaries in `TrendSignal.calculate`/EMA scoring and closing the verifier gap where categorical `LOW` in `state.obs[*].quality` could still raise `ValueError` inside `TrendSignal._ob_score`.

## What Changed

- Added regression coverage for latest `ema_3="LOW"` entering `TrendSignal.calculate`.
- Guarded current close, EMA values, and EMA score conversion with `pd.to_numeric(..., errors="coerce")` so categorical values become missing rather than raising.
- Added regression coverage for `state.obs` containing an order block with `quality="LOW"`.
- Guarded `_ob_score` conversion for `quality` and `body_ratio` using numeric coercion.
- Preserved numeric behavior: numeric EMA/close, `quality`, and `body_ratio` still contribute to the same trend payload and clamped score formulas.
- Non-numeric categorical metadata is not interpreted as numeric; invalid EMA/close returns safe `None`/`NEUTRAL`, while invalid OB quality/body_ratio falls back to the existing default `0.5` weight input.

## Verification

- `python -m pytest services/aureus-signal/tests/test_trend_categorical_values.py services/aureus-signal/tests/test_atr_o1.py services/aureus-signal/tests/test_dynamic_amplitude.py -q`
- Result: `11 passed in 0.65s` locally; verifier re-ran the same focused suite with `11 passed in 0.64s`.

## Commits

- `ca8ac46` test(quick-260425-nub): add LOW trend regression
- `0ad72bf` fix(quick-260425-nub): guard trend numeric conversion
- `b669aa7` fix(quick-260425-nub): coerce trend order-block quality

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Verification found a second LOW conversion boundary**
- **Found during:** Post-execution verification
- **Issue:** Initial fix guarded EMA/close conversion, but `_ob_score` still used direct `float(...)` conversion for order-block `quality`/`body_ratio`, so `quality="LOW"` could raise the same `ValueError`.
- **Fix:** Added regression coverage for `state.obs[*].quality="LOW"` and guarded `_ob_score` conversion with numeric coercion/default `0.5` fallback.
- **Files modified:** `services/aureus-signal/engine/signals/trend.py`, `services/aureus-signal/tests/test_trend_categorical_values.py`
- **Commit:** `b669aa7`

## GitNexus / Scope Check

GitNexus MCP tools were not available in this executor environment, so the required impact/detect-changes checks used fallback source/git inspection. Blast radius was limited to `TrendSignal`/`TrendSignal._ob_score`; the final code changes are surgical to:

- `services/aureus-signal/engine/signals/trend.py`
- `services/aureus-signal/tests/test_trend_categorical_values.py`

## Known Stubs

None.

## Threat Flags

None. The change only hardens an existing market-data/signal metadata to trend calculation boundary already identified in the plan threat model.

## Self-Check: PASSED

- Summary created at `D:/Aureus/.planning/quick/260425-nub-fix-l-i-trend-calc-error-could-not-conve/260425-nub-SUMMARY.md`.
- Focused tests passed.
- Code/test commits exist on `v4`.
