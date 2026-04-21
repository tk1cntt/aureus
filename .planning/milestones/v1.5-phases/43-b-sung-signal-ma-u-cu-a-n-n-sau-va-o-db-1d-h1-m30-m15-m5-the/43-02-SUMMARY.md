---
phase: 43-b-sung-signal-ma-u-cu-a-n-n-sau-va-o-db-1d-h1-m30-m15-m5-the
plan: 02
subsystem: signal-snapshot-persistence
tags: [python, postgres, snapshot, mtf, bb, null-policy]
requires: [43-01]
provides:
  - Persist candle color MTF + BB MTF vào snapshot path (single + batch)
  - Đồng bộ schema DB additive cho field mới
  - Regression tests cho null-first + backward compatibility
affects: [phase-43-verification]
tech-stack:
  added: []
  patterns: [additive contract, null-first policy, last-closed HTF]
key-files:
  modified:
    - services/aureus-signal/engine/snapshot_utils.py
    - services/aureus-signal/engine/live_engine.py
    - services/aureus-db-writer/schema.sql
  created:
    - services/aureus-signal/tests/test_snapshot_mtf_fields.py
    - services/aureus-signal/tests/test_snapshot_null_policy.py
requirements-completed: [PH43-01, PH43-02, PH43-03, PH43-04]
completed: 2026-04-16
---

# Phase 43 Plan 02 Summary

## Kết quả chính

- Mở rộng `build_snapshot()` để gắn đủ field mới:
  - `candle_color_d1`, `candle_color_h1`, `candle_color_m30`, `candle_color_m15`, `candle_color_m5`
  - `bb_m1`, `bb_m5`, `bb_m15`, `bb_m30`, `bb_h1`
- Đồng bộ insert contract cho cả `insert_single_snapshot()` và `batch_insert_snapshots()` với cùng danh sách 32 placeholders (thêm 10 field mới).
- Cập nhật `schema.sql` cho cả `aureus_signal_snapshots` và `aureus_backtest_snapshots` theo additive fields (TEXT cho candle color, JSONB cho BB).
- `live_engine.py` truyền `m1_df` + `digits` vào `build_snapshot(...)` để giữ semantics cadence M1 và hỗ trợ MTF mapping.

## Blast radius (GitNexus impact trước khi sửa)

- `build_snapshot` → **CRITICAL**
  - direct callers: `run_signal_engine`, `precompute_signals`, `backtest_engine.consumer_task`, tests
  - affected processes: 16
- `insert_single_snapshot` → **CRITICAL**
  - direct callers: `_safe_insert_snapshot`, `backtest_engine.consumer_task`
  - affected processes: 14
- `batch_insert_snapshots` → **CRITICAL**
  - direct callers: `precompute_signals`, `recalculate_all_signals`
  - affected processes: 12
- `run_signal_engine` (do có chỉnh callsite) → **MEDIUM**
  - direct dependents: integration tests + `main.py`

Mitigation đã áp dụng: chỉ thêm field mới theo additive contract, không đổi nghĩa field cũ, không đổi trigger/notifier flow.

## Verification

Đã chạy:

1. `PYTHONPATH="D:/Aureus/services/aureus-signal" python -m pytest D:/Aureus/services/aureus-signal/tests/test_snapshot_mtf_fields.py -q`
   - **3 passed**
2. `PYTHONPATH="D:/Aureus/services/aureus-signal" python -m pytest D:/Aureus/services/aureus-signal/tests/test_snapshot_mtf_fields.py D:/Aureus/services/aureus-signal/tests/test_mtf_last_closed_rule.py -q`
   - **6 passed**
3. `PYTHONPATH="D:/Aureus/services/aureus-signal" python -m pytest D:/Aureus/services/aureus-signal/tests/test_snapshot_mtf_fields.py D:/Aureus/services/aureus-signal/tests/test_snapshot_null_policy.py D:/Aureus/services/aureus-signal/tests/test_mtf_candle_color.py D:/Aureus/services/aureus-signal/tests/test_mtf_bb_snapshot.py D:/Aureus/services/aureus-signal/tests/test_mtf_last_closed_rule.py -q`
   - **16 passed**

## Ghi chú về detect_changes

CLI GitNexus hiện tại không có command `detect_changes`; đã dùng `git status --short` để kiểm soát scope thay đổi và xác nhận không chạm ngoài phạm vi plan 02.
