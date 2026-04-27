---
phase: 260427-v5g-implement-c-c-ph-n-todo-v-c-c-ph-n-ch-a-
plan: 01
subsystem: aureus-signal order planning
tags: [quick, orders, entry-price, pivot-sl, no-fallback]
requirements: [QUICK-260427-V5G]
key-files:
  created: []
  modified:
    - services/aureus-signal/engine/orders.py
    - services/aureus-signal/engine/snapshot_utils.py
    - services/aureus-signal/tests/test_entry_price_methods.py
    - services/aureus-signal/tests/test_pivot_sl.py
    - services/aureus-signal/tests/test_decision_trace_schema.py
    - services/aureus-signal/unittest/test_orders_events.py
decisions:
  - Invalid entry/SL plans now reject instead of silently falling back to CURRENT or FIXED_PIPS.
  - ENTRY_PIVOT_LIMIT is accepted by snapshot validation and resolved only from valid unbroken LL/HH pivots.
metrics:
  completed_at: "2026-04-27T15:38:23Z"
  tasks_completed: 3
  tests: "50 passed"
---

# Quick Task 260427-v5g Summary

Implemented no-fallback order planning semantics for live `orders.py`: invalid entry methods, failed entry helpers, and missing PIVOT_POINT pivots now warn and reject the order plan instead of opening with fallback prices.

## Completed Tasks

| Task | Name | Commit | Files |
|---|---|---|---|
| 1 | Tạo regression tests cho no-fallback entry/SL behavior | 7169dff | `services/aureus-signal/tests/test_entry_price_methods.py`, `services/aureus-signal/tests/test_pivot_sl.py`, `services/aureus-signal/tests/test_decision_trace_schema.py` |
| 2 | Implement entry và PIVOT_POINT SL no-fallback trong orders.py | 3fe7c23 | `services/aureus-signal/engine/orders.py`, `services/aureus-signal/engine/snapshot_utils.py` |
| 3 | Chạy verification mở rộng và GitNexus scope gate | 87f546e | `services/aureus-signal/unittest/test_orders_events.py` |

## What Changed

- `_calculate_entry_price` now returns current close only for `CURRENT`; unknown/failed methods return `None` with warning.
- `process_triggers` now rejects `computed_entry is None` before `_calculate_sl_tp` and before any `float(computed_entry)` cast.
- `_entry_pullback_50` uses valid unbroken side-specific swing points: BUY from LL to trigger high, SELL from HH to trigger low.
- `_entry_pivot_limit` uses valid unbroken LL below current for BUY and HH above current for SELL.
- PIVOT_POINT SL applies `pivot_index` after 5-candle pivot filtering and returns `(None, None)` when the requested candidate is unavailable.
- `VALID_ENTRY_METHODS` now includes `ENTRY_PIVOT_LIMIT` so strategy configs are not normalized to `CURRENT`.
- Existing order-event tests were updated to provide complete order plans explicitly; older fallback assumptions were removed.

## Verification

- `python -m pytest services/aureus-signal/tests/test_entry_price_methods.py services/aureus-signal/tests/test_pivot_sl.py services/aureus-signal/tests/test_decision_trace_schema.py -q` initially failed before production changes, as expected for TDD RED.
- `python -m pytest services/aureus-signal/tests/test_entry_price_methods.py services/aureus-signal/tests/test_pivot_sl.py services/aureus-signal/tests/test_decision_trace_schema.py services/aureus-signal/unittest/test_orders_events.py -q` passed: `50 passed in 0.67s`.

## GitNexus Gates

- Impact gate attempted before production edits.
- `npx gitnexus impact _calculate_entry_price --repo Aureus --direction upstream`: LOW risk, 1 direct caller in indexed graph (`process_triggers`), 0 indexed affected processes.
- `npx gitnexus impact _calculate_sl_tp --repo Aureus --direction upstream`: LOW risk, 1 direct caller in indexed graph (`process_triggers`), 0 indexed affected processes.
- `SimulatedTradeManager.process_triggers`, `_entry_pullback_50`, `_entry_pivot_limit`, and `VALID_ENTRY_METHODS` were not resolved by the current GitNexus CLI/index for the live target symbols; `_calculate_entry_price`/`_calculate_sl_tp` also resolved to similarly named `engine/simulated_orders.py` entries. This is documented as an index/tool limitation.
- `gitnexus_detect_changes` could not be run because this installed `npx gitnexus` CLI does not expose `detect_changes` or `detect-changes` commands. I attempted both and they returned `unknown command`. Scope was verified via `git diff`, targeted files only, and passing tests.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Restored worktree after Windows base correction**
- **Found during:** startup branch check
- **Issue:** Required `git reset --soft aa4fa66...` left the worktree showing widespread staged deletes/adds because the worktree had been materialized from the wrong base.
- **Fix:** Restored tracked files from `HEAD` with `git restore --source=HEAD --staged --worktree .` before making task changes.
- **Files modified:** none in final diff
- **Commit:** n/a

**2. [Rule 1 - Bug] Existing order-event tests used incomplete implicit order plans**
- **Found during:** Task 3 extended verification
- **Issue:** Existing tests expected order creation with missing `size`, `tp.value`, and explicit plan fields. New no-fallback validation correctly rejected those incomplete plans.
- **Fix:** Updated fixtures in `services/aureus-signal/unittest/test_orders_events.py` to pass explicit complete order plans and updated SELL pullback fixture to HH-side semantics.
- **Files modified:** `services/aureus-signal/unittest/test_orders_events.py`
- **Commit:** 87f546e

## Auth Gates

None.

## DB E2E

Not applicable. This quick task did not modify database schema, DB writer, journal persistence, or data creation paths. Changes are limited to live order validation/rejection runtime constants and unit tests.

## Known Stubs

None found in modified files. Existing tests use fake Redis/state fixtures intentionally for unit isolation.

## Threat Flags

No new network endpoints, auth paths, file access patterns, schema changes, or trust-boundary surfaces were introduced beyond the planned order validation/rejection behavior.

## Self-Check: PASSED

- Modified files exist in the worktree.
- Commits exist: `7169dff`, `3fe7c23`, `87f546e`.
- Working tree was clean after task commits.
