---
phase: 55-evaluation-data-model-pipeline
plan: 04
subsystem: database
tags: [timescaledb, migration, runtime-verification, pytest, trade-journal]
requires:
  - phase: 55-01
    provides: migration schema nền cho evaluations/signal snapshots
  - phase: 55-02
    provides: pipeline persist dữ liệu evaluation/snapshot
  - phase: 55-03
    provides: test coverage cho pipeline phase 55
provides:
  - Migration parity tests bắt buộc cho 2 bảng phase 55
  - Runtime DB verification gate trong runbook/dev-service flow
  - E2E evidence persistence thật cho evaluation + signal snapshot theo trace_id
affects: [phase-55-signoff, evaluation-pipeline, ops-runbook]
tech-stack:
  added: []
  patterns: [schema-parity-test-gate, runtime-db-proof-before-signoff]
key-files:
  created: [.planning/phases/55-evaluation-data-model-pipeline/55-04-SUMMARY.md]
  modified:
    - services/aureus-db-writer/tests/test_evaluation_migration.py
    - services/aureus-trader/tests/test_signal_snapshot_migration.py
    - RUN_SERVICES.md
    - scripts/dev-service.sh
    - services/aureus-trader/journal.py
key-decisions:
  - "Dùng query + impact CLI GitNexus làm phương án tương đương detect_changes vì bản CLI hiện tại không có command detect_changes."
  - "Bổ sung guard trade_journal_id trong on_order_opened để tránh lỗi FK/null khi persist runtime payload."
patterns-established:
  - "Schema phase 55 phải được verify ở cả migration test và runtime DB."
  - "Sign-off phase DB bắt buộc có evidence row mới theo trace_id trong DB thật."
requirements-completed: [EVAL-01, EVAL-02, SIGNAL-SNAPSHOT-01]
duration: 24min
completed: 2026-04-22
---

# Phase 55 Plan 04: Runtime Schema & Persistence Verification Summary

**Thiết lập gate xác minh runtime DB cho phase 55 bằng test parity schema, runbook kiểm tra production-like và bằng chứng persist thật theo trace_id.**

## Performance

- **Duration:** 24 min
- **Started:** 2026-04-22T17:25:36Z
- **Completed:** 2026-04-22T17:49:36Z
- **Tasks:** 3/3
- **Files modified:** 5

## Accomplishments
- Siết migration tests để fail ngay khi thiếu bảng/index/constraint JSONB của phase 55.
- Thêm runtime DB gate trong `RUN_SERVICES.md` và `scripts/dev-service.sh` để kiểm tra schema + dữ liệu mới nhất sau restart.
- Xác nhận E2E persistence thật bằng payload `ORDER_OPENED` có scoring + signal snapshot, verify được row mới ở cả `aureus_trade_evaluations` và `aureus_trade_signal_snapshots`.

## Task Commits

1. **Task 1: Bổ sung verification test cho runtime schema parity** - `aa07291` (test)
2. **Task 2: Add runtime DB verification gate trong runbook** - `639ad72` (chore)
3. **Task 3: End-to-end persistence verification and sign-off** - `fbc1266` (fix)

## Files Created/Modified
- `D:/Aureus/services/aureus-db-writer/tests/test_evaluation_migration.py` - Thêm assert tồn tại 2 bảng phase 55, shape index/partial-index và JSONB check constraints.
- `D:/Aureus/services/aureus-trader/tests/test_signal_snapshot_migration.py` - Thêm assert unique constraint + shape index BRIN/composite + tồn tại đủ 2 bảng.
- `D:/Aureus/RUN_SERVICES.md` - Bổ sung lệnh count + latest rows để verify runtime persistence.
- `D:/Aureus/scripts/dev-service.sh` - Thêm bước verify tồn tại 2 bảng phase 55 ngay sau startup dev services.
- `D:/Aureus/services/aureus-trader/journal.py` - Guard persist evaluation/snapshot khi thiếu `trade_journal_id` để tránh lỗi runtime DB.

## Decisions Made
- Không có `gitnexus_detect_changes` trong CLI hiện tại (`npx gitnexus` chỉ có `query/context/impact/cypher`), nên dùng `gitnexus query` kết hợp staged file check (`git diff --cached --name-only`) làm scope check tương đương trước mỗi commit task.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Ngăn persist lỗi khi thiếu trade_journal_id trong on_order_opened**
- **Found during:** Task 3
- **Issue:** Luồng runtime có thể gọi insert evaluation/snapshot với `trade_journal_id=None` khi fetch journal row không trả dữ liệu, gây lỗi DB và cản trở verify e2e.
- **Fix:** Thêm guard chỉ persist khi `trade_journal_id` hợp lệ; nếu thiếu thì warning và vẫn giữ update journal flow.
- **Files modified:** `services/aureus-trader/journal.py`
- **Verification:** `71 passed` cho bộ test pipeline + journal và verify runtime DB row mới theo trace_id.
- **Committed in:** `fbc1266`

---

**Total deviations:** 1 auto-fixed (Rule 1)
**Impact on plan:** Auto-fix cần thiết để đảm bảo runtime persistence verification không false-negative do lỗi FK/null.

## Auth Gates
None.

## Issues Encountered
- Chạy script verify runtime đầu tiên lỗi do quoting/heredoc và credential DB; đã chuyển sang script file tạm với credential đúng (`aureus_password`) để hoàn tất verify DB thật.

## Known Stubs
None.

## Next Phase Readiness
- Phase 55-04 đã có cả bằng chứng test và runtime DB thực tế.
- Có thể tiếp tục plan 55-06 với confidence cao hơn về schema/runtime parity của evaluation pipeline.
