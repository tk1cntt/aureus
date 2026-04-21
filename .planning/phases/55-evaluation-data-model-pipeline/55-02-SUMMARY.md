---
phase: 55-evaluation-data-model-pipeline
plan: 02
subsystem: database
tags: [trader, evaluation, signal-snapshot, order-opened, idempotency]
requires:
  - phase: 55-01
    provides: evaluation/signal snapshot schema and constraints
provides:
  - ORDER_OPENED-bound evaluation persistence with journal lineage
  - ORDER_OPENED-bound signal snapshot persistence with journal lineage
  - regression tests for boundary and optional payload behaviors
affects: [evaluation-ingest, trader-lifecycle, reporting-engine]
tech-stack:
  added: []
  patterns: [persist-only-after-update, on-conflict-idempotency, lineage-first-mapping]
key-files:
  created: []
  modified:
    - services/aureus-trader/journal.py
    - services/aureus-trader/tests/test_evaluation_pipeline.py
    - services/aureus-trader/tests/test_signal_snapshot_pipeline.py
key-decisions:
  - "Chỉ persist evaluation/snapshot sau khi UPDATE journal thành công (UPDATE 1)."
  - "Nếu payload persist không được gửi thì vẫn cập nhật journal; nếu payload được gửi nhưng thiếu core fields thì reject path đó theo test contract."
patterns-established:
  - "ORDER_OPENED là boundary duy nhất cho persist evaluation/snapshot"
  - "Idempotency dùng ON CONFLICT theo (trade_journal_id, version)"
requirements-completed: [EVAL-02, EVAL-04, SIGNAL-SNAPSHOT-01]
duration: 70min
completed: 2026-04-21
---

# Phase 55 Plan 02: Evaluation Runtime Persist Boundary Summary

**Wiring persist evaluation + signal snapshot theo boundary ORDER_OPENED với lineage đầy đủ và idempotency theo version/schema_version.**

## Performance

- **Duration:** 70 min
- **Started:** 2026-04-21T16:xx:xxZ
- **Completed:** 2026-04-21T17:xx:xxZ
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments
- Hoàn tất RED tests cho boundary pre-open/post-open, lineage, payload contract, duplicate replay.
- Implement runtime persist trong `on_order_opened` cho `aureus_trade_evaluations` và `aureus_trade_signal_snapshots`.
- Bổ sung regression đảm bảo luồng journal cũ không bị phá khi event không có payload evaluation/snapshot.

## Task Commits

1. **Task 1: RED integration tests cho boundary + payload/snapshot** - `ed19465` (test)
2. **Task 2: Implement persist evaluation + signal snapshot trong on_order_opened** - `f001146` (feat)
3. **Task 3: Regression subset cho trader lifecycle + evaluation ingest** - `d437457` (test)

## Files Created/Modified
- `D:/Aureus/services/aureus-trader/journal.py` - thêm persist evaluation/snapshot sau ORDER_OPENED, map lineage, và guard payload theo contract.
- `D:/Aureus/services/aureus-trader/tests/test_evaluation_pipeline.py` - RED + regression cho boundary, duplicate, và case thiếu payload evaluation.
- `D:/Aureus/services/aureus-trader/tests/test_signal_snapshot_pipeline.py` - RED + regression cho boundary, duplicate, và case thiếu payload signal snapshot.

## Decisions Made
- Giữ nguyên boundary `dispatch_order` (chỉ trigger tại ORDER_OPENED), không thêm trigger sớm hơn.
- Không persist cột dẫn xuất `ema21_above_ema55`, chỉ lưu `ema21/ema55` + snapshot JSONB.
- Không thay đổi `dispatcher.py` vì boundary hiện tại đã đúng với plan và blast radius CRITICAL được cung cấp.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Guard payload persist theo threat model T-55-05**
- **Found during:** Task 2
- **Issue:** Path persist có thể nhận payload thiếu core fields.
- **Fix:** Chỉ persist khi đủ core fields cho từng path; reject khi payload được gửi nhưng thiếu core bắt buộc.
- **Files modified:** `services/aureus-trader/journal.py`
- **Verification:** `pytest` subset plan 55-02 pass.
- **Committed in:** `f001146`

---

**Total deviations:** 1 auto-fixed (Rule 2)
**Impact on plan:** Cải thiện correctness/security theo threat model, không mở rộng scope kiến trúc.

## Issues Encountered
- `npx gitnexus detect-changes` không tồn tại trong CLI hiện tại (chỉ có subcommands `query/context/impact/...`). Tiếp tục bằng blast radius đã orchestrator cung cấp và giữ scope sửa file đúng plan.

## Next Phase Readiness
- Runtime persist path đã sẵn sàng cho phase reporting/insight downstream.
- Dữ liệu evaluation/snapshot có lineage rõ (`trade_journal_id`, `trace_id`, `ticket`) và idempotent replay.

## Self-Check: PASSED
- FOUND: `D:/Aureus/.planning/phases/55-evaluation-data-model-pipeline/55-02-SUMMARY.md`
- FOUND: `ed19465`
- FOUND: `f001146`
- FOUND: `d437457`
