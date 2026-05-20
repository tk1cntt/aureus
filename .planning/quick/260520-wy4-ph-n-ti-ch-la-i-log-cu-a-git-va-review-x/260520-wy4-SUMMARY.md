---
phase: quick-260520-wy4
plan: 01
subsystem: trading-lifecycle
tags: [postgres, mt5, order-lifecycle, journal]
requires:
  - phase: quick-260520-9kx
    provides: exact close cmd_id correlation
provides:
  - ORDER_OPENED parent trade status update from SENT to OPEN
  - regression coverage for exact trace correlation parent upsert
  - runtime DB evidence for current SENT/journal failure
  - DB transaction proof that lifecycle update moves SENT row to OPEN
affects: [aureus-trader, aureus_trade_journal, aureus_trades]
tech-stack:
  added: []
  patterns: [exact trace_id lifecycle correlation, no broad fallback]
key-files:
  created: []
  modified:
    - services/aureus-trader/journal.py
    - services/aureus-trader/tests/test_journal.py
    - services/aureus-trader/tests/conftest.py
key-decisions:
  - "Root cause là on_order_opened parent upsert không set aureus_trades.status khi trace_id conflict, nên row đã SENT vẫn kẹt SENT dù ORDER_OPENED đi qua."
  - "Giữ correlation exact bằng trace_id hiện có, không thêm fallback ticket/cmd_id rộng."
requirements-completed: [QUICK-260520-WY4]
duration: 10min
completed: 2026-05-20
---

# Quick 260520-wy4: Lifecycle SENT fix Summary

**ORDER_OPENED parent trade upsert now moves existing aureus_trades rows from SENT to OPEN with filled_at while preserving exact trace correlation.**

## Performance

- **Duration:** 10 min
- **Started:** 2026-05-20T16:51:12Z
- **Completed:** 2026-05-20T16:58:00Z
- **Tasks:** 3
- **Files modified:** 3

## Evidence

- Git history checked: `4fe9793`, `0d1a6c5`, `9637c91`, `add3910`.
- Runtime DB before fix:
  - `aureus_trade_journal` today: `0`
  - `aureus_trades` today: `SENT=125`
  - samples around 16:18 include `BTCUSD:2604:1779304620`, status `SENT`, empty ticket.
- `260520-9kx` fixed close cmd_id mapping, but did not address parent `aureus_trades` status on ORDER_OPENED conflict.
- Exact failing link: journal `on_order_opened` reached parent `INSERT INTO aureus_trades ... ON CONFLICT (trace_id) DO UPDATE`, but conflict update kept prior `status='SENT'` and `filled_at=NULL`.

## Accomplishments

- Fixed parent trade upsert so ORDER_OPENED exact trace conflict updates `status='OPEN'` and `filled_at`.
- Added targeted regression assertions that parent upsert includes lifecycle status update.
- Adjusted mock DB trace return so regression validates trace_id argument, not ticket.
- Verified DB update semantics in real runtime database transaction.

## Task Commits

1. **Task 2/3 lifecycle code fix** - `75a7ec6` (fix)

## Files Created/Modified

- `services/aureus-trader/journal.py` - adds `status='OPEN'` and `filled_at` on parent upsert conflict.
- `services/aureus-trader/tests/test_journal.py` - asserts parent lifecycle upsert status behavior.
- `services/aureus-trader/tests/conftest.py` - returns correct trace arg for journal update mock.

## Verification

- `wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus/services/aureus-trader && PYTHONPATH=. ../../.venv/bin/python -m pytest tests/test_journal.py::TestReasoningBank::test_on_order_opened_ensures_parent_trade_before_reasoning_insert -q"` passed.
- Real DB transaction proof:
  - seed `e2e-lifecycle-wy4` as `SENT`
  - update same row to `OPEN`, ticket `2605204`
  - returned `e2e-lifecycle-wy4 | OPEN | 2605204`
  - rolled back cleanup.

## GitNexus

- `gitnexus_query -r Aureus "ORDER_OPENED SENT journal empty"` ran.
- `gitnexus_context -r Aureus on_order_opened` found ambiguity between journal and test symbol.
- `gitnexus_impact -r Aureus --direction upstream on_order_opened` ran; blast radius: CRITICAL, 8 impacted, 3 direct, 9 affected processes. Direct d=1: `on_order_filled`, `verify_reasoning_bank_reuse_e2e.py:run_e2e`, `verify_reasoning_bank_db_e2e.py:main`.
- `gitnexus_detect_changes` blocker: CLI has no `detect_changes`, `detect-changes`, or `changes` command in current installed version. Used `git diff` scoped review instead.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Plan referenced wrong service paths**
- **Found during:** Task 2
- **Issue:** planned files under `services/aureus-signal/gateway/trader_gateway.py` and `services/aureus-signal/journal.py` do not exist. Runtime lifecycle code is in `services/aureus-trader/dispatcher.py` and `services/aureus-trader/journal.py`.
- **Fix:** followed actual runtime symbol from grep/GitNexus and edited `services/aureus-trader/journal.py` only.
- **Verification:** targeted pytest and DB proof passed.
- **Committed in:** `75a7ec6`

## Issues Encountered

- Direct `docker` unavailable on Windows host. Read `RUN_SERVICES.md`, retried via `wsl -d Aureus` as required.
- Full `tests/test_journal.py` has pre-existing async pytest marker/path issues when run different cwd; focused regression test passed.

## Known Stubs

None.

## Threat Flags

None.

## Self-Check: PASSED

- Commit `75a7ec6` exists.
- Modified files committed: `services/aureus-trader/journal.py`, `services/aureus-trader/tests/test_journal.py`, `services/aureus-trader/tests/conftest.py`.
- Summary created at `D:/Aureus/.planning/quick/260520-wy4-ph-n-ti-ch-la-i-log-cu-a-git-va-review-x/260520-wy4-SUMMARY.md`.

---
*Phase: quick-260520-wy4*
*Completed: 2026-05-20*
