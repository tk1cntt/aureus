---
phase: 260523-ua9-ph-n-tich-va-ti-m-nguy-n-nh-n-k-l-u-data
plan: 01
subsystem: signal snapshot persistence
tags: [quick, tpo, journal, db-e2e]
requires: [260521-u20]
provides: [full TPO D0-D3 persistence via ORDER_OPENED]
affects: [signal_event_publisher, trade_journal, signal_snapshot_pipeline_tests]
tech-stack:
  added: []
  patterns: [nested snapshot merge, asyncpg DB E2E]
key-files:
  created: []
  modified:
    - services/aureus-signal/engine/signal_event_publisher.py
    - services/aureus-signal/tests/test_signal_event_publisher.py
    - services/aureus-trader/tests/test_signal_snapshot_pipeline.py
decisions:
  - Fix only nested merge in signal publisher; journal mapping already persisted D0-D3 correctly.
metrics:
  completed_date: 2026-05-23T15:20:36Z
  tasks_completed: 3
---

# Quick 260523-ua9 Summary: Full TPO D0-D3 Snapshot Persistence

## One-liner

Nested TPO D0-D3 signal snapshots now survive strategy-match merge and DB E2E proves `TradeJournalManager.on_order_opened` persists non-null d0/d1/d2/d3 POC/VAH/VAL/OHLC.

## Root Cause

`_merge_signal_snapshots` merged only top-level keys. When `normalized_signal_snapshot` already had a partial nested block like `tpo_d1={POC,CLOSE}`, derived `indicator_snapshot.tpo_d1` could not add missing `VAH/VAL/OPEN/HIGH/LOW`. Journal extraction and INSERT already handled nested `tpo_d0..tpo_d3` and `d0_poc..d3_close` correctly.

## Changes

- Added failing signal publisher reproduction for partial `tpo_d1` merge plus full `tpo_d0/tpo_d2/tpo_d3` preservation.
- Changed `_merge_signal_snapshots` to merge nested dict values without overwriting existing nested fields.
- Added DB E2E that creates TRIGGERED journal row, calls `TradeJournalManager.on_order_opened`, then SELECTs all `d0_poc..d3_close` values.
- Updated old snapshot pipeline assertion indexes after D0-D3 column expansion.

## GitNexus Blast Radius

| Symbol | Risk | Direct Callers | Affected Processes | Notes |
|---|---:|---|---:|---|
| `_resolve_strategy_match_signal_snapshot` | CRITICAL | `publish_strategy_match` | 11 | Upstream path to `prepare_and_publish_strategy_match` and `run_strategy_executor`. |
| `_build_signal_snapshot_columns` | CRITICAL | `on_order_opened` | 9 | Inspected only; no production change. |
| `_merge_signal_snapshots` | LOW | `_resolve_strategy_match_signal_snapshot` | 0 | Production fix target. |

GitNexus `detect_changes` equivalent was unavailable in installed CLI (`detect-changes` and `detect_changes` unknown). Scope checked with `git diff` and committed file list: only expected signal publisher and tests changed.

## Verification

- `cd D:/Aureus/services/aureus-signal && pytest tests/test_signal_event_publisher.py -q` → 10 passed.
- `cd D:/Aureus/services/aureus-trader && pytest tests/test_journal.py::TestReasoningBank::test_on_order_opened_persists_d0_d3_tpo_levels_to_signal_snapshot -q` → 1 passed.
- `cd D:/Aureus/services/aureus-trader && AUREUS_TEST_DB_DSN="postgresql://aureus:aureus_password@localhost:5433/aureus" pytest tests/test_signal_snapshot_pipeline.py::test_tpo_d0_d3_db_e2e_journal_on_order_opened_persists_full_tpo -q` → 1 passed.
- `cd D:/Aureus/services/aureus-trader && pytest tests/test_signal_snapshot_pipeline.py -q` → 9 passed, 1 skipped.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed stale snapshot argument indexes**
- **Found during:** Task 2 full pipeline verification.
- **Issue:** Existing tests asserted old argument indexes before D0-D3 columns were added, causing false failures while production behavior was correct.
- **Fix:** Updated assertions for `created_at` and `d1_open/high/low/close` to current INSERT argument positions.
- **Files modified:** `services/aureus-trader/tests/test_signal_snapshot_pipeline.py`
- **Commit:** `29b05f8`

## Threat Flags

None.

## Known Stubs

None.

## Commits

- `aab842a` fix(260523-ua9): preserve nested TPO snapshot fields
- `29b05f8` test(260523-ua9): align TPO snapshot assertions

## Self-Check: PASSED

- Summary file exists.
- Code commits exist: `aab842a`, `29b05f8`.
- Modified plan files committed: `services/aureus-signal/engine/signal_event_publisher.py`, `services/aureus-signal/tests/test_signal_event_publisher.py`, `services/aureus-trader/tests/test_signal_snapshot_pipeline.py`.
