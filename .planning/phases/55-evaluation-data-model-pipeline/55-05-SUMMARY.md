---
phase: 55
plan: 05
subsystem: aureus-db-writer,aureus-trader
tags: [runtime-parity, migration-compatibility, recompute, verification]
requires: [55-01, 55-02, 55-03, 55-04]
provides: [EVAL-01, EVAL-02, EVAL-03, EVAL-04, SIGNAL-SNAPSHOT-01, EVAL-RUNTIME-01, EVAL-RUNTIME-02, EVAL-RUNTIME-03, EVAL-RUNTIME-04]
affects:
  - services/aureus-db-writer/migrations/add_trade_evaluations.sql
  - services/aureus-db-writer/tests/test_evaluation_migration.py
  - services/aureus-trader/tests/test_signal_snapshot_migration.py
  - services/aureus-trader/recompute_evaluations.py
  - RUN_SERVICES.md
tech_stack:
  added: []
  patterns: [runtime-schema-gate, compatibility-safe-check-constraints, e2e-runtime-sql-evidence]
metrics:
  completed_at: 2026-04-22
  tasks_completed: 3
  files_changed: 5
---

# Phase 55 Plan 05: Runtime Parity Hardening Summary

Đã triển khai plan 55-05 để xử lý triệt để gap giữa test-pass và runtime DB readiness cho phase 55.

## Completed Tasks

1. **Task 1 — Compatibility-safe JSONB constraints**
   - Chuẩn hóa CHECK constraints trong migration để tương thích runtime PG hiện tại:
     - `jsonb_typeof(...) = 'object'`
     - `... <> '{}'::jsonb`
   - Cập nhật migration tests tương ứng.

2. **Task 2 — Recompute timeframe bridge ổn định runtime**
   - Loại bỏ phụ thuộc vào cột không tồn tại `j.timeframe` trong `aureus_trade_journal`.
   - Dùng bridge deterministic:
     - `COALESCE(ss.signal_snapshot->>'timeframe', 'M1') AS timeframe`
   - Gắn TODO follow-up để chuyển về canonical lineage column.

3. **Task 3 — Runtime sign-off evidence gate**
   - Bổ sung checklist runtime vào `RUN_SERVICES.md`.
   - Thu thập bằng chứng SQL runtime đầy đủ: bảng/index/count/latest rows.

## Verification

### Automated tests
- `python3 -m pytest services/aureus-db-writer/tests/test_evaluation_migration.py services/aureus-trader/tests/test_signal_snapshot_migration.py services/aureus-trader/tests/test_evaluation_recompute.py services/aureus-trader/tests/test_signal_snapshot_recompute.py -q`
  - **Result:** `15 passed`
- `python3 -m pytest services/aureus-trader/tests/test_evaluation_recompute.py services/aureus-trader/tests/test_signal_snapshot_recompute.py -q`
  - **Result:** `4 passed`

### Runtime SQL evidence (aureus_timescaledb_dev)
- Table existence:
  - `aureus_trade_evaluations`
  - `aureus_trade_signal_snapshots`
- Index evidence:
  - `idx_trade_eval_symbol_tf_eval_at`
  - `idx_trade_eval_current_symbol_tf_eval_at`
  - `idx_trade_signal_snapshot_symbol_tf_created_at`
  - `idx_trade_signal_snapshot_symbol_tf_cisd_created_at`
  - `idx_trade_signal_snapshot_created_at_brin`
  - cùng các PK/UNIQUE index tương ứng
- Data evidence:
  - `aureus_trade_evaluations`: `26 rows`, `MAX(evaluated_at)=2026-04-22 02:27:03.479902+00`
  - `aureus_trade_signal_snapshots`: `26 rows`, `MAX(created_at)=2026-04-22 02:27:03.521261+00`
  - Có sample 5 rows mới nhất cho cả hai bảng với `trace_id/symbol/timeframe/version`.

## Deviations / Notes

- Lúc apply migration ban đầu phát hiện incompatibility:
  - `jsonb_object_length` không tồn tại trên runtime DB hiện tại.
  - `EXISTS (SELECT...)` không hợp lệ trong CHECK constraint.
- Đã chốt biểu thức CHECK tương thích thay thế như trên.

## Risks & Follow-up

- `timeframe` hiện vẫn bridge từ snapshot (`COALESCE(..., 'M1')`) — đây là giải pháp tạm thời để không block runtime.
- Follow-up bắt buộc: bổ sung canonical lineage `timeframe` trong `aureus_trade_journal` để loại bỏ fallback JSON.

## Success Criteria Check

- [x] Migration phase 55 apply được trên runtime DB dev không lỗi compatibility.
- [x] Recompute phase 55 chạy thực tế và persist dữ liệu vào 2 bảng mục tiêu.
- [x] Sign-off có bằng chứng runtime đầy đủ (schema + indexes + rows), không chỉ test output.
