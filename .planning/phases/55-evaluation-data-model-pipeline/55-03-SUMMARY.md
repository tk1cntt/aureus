---
phase: 55
plan: 03
subsystem: aureus-trader
tags: [evaluation, recompute, signal-snapshot, tdd]
requires: [55-01, 55-02]
provides: [EVAL-03, SIGNAL-SNAPSHOT-01]
affects:
  - services/aureus-trader/recompute_evaluations.py
  - services/aureus-trader/tests/test_evaluation_recompute.py
  - services/aureus-trader/tests/test_signal_snapshot_recompute.py
tech_stack:
  added: []
  patterns: [append-only version history, on-conflict idempotency, WSL-venv pytest]
decisions:
  - Recompute append row mới theo (trade_journal_id, score_version/signal_schema_version), không overwrite version cũ.
  - Chỉ flip is_current khi insert evaluation mới thành công để đảm bảo idempotent rerun.
metrics:
  completed_at: 2026-04-21
  duration: "~30m"
  tasks_completed: 3
  files_changed: 3
---

# Phase 55 Plan 03: Recompute Pipeline Summary

Triển khai recompute/backfill cho evaluation + signal snapshot theo version với cơ chế append-only, idempotent khi rerun cùng version và giữ nguyên lịch sử cũ.

## Completed Tasks

1. RED tests cho recompute history/idempotency (evaluation + signal snapshot).
2. GREEN implementation script `recompute_evaluations.py` theo batch window, score_version, signal_schema_version.
3. Verification full subset cho migration/pipeline/recompute phase scope.

## Commits theo task

- Task 1: `1153963` — `test(55-03): add failing recompute contracts for evaluation and signal snapshots`
- Task 2: `2ef41b2` — `feat(55-03): add batch recompute script for versioned evaluations and snapshots`
- Task 3: Không commit (verification-only, không thay đổi file)

## Verification

- `wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus && ./.venv/bin/python -m pytest services/aureus-trader/tests/test_evaluation_recompute.py services/aureus-trader/tests/test_signal_snapshot_recompute.py -q"` → exit code `2` (RED expected: thiếu module trước khi implement)
- `wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus && ./.venv/bin/python -m pytest services/aureus-trader/tests/test_evaluation_recompute.py services/aureus-trader/tests/test_signal_snapshot_recompute.py services/aureus-trader/tests/test_evaluation_pipeline.py services/aureus-trader/tests/test_signal_snapshot_pipeline.py -q"` → exit code `0`
- `wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus && ./.venv/bin/python -m pytest services/aureus-db-writer/tests/test_evaluation_migration.py services/aureus-trader/tests/test_signal_snapshot_migration.py services/aureus-trader/tests/test_evaluation_pipeline.py services/aureus-trader/tests/test_signal_snapshot_pipeline.py services/aureus-trader/tests/test_evaluation_recompute.py services/aureus-trader/tests/test_signal_snapshot_recompute.py -q"` → exit code `0`

## Deviations from Plan

### Auto-fixed Issues

1. [Rule 3 - Blocking issue] GitNexus index stale và `gitnexus analyze` không chạy được do EPERM trên `D:/Aureus/CLAUDE.md`.
   - Found during: pre-task setup
   - Handling: vẫn chạy được `gitnexus impact` cho symbol hiện hữu (`on_order_opened`), tiếp tục thực thi task trong phạm vi plan.

2. [Rule 3 - Tooling mismatch] GitNexus CLI bản hiện tại không hỗ trợ `detect_changes` command.
   - Found during: pre-commit check
   - Handling: thay thế bằng kiểm tra scope qua `git diff --staged --name-only` để đảm bảo commit đúng file kế hoạch.

## Blast Radius (GitNexus impact)

- Target: `on_order_opened` (`services/aureus-trader/journal.py`)
- Risk: `CRITICAL`
- Direct callers (d=1): `dispatch_order`
- Indirect (d=2/d=3): `dispatch_loop`, `run_trader`
- Affected processes: 5 luồng trong trader runtime
- Action: Không sửa symbol này trong plan 55-03; implement script mới tách biệt để tránh tác động runtime hiện hữu.

## Known Stubs

None.

## Threat Flags

None.

## Self-Check: PASSED

- FOUND: `D:/Aureus/services/aureus-trader/recompute_evaluations.py`
- FOUND: `D:/Aureus/services/aureus-trader/tests/test_evaluation_recompute.py`
- FOUND: `D:/Aureus/services/aureus-trader/tests/test_signal_snapshot_recompute.py`
- FOUND: `D:/Aureus/.planning/phases/55-evaluation-data-model-pipeline/55-03-SUMMARY.md`
- FOUND commits: `1153963`, `2ef41b2`
