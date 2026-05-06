---
phase: 260506-rkn-pivot-sl-distance-limits
plan: 01
subsystem: aureus-signal
status: completed
tags:
  - quick
  - pivot-sl
  - risk-control
requirements:
  - QUICK-260506-RKN
dependency_graph:
  requires:
    - services/aureus-signal/engine/orders.py::_calculate_sl_tp
    - services/aureus-signal/engine/orders.py::_get_pivot_sl_max_distance
  provides:
    - PIVOT_POINT SL distance cap by symbol class
  affects:
    - services/aureus-signal/engine/orders.py PIVOT_POINT branch
tech_stack:
  added: []
  patterns:
    - symbol-class threshold helper
    - selected-SL distance rejection
key_files:
  created:
    - D:/Aureus/.planning/quick/260506-rkn-pivot-sl-distance-limits/260506-rkn-SUMMARY.md
  modified:
    - D:/Aureus/services/aureus-signal/engine/orders.py
    - D:/Aureus/services/aureus-signal/tests/test_pivot_sl.py
decisions:
  - Distance uses abs(entry - selected_sl) after pivot selection and offset.
  - Rejection uses existing no-order path by returning (None, None) from _calculate_sl_tp.
  - Equal-to-threshold remains allowed because only distance greater than threshold rejects.
metrics:
  completed_date: 2026-05-06
  tasks_completed: 3
  tests_run: "python -m pytest services/aureus-signal/tests/test_pivot_sl.py -x"
---

# Quick Task 260506-rkn: Pivot SL Distance Limits Summary

PIVOT_POINT SL now rejects orders when selected SL is too far from entry for the symbol class.

## Completed Tasks

| Task | Status | Commit | Notes |
|------|--------|--------|-------|
| Task 1: Add PIVOT_POINT SL distance cap regression tests | Completed | 841cb90 / 5b3a914 | Tests cover XAU, USTEC, BTC, forex, equal-threshold allow, and non-PIVOT_POINT isolation. Duplicate test commit exists because first executor overload left committed work before retry. |
| Task 2: Enforce selected PIVOT_POINT SL distance caps | Completed | 5b6743c | Added `_get_pivot_sl_max_distance`; PIVOT_POINT branch rejects `abs(entry - sl) > threshold`. |
| Task 3: Run focused verification and GitNexus change check | Completed | 5b6743c | Focused tests pass; GitNexus detect command unavailable, fallback status/diff used. |

## Behavior

Thresholds:

| Symbol class | Max distance |
|---|---:|
| XAU | 10.0 price units |
| USTEC / NAS | 50.0 index points |
| BTC | 500.0 price units |
| Forex/default | `20 * get_point_size(symbol)` |

Rules:

- Applies only in `sl_mode == 'PIVOT_POINT'` branch.
- Uses selected SL after pivot selection and `offset_pips`.
- Rejects only when distance is greater than threshold.
- Returns `(None, None)` to reuse existing no-order path.
- Non-PIVOT_POINT modes unchanged.

## Verification

```bash
python -m pytest services/aureus-signal/tests/test_pivot_sl.py -x
```

Result:

```text
23 passed in 0.56s
```

Database E2E not run because no DB behavior changed.

## GitNexus Results

Impact before production edit:

- `_calculate_sl_tp` lookup resolved to a test-local symbol due ambiguous symbol names: direct callers 0, affected processes 0, risk LOW. Limitation documented.
- `_find_pivot_for_sl_candidates` upstream: direct caller `_calculate_sl_tp`, affected processes 11, modules Engine/Tests, risk CRITICAL. Change kept surgical inside PIVOT_POINT path and verified with focused regression tests.

Detect changes:

- `npx gitnexus detect-changes --repo Aureus` failed: `error: unknown command 'detect-changes'`.
- Fallback used `git status`, recent commits, focused tests, and file-scope checks.

## Deviations from Plan

### Executor overload recovery

- First two gsd-executor attempts failed with server overload.
- One failed attempt still committed test/code commits before returning overload error.
- Orchestrator continued inline, verified code, created summary, and will complete verification/docs commit.

## Known Stubs

None.

## Threat Flags

None. No new endpoint, auth path, schema change, DB access, or trust boundary added.

## Self-Check: PASSED

- Found `D:/Aureus/services/aureus-signal/engine/orders.py`.
- Found `D:/Aureus/services/aureus-signal/tests/test_pivot_sl.py`.
- Found commits `841cb90`, `5b3a914`, `5b6743c`.
- Focused tests pass.
