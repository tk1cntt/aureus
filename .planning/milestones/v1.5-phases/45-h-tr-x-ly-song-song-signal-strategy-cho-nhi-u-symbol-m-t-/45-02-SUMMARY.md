---
phase: 45-h-tr-x-ly-song-song-signal-strategy-cho-nhi-u-symbol-m-t-
plan: 02
subsystem: testing
tags: [strategy-executor, snapshot-consistency, trace-id, dedupe, tdd]
requires:
  - phase: 45-01
    provides: PerSymbolWorkerRuntime và contract nền cho routing/queue đa symbol
provides:
  - Contract test D-07 cho snapshot cùng candle trước strategy evaluation
  - Contract test D-08 cho trace_id strict và replay dedupe trong orders
  - Runtime gate trong strategy executor để reject+ack payload lệch candle
affects: [signal-engine, strategy-executor, orders, phase-45-03]
tech-stack:
  added: []
  patterns: [tdd-red-green, snapshot-consistency-gate, strict-trace-id-dedupe]
key-files:
  created: []
  modified:
    - services/aureus-signal/tests/test_strategy_trigger_lifecycle.py
    - services/aureus-signal/unittest/test_orders_events.py
    - services/aureus-signal/engine/strategy_executor.py
key-decisions:
  - "Thêm gate validate snapshot ngay đầu xử lý từng stream entry để reject sớm và xack tránh treo queue."
  - "Giữ trace_id format hiện tại symbol:strategy_id:origin_timestamp và khóa bằng test replay dedupe strict."
patterns-established:
  - "Pattern: validate_snapshot_candle_consistency(payload) trả (is_valid, reason) để dùng lại trong runtime gate."
  - "Pattern: test D-08 kiểm tra vừa format trace_id vừa replay không phát sinh ORDER_OPEN mới."
requirements-completed: [PH45-04, PH45-05]
duration: 5min
completed: 2026-04-18
---

# Phase 45 Plan 02: Strategy Snapshot/Trace Consistency Summary

**Strategy executor được khóa consistency snapshot cùng candle và idempotency trace_id strict để ngăn trigger/order sai khi replay hoặc payload lệch thời điểm.**

## Performance

- **Duration:** 5 min
- **Started:** 2026-04-18T09:27:40Z
- **Completed:** 2026-04-18T09:32:11Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Viết test RED cho D-07: payload mismatch giữa `t` candle và snapshot bị reject với reason rõ ràng.
- Viết test RED cho D-08: trace_id theo format `symbol:strategy_id:origin_timestamp` và replay không tạo thêm order event.
- Implement runtime gate trong `strategy_executor.py` để reject + `xack` entry lệch candle trước evaluate/process_triggers.

## Task Commits

1. **Task 1: Viết test consistency snapshot-cùng-candle và trace_id strict** - `ca142d7` (test)
2. **Task 2: Implement strategy executor per-symbol worker + strict trace lifecycle** - `251d13a` (feat)

## Files Created/Modified
- `/d/Aureus/services/aureus-signal/tests/test_strategy_trigger_lifecycle.py` - Thêm contract test mismatch candle cho snapshot gate D-07.
- `/d/Aureus/services/aureus-signal/unittest/test_orders_events.py` - Thêm contract test format trace_id và replay dedupe D-08.
- `/d/Aureus/services/aureus-signal/engine/strategy_executor.py` - Thêm `validate_snapshot_candle_consistency(...)` và runtime reject+ack gate.

## Decisions Made
- Đặt consistency gate ngay sau `json.loads(payload_raw)` để fail fast trước khi dựng state/evaluate.
- Không đổi schema event downstream (`type` + `data`) và không đụng fallback direction logic để giữ compatibility phase 36.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Chạy pytest host thất bại do path WSL sai**
- **Found during:** Task 1
- **Issue:** Lệnh verify dùng `/d/Aureus` trong WSL gây `No such file or directory`.
- **Fix:** Đổi sang mount path `/mnt/d/Aureus` để chạy đúng virtualenv test.
- **Files modified:** none
- **Verification:** Pytest chạy đúng và trả RED theo expected missing symbol.
- **Committed in:** `ca142d7` (task context)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Không scope creep; chỉ sửa môi trường chạy verify để hoàn tất TDD.

## Issues Encountered
- GitNexus CLI hiện tại không có command `detect_changes`; thay bằng kiểm soát phạm vi staged qua `git diff --cached --name-only` và vẫn giữ bắt buộc impact analysis trước sửa symbol.

## Next Phase Readiness
- D-07/D-08 đã được khóa bằng test + runtime gate, sẵn sàng mở rộng routing/per-symbol strategy worker sâu hơn ở plan 45-03.
- Không còn blocker kỹ thuật trong phạm vi plan 45-02.

## Self-Check: PASSED
- FOUND: /d/Aureus/.planning/phases/45-h-tr-x-ly-song-song-signal-strategy-cho-nhi-u-symbol-m-t-/45-02-SUMMARY.md
- FOUND: ca142d7
- FOUND: 251d13a
