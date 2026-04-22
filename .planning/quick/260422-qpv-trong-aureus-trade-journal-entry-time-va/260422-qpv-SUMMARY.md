# Quick Task 260422-qpv Summary

## Goal
Bắt buộc `entry_time` và `exit_time` trong `aureus_trade_journal` chỉ lấy từ payload order MT5, không fallback sang nguồn khác.

## Changes

### 1) Journal logic hardened to MT5-only timestamps
- Updated: `services/aureus-trader/journal.py`
- `on_order_opened`:
  - Requires `time`/`open_time` from MT5.
  - Returns `False` when missing/invalid/unsupported timestamp type.
  - No fallback to `datetime.now(...)`.
- `on_order_closed`:
  - Requires `close_time`/`time` from MT5.
  - Returns `False` when missing/invalid/unsupported timestamp type.
  - No fallback to `datetime.now(...)`.

### 2) Pipeline tests aligned with MT5 timestamp contract
- Updated: `services/aureus-trader/tests/test_evaluation_pipeline.py`
  - Added `time` in ORDER_OPENED payloads for positive-path tests.
- Updated: `services/aureus-trader/tests/test_signal_snapshot_pipeline.py`
  - Added `time` in positive-path ORDER_OPENED payloads.
  - Added negative tests for missing/invalid MT5 order time.

### 3) Journal tests updated for no-fallback behavior
- Updated: `services/aureus-trader/tests/test_journal.py`
  - Added `test_TJ_IN_10c_missing_mt5_order_time`.
  - Added `test_TJ_IN_10d_invalid_mt5_order_time_string`.
  - Updated branch-coverage expectations to `False` when MT5 time is absent.

## Verification
- `pytest services/aureus-trader/tests/test_evaluation_pipeline.py services/aureus-trader/tests/test_signal_snapshot_pipeline.py -q` → **10 passed**
- `pytest services/aureus-trader/tests/test_journal.py -q` → **62 passed**
- `pytest services/aureus-trader/tests/test_signal_snapshot_migration.py -q` → **5 passed**

## Outcome
`aureus_trade_journal.entry_time` và `aureus_trade_journal.exit_time` hiện không còn được synthesize/fallback; dữ liệu thời gian chỉ chấp nhận nguồn order MT5 như yêu cầu.