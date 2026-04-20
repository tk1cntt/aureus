---
phase: 49-order-execution-contract-multi-symbol
plan: 02
subsystem: api
tags: [redis-stream, multi-symbol, execution-policy, nautilus]

requires:
  - phase: 49-01
    provides: ORDER_OPEN contract baseline and qty semantics compatibility
provides:
  - Multi-symbol stream discovery without implicit XAUUSD stream injection
  - Stream/payload symbol mismatch guard with stable reason code SYMBOL_STREAM_MISMATCH
  - Regression contract tests for per-stream cursor independence
affects: [execution-client, order-routing, ph45-06]

tech-stack:
  added: []
  patterns: [per-stream last_id cursor, explicit env validation, stream-symbol consistency guard]

key-files:
  created:
    - services/aureus-nautilus-node/tests/test_execution_client_policy.py
    - services/aureus-nautilus-node/tests/test_execution_multi_symbol_contract.py
  modified:
    - services/aureus-nautilus-node/settings.py
    - services/aureus-nautilus-node/execution_client.py
    - services/aureus-nautilus-node/tests/test_config_validation.py

key-decisions:
  - "Reject missing whitelist env via validation instead of silently defaulting to singleton symbol."
  - "Discover and poll only actual Redis order streams that match whitelist, sorted deterministically by stream key."
  - "Treat stream/payload symbol mismatch as hard reject with SYMBOL_STREAM_MISMATCH and dedicated metric counter."

patterns-established:
  - "Execution consume path derives symbol from stream key and verifies payload symbol alignment before order generation."
  - "Multi-stream polling keeps independent last_id cursor per stream to preserve fairness and deterministic progress."

requirements-completed: [ORDER-01, PH45-06]

duration: 55min
completed: 2026-04-20
---

# Phase 49 Plan 02: Multi-symbol execution stream contract Summary

**Execution client poll runtime chuyển sang discover multi-stream thực tế theo whitelist và khóa reject mismatch symbol giữa stream/payload bằng reason code ổn định.**

## Performance

- **Duration:** 55 min
- **Started:** 2026-04-20T15:55:00Z
- **Completed:** 2026-04-20T16:50:00Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Loại bỏ default/fallback singleton `XAUUSD` trong `NautilusNodeSettings.from_env` bằng yêu cầu whitelist env hợp lệ.
- Loại bỏ hardcode stream poll singleton, thêm `_discover_order_streams` + `_extract_stream_symbol`, và giữ stream map deterministic.
- Khóa guard `SYMBOL_STREAM_MISMATCH` trên path consume + bổ sung test contract chứng minh cursor per-stream độc lập cho >=2 symbols.

## Blast Radius (GitNexus impact)

- `from_env`: risk **LOW**, impactedCount=0.
- `_discover_order_streams`: risk **CRITICAL**, direct callers `_poll_loop`, `_poll_orders_once`; indirect `connect`; ảnh hưởng execution flows poll/validate/reject.
- `_poll_loop`, `_poll_orders_once`, `_handle_message`, `_validate_and_build_orders`: risk **CRITICAL**; thay đổi đã được giới hạn trong execution client path và có regression tests trực tiếp.
- `_build_policy`: risk **LOW**, direct caller `__init__`.

## Task Commits

Each task was committed atomically (TDD RED/GREEN):

1. **Task 1: Chuẩn hóa settings multi-symbol, bỏ default singleton XAUUSD**
   - `a335b73` (test) — failing tests cho whitelist env và stream policy
   - `30e970f` (feat) — implement multi-stream discovery + mismatch guard + bỏ default XAUUSD ở settings
2. **Task 2: Khóa guard mismatch + test contract mới**
   - `d8cd6b8` (test) — failing contract tests multi-symbol mới
   - `9236af1` (feat) — remove fallback singleton trong `_build_policy`

## Files Created/Modified
- `D:/Aureus/.claude/worktrees/agent-a594a538/services/aureus-nautilus-node/settings.py` - Bỏ default whitelist singleton, bắt buộc env whitelist hợp lệ.
- `D:/Aureus/.claude/worktrees/agent-a594a538/services/aureus-nautilus-node/execution_client.py` - Multi-stream discover/poll, stream symbol extraction, mismatch guard reason code.
- `D:/Aureus/.claude/worktrees/agent-a594a538/services/aureus-nautilus-node/tests/test_config_validation.py` - TDD cho behavior env whitelist bắt buộc.
- `D:/Aureus/.claude/worktrees/agent-a594a538/services/aureus-nautilus-node/tests/test_execution_client_policy.py` - Policy regressions cho fallback removal + mismatch + per-stream cursor.
- `D:/Aureus/.claude/worktrees/agent-a594a538/services/aureus-nautilus-node/tests/test_execution_multi_symbol_contract.py` - Contract tests wave-0 cho multi-symbol path.

## Decisions Made
- Dùng validation fail-fast cho `NAUTILUS_SYMBOL_WHITELIST` thay vì fallback ngầm để đáp ứng threat T-49-05.
- Stream discovery chỉ đọc keys thực có trong Redis pattern và lọc bằng whitelist runtime, không auto-inject stream mặc định.
- Mismatch stream/payload là reject cứng, có metric `symbol_stream_mismatch_total` để quan sát vận hành.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Bỏ fallback singleton trong execution policy mặc định**
- **Found during:** Task 2
- **Issue:** `_build_policy(settings=None)` còn fallback `symbol_whitelist=["XAUUSD"]`, trái yêu cầu bỏ bias singleton ở runtime path.
- **Fix:** Đổi mặc định thành whitelist rỗng, không tự thêm `XAUUSD`.
- **Files modified:** `services/aureus-nautilus-node/execution_client.py`
- **Verification:** `python3 -m pytest .../test_execution_client_policy.py .../test_execution_multi_symbol_contract.py -q` (6 passed)
- **Committed in:** `9236af1`

---

**Total deviations:** 1 auto-fixed (Rule 2)
**Impact on plan:** Sửa bắt buộc để đúng semantics multi-symbol, không mở rộng scope.

## Issues Encountered
- Worktree khởi tạo thiếu `.planning`; đã tạo riêng thư mục summary trong worktree để ghi artifact plan mà không chỉnh STATE/ROADMAP theo yêu cầu objective.
- CLI local không có command `gitnexus_detect_changes`/`detect-changes`; đã ghi nhận giới hạn công cụ này trong execution.

## Known Stubs
None.

## Next Phase Readiness
- Multi-symbol consume path đã có evidence tự động cho discovery + mismatch guard + cursor isolation.
- Sẵn sàng cho verifier phase 49 kiểm tra thêm trên runtime Redis thật theo checklist manual nếu cần.

## Self-Check: PASSED
- FOUND: `D:/Aureus/.claude/worktrees/agent-a594a538/.planning/phases/49-order-execution-contract-multi-symbol/49-02-SUMMARY.md`
- FOUND commit: `a335b73`
- FOUND commit: `30e970f`
- FOUND commit: `d8cd6b8`
- FOUND commit: `9236af1`

---
*Phase: 49-order-execution-contract-multi-symbol*
*Completed: 2026-04-20*
