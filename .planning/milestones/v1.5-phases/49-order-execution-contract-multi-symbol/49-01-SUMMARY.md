---
phase: 49-order-execution-contract-multi-symbol
plan: 01
subsystem: api
tags: [order-open, validation, idempotency, nautilus, redis-stream]
requires: []
provides:
  - "Contract-first validation cho ORDER_OPEN tại execution boundary"
  - "Qty canonicalization: ưu tiên qty, fallback quantity"
  - "Regression tests cho critical fields, duplicate trace_id và contingent generation"
affects: [order-execution, multi-symbol-runtime, risk-controls]
tech-stack:
  added: []
  patterns: [contract-first-validation, deterministic-reason-codes, strict-idempotency]
key-files:
  created: []
  modified:
    - services/aureus-nautilus-node/execution_client.py
    - services/aureus-nautilus-node/tests/test_execution_client.py
    - services/aureus-nautilus-node/tests/test_execution_risk_controls.py
key-decisions:
  - "Giữ minimum-change wiring: chỉ sửa execution client + tests, không đổi producer stream format"
  - "Dùng reason code ổn định ORDER_OPEN_MISSING_CRITICAL_FIELD cho thiếu critical fields"
  - "Giữ strict duplicate gate qua _seen_trace_ids và verify bằng regression test"
patterns-established:
  - "ORDER_OPEN critical fields phải validate cứng ở consume boundary"
  - "Optional field fallback phải có metric evidence"
requirements-completed: [ORDER-01, ORDER-02, PH45-05]
duration: 39min
completed: 2026-04-20
---

# Phase 49 Plan 01: Order execution contract-first hardening Summary

**ORDER_OPEN consume path đã được khóa contract-first với reason code deterministic, hỗ trợ alias quantity->qty không false reject, và giữ strict idempotency cho duplicate trace_id.**

## Performance

- **Duration:** 39 min
- **Started:** 2026-04-20T22:33:00Z
- **Completed:** 2026-04-20T23:12:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Chuẩn hóa validation critical fields (`trace_id/symbol/side/qty`) về reason code ổn định `ORDER_OPEN_MISSING_CRITICAL_FIELD`.
- Bổ sung canonicalization `qty` ưu tiên và fallback alias `quantity`, tránh reject sai payload hợp lệ.
- Bổ sung regression tests cho contingent generation (ENTRY+SL+TP) và duplicate trace_id (`DUPLICATE_TRACE_ID`) không generate lần 2.

## Blast Radius (GitNexus impact)

Target: `_validate_and_build_orders` (upstream)
- d=1: `_handle_message` (direct caller)
- d=2: `_poll_orders_once`
- d=3: `_poll_loop`, test path `_case`
- Affected processes: 5
- Risk reported by GitNexus: **CRITICAL**

## Task Commits

1. **Task 1: Chuẩn hóa validation critical fields + qty alias tại execution boundary** - `da70014` (feat)
2. **Task 2: Khóa idempotency strict và contingent generation theo ORDER_OPEN** - `a504191` (test)

## Files Created/Modified
- `D:/Aureus/.claude/worktrees/agent-ae4bc3d1/services/aureus-nautilus-node/execution_client.py` - thêm critical validation reason code ổn định, qty alias normalization, optional fallback metrics.
- `D:/Aureus/.claude/worktrees/agent-ae4bc3d1/services/aureus-nautilus-node/tests/test_execution_client.py` - thêm regression tests cho missing critical fields, quantity alias, optional fallback metrics.
- `D:/Aureus/.claude/worktrees/agent-ae4bc3d1/services/aureus-nautilus-node/tests/test_execution_risk_controls.py` - thêm regression tests cho contingent generation dùng quantity alias và duplicate reason code.

## Decisions Made
- Áp dụng sửa tối thiểu đúng scope plan, không mở rộng service boundary (theo D-10).
- Giữ reject deterministic cho critical contract thay vì reason code rời rạc từng field.
- Giữ idempotency path hiện có, chỉ tăng coverage test để khóa regression.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Không thể chạy `gitnexus analyze` do EPERM ghi `D:/Aureus/CLAUDE.md`**
- **Found during:** Trước Task 1 impact workflow
- **Issue:** GitNexus index stale, nhưng analyze fail vì permission file `CLAUDE.md`.
- **Fix:** Tiếp tục dùng `gitnexus impact` trực tiếp (lệnh vẫn chạy) để lấy blast radius bắt buộc trước khi sửa symbol.
- **Verification:** `gitnexus impact "_validate_and_build_orders" --direction upstream --repo Aureus --depth 3 --include-tests` trả về đầy đủ byDepth/processes/risk.
- **Committed in:** N/A (environment/tooling gate)

**2. [Rule 3 - Blocking] CLI không có lệnh `gitnexus detect_changes`**
- **Found during:** Pre-commit checks
- **Issue:** CLAUDE.md yêu cầu detect_changes trước commit, nhưng CLI trả `unknown command 'detect_changes'`.
- **Fix:** Fallback kiểm soát phạm vi bằng staging file tường minh + `git status` chỉ chứa file thuộc plan.
- **Verification:** Hai commit chỉ chạm đúng file trong `files_modified` của plan.
- **Committed in:** N/A (tool capability gap)

---

**Total deviations:** 2 auto-fixed (2 blocking/tooling)
**Impact on plan:** Không đổi phạm vi chức năng; toàn bộ mục tiêu kỹ thuật của plan vẫn hoàn thành.

## Issues Encountered
- Pytest tạo `__pycache__/*.pyc` untracked; đã xóa trước mỗi commit để giữ tree sạch.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Ready cho 49-02: contract consistency ở bridge/signal path có thể tiếp tục dựa trên reason-code + idempotency baseline đã khóa.
- Không có blocker mã nguồn còn mở trong phạm vi plan 49-01.

## Self-Check: PASSED
- FOUND: D:/Aureus/.planning/phases/49-order-execution-contract-multi-symbol/49-01-SUMMARY.md
- FOUND: da70014
- FOUND: a504191
