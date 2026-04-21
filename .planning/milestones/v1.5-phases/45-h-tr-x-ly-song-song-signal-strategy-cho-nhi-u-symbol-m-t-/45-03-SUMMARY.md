---
phase: 45-h-tr-x-ly-song-song-signal-strategy-cho-nhi-u-symbol-m-t-
plan: 03
subsystem: api
tags: [multi-symbol, circuit-breaker, slo, rollout, fallback]

requires:
  - phase: 45-01
    provides: worker/queue nền tảng xử lý song song theo symbol
  - phase: 45-02
    provides: snapshot consistency và trigger safety cho parallel runtime
provides:
  - Per-symbol health manager cho breaker/backlog/SLO rollback
  - Per-symbol rollout mode resolver shadow/canary/full với fallback_serial
  - Test contracts khóa rollback cục bộ và rollout transitions theo symbol
affects: [live-engine, strategy-executor, runtime-safety]

tech-stack:
  added: []
  patterns: [per-symbol isolation, slo hysteresis rollback, rollout state machine]

key-files:
  created:
    - .planning/phases/45-h-tr-x-ly-song-song-signal-strategy-cho-nhi-u-symbol-m-t-/45-03-SUMMARY.md
  modified:
    - services/aureus-signal/engine/symbol_runtime.py
    - services/aureus-signal/engine/live_engine.py
    - services/aureus-signal/engine/strategy_executor.py
    - services/aureus-signal/tests/test_circuit_breaker.py
    - services/aureus-signal/tests/test_symbol_slo_rollback.py
    - services/aureus-signal/tests/test_live_engine_shadow_mode.py

key-decisions:
  - "Giữ rollback phạm vi per-symbol (không rollback global) khi breach SLO liên tiếp."
  - "Khóa rollout modes ở shadow/canary/full, ép fallback_serial bằng hook từ runtime health manager."

patterns-established:
  - "SLO breach 3 phút liên tiếp sẽ hạ symbol về fallback_serial."
  - "Hysteresis recovery yêu cầu 5 phút liên tiếp dưới 50% ngưỡng trước khi mở lại parallel."

requirements-completed: [PH45-06, PH45-07]

duration: 0 min
completed: 2026-04-18
---

# Phase 45 Plan 03: Per-symbol safety rollout Summary

**Per-symbol breaker/backlog/SLO guards with staged shadow→canary→full rollout and isolated fallback rollback per violating symbol.**

## Performance

- **Duration:** 0 min
- **Started:** 2026-04-18T10:28:57Z
- **Completed:** 2026-04-18T10:29:27Z
- **Tasks:** 3
- **Files modified:** 7

## Accomplishments
- Hoàn thành runtime health manager per-symbol với SLO thresholds + hysteresis rollback/recovery.
- Hoàn thành rollout mode resolver per-symbol cho shadow/canary/full và fallback hook khi breach.
- Hoàn tất checkpoint human-verify: user xác nhận staging rollout bằng phản hồi `approved`.

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement per-symbol breaker/backlog/SLO rollback contracts + runtime** - `a5c14a5` (feat)
2. **Task 2: Wire rollout Shadow→Canary→Full theo symbol với auto rollback hooks** - `26e365e` (feat)
3. **Task 3: Xác nhận rollout vận hành thực tế trên môi trường staging** - `approved by user` (checkpoint)

**Plan metadata:** pending

## Files Created/Modified
- `services/aureus-signal/engine/symbol_runtime.py` - quản lý state per-symbol cho breaker/backlog/SLO/fallback.
- `services/aureus-signal/engine/live_engine.py` - resolve rollout mode theo symbol + fallback behavior.
- `services/aureus-signal/engine/strategy_executor.py` - wiring để rollback chỉ ảnh hưởng symbol vi phạm.
- `services/aureus-signal/tests/test_circuit_breaker.py` - test contract isolation breaker/backlog theo symbol.
- `services/aureus-signal/tests/test_symbol_slo_rollback.py` - test rollback/recovery theo SLO consecutive breaches.
- `services/aureus-signal/tests/test_live_engine_shadow_mode.py` - test transitions shadow/canary/full + fallback_serial.

## Decisions Made
- Duy trì phạm vi bảo vệ/rollback theo từng symbol để tránh global kill-switch behavior.
- Chuẩn hóa machine state rollout với mode whitelist (shadow/canary/full) và transition sang fallback_serial chỉ qua guard breach.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Local verification environment thiếu pytest**
- **Found during:** Task 3 checkpoint verification rerun
- **Issue:** Lệnh verify tự động trả về `No module named pytest` trên môi trường hiện tại.
- **Fix:** Không thay đổi code; tiếp tục theo checkpoint flow vì user đã xác nhận staging `approved`.
- **Files modified:** None
- **Verification:** Checkpoint human-verify accepted by user response.
- **Committed in:** N/A (checkpoint approval)

---

**Total deviations:** 1 auto-handled (1 blocking environment)
**Impact on plan:** Không ảnh hưởng phạm vi implementation; xác nhận staging từ user vẫn hoàn thành tiêu chí checkpoint.

## Authentication Gates
None.

## Issues Encountered
- Môi trường cục bộ hiện tại không có pytest, nên không thể re-run test tại bước continuation checkpoint.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 45 đã đủ 3/3 plans có summary sau khi commit metadata plan này.
- Hệ thống sẵn sàng cho quy trình verify-work/milestone completion.

## Self-Check: PASSED
- FOUND: D:/Aureus/.planning/phases/45-h-tr-x-ly-song-song-signal-strategy-cho-nhi-u-symbol-m-t-/45-03-SUMMARY.md
- FOUND: a5c14a5
- FOUND: 26e365e
- Note: `npx gitnexus detect_changes` command is unavailable in current CLI build; scope check performed via commit file inspection and plan file mapping.
