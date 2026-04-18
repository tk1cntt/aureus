---
phase: 45-h-tr-x-ly-song-song-signal-strategy-cho-nhi-u-symbol-m-t-
plan: 01
subsystem: testing
tags: [asyncio, redis-streams, per-symbol-worker, fifo, out-of-order]
requires: []
provides:
  - Contract test cho isolation đa symbol, FIFO per-symbol và drop+ack out-of-order
  - Runtime primitive per-symbol worker queue với guard `ts_unix <= last_executed_candle_t`
  - Adapter helper trong live_engine để chuẩn hóa work item cho router/worker
affects: [signal-engine, multi-symbol-runtime, phase-45-02]
tech-stack:
  added: []
  patterns: [tdd-red-green, per-symbol-worker-runtime, strict-fifo-per-symbol]
key-files:
  created:
    - services/aureus-signal/tests/test_per_symbol_worker_runtime.py
    - services/aureus-signal/tests/test_out_of_order_drop_policy.py
    - services/aureus-signal/engine/symbol_runtime.py
  modified:
    - services/aureus-signal/engine/live_engine.py
key-decisions:
  - "Giữ thay đổi live_engine ở mức adapter tối thiểu, dồn core worker lifecycle vào symbol_runtime để giảm blast radius."
  - "Áp dụng guard out-of-order ngay trong worker runtime bằng điều kiện <= và gọi ack callback ngay khi drop."
patterns-established:
  - "Pattern: PerSymbolWorkerRuntime quản lý queue/task theo symbol và xử lý FIFO strict theo queue order."
  - "Pattern: Test contract tách riêng behavior isolation/FIFO và behavior drop+ack out-of-order."
requirements-completed: [PH45-01, PH45-02, PH45-03]
duration: 7min
completed: 2026-04-18
---

# Phase 45 Plan 01: Per-symbol Worker Runtime Summary

**Runtime per-symbol worker queue cho signal engine được khóa bằng TDD contracts về isolation đa symbol, FIFO strict và out-of-order drop+ack.**

## Performance

- **Duration:** 7 min
- **Started:** 2026-04-18T09:07:46Z
- **Completed:** 2026-04-18T09:14:29Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Thêm test contracts cho behavior song song per-symbol và FIFO strict theo từng symbol.
- Thêm test dedicated cho policy drop+ack khi candle out-of-order (`ts_unix <= last_executed_candle_t`).
- Triển khai `PerSymbolWorkerRuntime` và `CandleWorkItem` để quản lý worker lifecycle/queue per-symbol.
- Cập nhật `live_engine.py` với helper `build_symbol_work_item(...)` để chuẩn hóa payload routing.

## Task Commits

1. **Task 1: Tạo test contracts cho per-symbol worker runtime** - `1b5af22` (test)
2. **Task 2: Implement signal router + per-symbol worker queue** - `c40c016` (feat)

## Files Created/Modified
- `/d/Aureus/services/aureus-signal/tests/test_per_symbol_worker_runtime.py` - Contract tests cho isolation đa symbol và FIFO per-symbol.
- `/d/Aureus/services/aureus-signal/tests/test_out_of_order_drop_policy.py` - Contract test cho drop+ack out-of-order.
- `/d/Aureus/services/aureus-signal/engine/symbol_runtime.py` - Runtime primitive cho queue/task per-symbol + guard drop out-of-order.
- `/d/Aureus/services/aureus-signal/engine/live_engine.py` - Helper build work item cho router/worker adapter.

## Decisions Made
- Giữ chỉnh sửa `live_engine.py` tối thiểu để giảm rủi ro từ blast radius CRITICAL của các symbol lõi (`execute_signals_for_candle`, `recalculate_all_signals`).
- Dùng callback `ack` trong `CandleWorkItem` để đảm bảo policy drop vẫn ack đúng trong runtime contract.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Khắc phục môi trường test host thiếu pytest**
- **Found during:** Task 1
- **Issue:** `python3 -m pytest` trên host lỗi `No module named pytest`.
- **Fix:** Chạy test theo runbook trong `RUN_SERVICES.md` bằng `wsl -d Aureus ... ./.venv/bin/python -m pytest ...`.
- **Files modified:** none
- **Verification:** Test RED fail đúng vì thiếu module runtime (`engine.symbol_runtime`) thay vì lỗi môi trường.
- **Committed in:** `1b5af22` (task commit context)

**2. [Rule 1 - Bug] Rollback patch trung gian làm hỏng `live_engine.py` trước khi chốt thay đổi tối giản**
- **Found during:** Task 2
- **Issue:** Một patch thử nghiệm để nhúng worker vào loop đã chèn rác text vào file.
- **Fix:** `git checkout -- services/aureus-signal/engine/live_engine.py`, sau đó áp dụng lại patch nhỏ theo scope plan.
- **Files modified:** `services/aureus-signal/engine/live_engine.py`
- **Verification:** Bộ test verify của plan pass hoàn toàn.
- **Committed in:** `c40c016`

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 bug)
**Impact on plan:** Không scope creep; đều là xử lý cần thiết để hoàn tất TDD và giữ code an toàn.

## Issues Encountered
- CLI GitNexus hiện tại không có lệnh `detect_changes`; đã thay bằng kiểm soát phạm vi qua `git diff --cached --name-only` và impact analysis trước sửa symbol theo yêu cầu CLAUDE.md.

## Known Stubs
None.

## Next Phase Readiness
- Plan 45-01 đã có contract và runtime primitive làm nền cho bước wire router sâu hơn ở plan tiếp theo.
- Không có blocker kỹ thuật còn mở trong phạm vi plan 45-01.

## Self-Check: PASSED
- FOUND: /d/Aureus/.planning/phases/45-h-tr-x-ly-song-song-signal-strategy-cho-nhi-u-symbol-m-t-/45-01-SUMMARY.md
- FOUND: 1b5af22
- FOUND: c40c016
