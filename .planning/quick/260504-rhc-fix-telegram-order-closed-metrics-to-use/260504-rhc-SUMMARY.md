---
phase: quick-260504-rhc-fix-telegram-order-closed-metrics-to-use
plan: 01
subsystem: notifier
tags: [telegram, order-closed, pips, realized-rr, pytest]
requires: []
provides:
  - ORDER_CLOSED Telegram pips use actual entry/close price before event pips
  - ORDER_CLOSED realized RR uses close move against initial SL
  - Regression tests for ETHUSD explicit bad pips override and planned TP mismatch
affects: [aureus-notifier, telegram-order-messages]
tech-stack:
  added: []
  patterns: [price-derived formatter metrics before untrusted event metric fallback]
key-files:
  created:
    - .planning/quick/260504-rhc-fix-telegram-order-closed-metrics-to-use/260504-rhc-SUMMARY.md
  modified:
    - services/aureus-notifier/order_reporter.py
    - services/aureus-notifier/tests/test_order_reporter.py
key-decisions:
  - Prefer valid entry/close price for ORDER_CLOSED pips before explicit event pips to avoid stale EA override.
  - Use realized close move over initial SL risk for ORDER_CLOSED RR instead of planned TP/SL ratio.
patterns-established:
  - Formatter trust boundary favors independently derived metrics when source prices are valid.
requirements-completed: [QUICK-260504-RHC]
duration: unknown
completed: 2026-05-04
---

# Quick 260504-rhc: Fix Telegram Order Closed Metrics Summary

**ORDER_CLOSED Telegram pips and RR now use actual close price when valid, preventing ETHUSD +9900.0 pips from stale event data.**

## Performance

- **Duration:** unknown
- **Started:** not captured
- **Completed:** 2026-05-04
- **Tasks:** 3
- **Files modified:** 2

## Accomplishments

- Added regression coverage proving ETHUSD BUY `2364.45 -> 2365.44` renders `+99.0 pips`, not `+9900.0 pips`.
- Added regression coverage proving ORDER_CLOSED RR uses actual close price, not planned TP.
- Updated `_format_close` pips/RR logic only, without DB, MQL5, or unrelated file changes.

## Task Commits

1. **Task 1: Add regression tests for actual close-price metrics** - `db814d3` (test)
2. **Task 2: Recalculate pips and RR from real close price** - `61271b2` (fix)
3. **Task 3: Run expected-scope checks** - no code commit; verification-only task

## Files Created/Modified

- `services/aureus-notifier/tests/test_order_reporter.py` - ETHUSD pips override and realized RR regression tests.
- `services/aureus-notifier/order_reporter.py` - `_format_close` pips and RR calculation changed to use valid entry/close/SL.
- `.planning/quick/260504-rhc-fix-telegram-order-closed-metrics-to-use/260504-rhc-SUMMARY.md` - execution summary.

## Decisions Made

- Prefer price-derived pips when `entry > 0`, `close_price > 0`, and symbol pip size exists; fallback to explicit event pips only when price calculation cannot run.
- Compute realized RR as `abs(close_price - entry) / abs(entry - sl_initial)`; omit RR when SL missing or invalid.

## Deviations from Plan

None - plan executed exactly as written.

## GitNexus Checks

- Impact attempted before editing: `gitnexus_impact '{"target":"OrderStatusReporter._format_close","direction":"upstream"}'`
  - Result: `/usr/bin/bash: line 1: gitnexus_impact: command not found`
  - Fallback blast radius: direct production caller `_handle_order_closed`; direct test callers in `TestFormatClose`; risk low, scoped to ORDER_CLOSED Telegram formatting.
- Detect changes attempted before code commit and at end: `gitnexus_detect_changes '{"scope":"all"}'`
  - Result: `/usr/bin/bash: line 1: gitnexus_detect_changes: command not found`
  - Fallback scope check: `git status --short -- services/aureus-notifier/order_reporter.py services/aureus-notifier/tests/test_order_reporter.py mql5/AureusProvider_v2.mq5 mql5/AureusProvider_v2.ex5 stable` showed only expected notifier files plus preserved unrelated user work.

## Verification

- RED: `cd D:/Aureus/services/aureus-notifier && python -m pytest tests/test_order_reporter.py::TestFormatClose -q`
  - Result: 2 failed, 10 passed before production fix.
- GREEN: `cd D:/Aureus/services/aureus-notifier && python -m pytest tests/test_order_reporter.py::TestFormatClose -q`
  - Result: 12 passed.
- Full suite: `cd D:/Aureus/services/aureus-notifier && python -m pytest tests/test_order_reporter.py -q`
  - Result: 16 passed.

## Known Stubs

None found in files modified by this quick task.

## Threat Flags

None. Existing formatter trust boundary mitigated by preferring price-derived metrics over event pips.

## Issues Encountered

- GitNexus shell commands unavailable in this environment; exact command errors documented above.
- Worktree branch check required soft reset to `aeb60f45214c2bea9439697cea7def8a9ed762e4`; unrelated user work in `mql5/AureusProvider_v2.mq5`, `mql5/AureusProvider_v2.ex5`, and `stable/` preserved.

## User Setup Required

None.

## Next Phase Readiness

Notifier ORDER_CLOSED metrics now have focused regression tests and can be verified with `python -m pytest tests/test_order_reporter.py -q` from `D:/Aureus/services/aureus-notifier`.

## Self-Check: PASSED

- Found modified code file: `D:/Aureus/services/aureus-notifier/order_reporter.py`
- Found modified test file: `D:/Aureus/services/aureus-notifier/tests/test_order_reporter.py`
- Found summary file: `D:/Aureus/.planning/quick/260504-rhc-fix-telegram-order-closed-metrics-to-use/260504-rhc-SUMMARY.md`
- Found task commit: `db814d3`
- Found task commit: `61271b2`

---
*Phase: quick-260504-rhc-fix-telegram-order-closed-metrics-to-use*
*Completed: 2026-05-04*
