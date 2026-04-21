---
phase: 46-strategy-seed-sync
plan: 02
subsystem: testing
tags: [seed-sync, rollback, dry-run, strategy, operations]
requires:
  - phase: 46-01
    provides: seed sync active/inactive semantics and startup/reload ordering
provides:
  - regression tests for seed sync, reload order, active-only load, and runbook contract
  - dry-run CLI preview for strategy seed sync diffs
  - rollback CLI to restore aureus_symbol_strategies.is_active from snapshot JSON
  - concise rollback runbook for operators
affects: [signal-engine, strategy-executor, operations, phase-46]
tech-stack:
  added: []
  patterns: [snapshot-json-rollback, dry-run-without-db-mutation, runbook-contract-test]
key-files:
  created:
    - services/aureus-signal/scripts/strategy_seed_sync_dryrun.py
    - services/aureus-signal/scripts/strategy_seed_sync_rollback.py
    - .planning/phases/46-strategy-seed-sync/46-ROLLBACK-RUNBOOK.md
  modified:
    - services/aureus-signal/tests/test_strategy_seed_sync.py
key-decisions:
  - "Dùng snapshot JSON file theo timestamp trong services/aureus-signal/scripts/snapshots thay vì bảng tạm DB."
  - "Rollback bắt buộc validate schema symbol/strategy_id/is_active và hỗ trợ preview mặc định, chỉ apply khi có --apply."
patterns-established:
  - "Seed sync rollout flow: dry-run -> apply seed -> refresh -> rollback preview/apply khi cần"
requirements-completed: [PH46-04, PH46-05]
duration: 55min
completed: 2026-04-19
---

# Phase 46 Plan 02: Strategy Seed Sync Summary

**Bổ sung bộ công cụ dry-run/rollback và regression tests để rollout strategy seed sync có thể preview, apply, và rollback an toàn theo command chuẩn.**

## Performance

- **Duration:** 55 min
- **Started:** 2026-04-19T07:31:00Z
- **Completed:** 2026-04-19T08:26:00Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments
- Khóa behavior cốt lõi seed sync bằng test regression (idempotent/deactivate/reactivate/order/active-only).
- Thêm `strategy_seed_sync_dryrun.py` và `strategy_seed_sync_rollback.py` với CLI contract rõ ràng.
- Tạo rollback runbook 3 luồng và test contract để đảm bảo command bắt buộc luôn hiện diện.

## Task Commits

1. **Task 1: Hoàn thiện regression tests cho sync + reload + rollback semantics** - `eaf6986` (test)
2. **Task 2: Tạo công cụ dry-run và rollback executable cho operator** - `adf1b7d` (feat)
3. **Task 3: Viết rollback runbook ngắn gọn gắn trực tiếp với command thật** - `fb7d640` (docs)

## Files Created/Modified
- `/d/Aureus/services/aureus-signal/tests/test_strategy_seed_sync.py` - Regression tests + runbook contract.
- `/d/Aureus/services/aureus-signal/scripts/strategy_seed_sync_dryrun.py` - Dry-run preview không mutate DB, xuất diff JSON.
- `/d/Aureus/services/aureus-signal/scripts/strategy_seed_sync_rollback.py` - Rollback preview/apply từ snapshot JSON.
- `/d/Aureus/.planning/phases/46-strategy-seed-sync/46-ROLLBACK-RUNBOOK.md` - Checklist vận hành pre-check/rollout/rollback.

## Decisions Made
- Dùng transaction rollback cho dry-run để bảo đảm không đổi trạng thái DB khi preview (mitigate T-46-02-03).
- Dùng `--apply` làm cờ bắt buộc để ngăn rollback nhầm trong chế độ preview (mitigate T-46-02-01).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Sửa import path cho script CLI chạy trực tiếp**
- **Found during:** Task 2
- **Issue:** Script chạy `python services/.../strategy_seed_sync_dryrun.py --help` bị `ModuleNotFoundError: No module named 'engine'`.
- **Fix:** Thêm `sys.path` bootstrap từ thư mục service trước khi import `engine.strategies.seed_strategies`.
- **Files modified:** `services/aureus-signal/scripts/strategy_seed_sync_dryrun.py`
- **Verification:** `--help` của cả 2 scripts chạy thành công.
- **Committed in:** `adf1b7d`

**2. [Rule 3 - Blocking] Sửa path runbook trong test contract**
- **Found during:** Task 3
- **Issue:** Test dùng đường dẫn tuyệt đối `/d/Aureus/...` gây fail trong pytest context.
- **Fix:** Tính repo root từ `Path(__file__).resolve().parents[3]` và ghép path tương đối.
- **Files modified:** `services/aureus-signal/tests/test_strategy_seed_sync.py`
- **Verification:** `pytest -k runbook_contract` pass.
- **Committed in:** `fb7d640`

---

**Total deviations:** 2 auto-fixed (2 blocking)
**Impact on plan:** Không scope creep, chỉ bổ sung sửa tối thiểu để đạt verify bắt buộc.

## Issues Encountered
- `gitnexus detect_changes` không có subcommand trong CLI hiện tại; fallback bằng `git diff --name-only --cached` trước commit.

## Known Stubs
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Đã sẵn sàng flow vận hành: dry-run -> rollout -> verify -> rollback.
- Không còn blocker kỹ thuật cho phase 46.

## Self-Check: PASSED
- FOUND: /d/Aureus/.planning/phases/46-strategy-seed-sync/46-02-SUMMARY.md
- FOUND: eaf6986
- FOUND: adf1b7d
- FOUND: fb7d640
