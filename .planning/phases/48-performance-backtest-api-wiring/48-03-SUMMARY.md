---
phase: 48-performance-backtest-api-wiring
plan: 03
subsystem: api
tags: [fastapi, react, vitest, pytest, performance, contract-testing]
requires:
  - phase: 48-01
    provides: API performance endpoints and contract baseline
  - phase: 48-02
    provides: web /performance contract wiring baseline
provides:
  - Equity endpoint applies normalized filter dimensions in runtime query path
  - Web parser aligned to backend top-level error envelope with backward compatibility
  - Regression tests covering both closed verification gaps
affects: [performance-dashboard, api-contract, verification]
tech-stack:
  added: []
  patterns: [normalized-filter reuse, contract-first error parsing, targeted regression tests]
key-files:
  created:
    - .planning/phases/48-performance-backtest-api-wiring/48-03-SUMMARY.md
  modified:
    - services/aureus-dashboard/api/main.py
    - services/aureus-dashboard/api/tests/conftest.py
    - services/aureus-dashboard/api/tests/test_performance_contract.py
    - services/aureus-dashboard/web/src/app/performance/page.tsx
    - services/aureus-dashboard/web/src/app/performance/__tests__/page.contract.test.tsx
key-decisions:
  - "Filter dimensions symbol/strategy_id/timeframe phải đi qua cả snapshot và fallback path của equity endpoint để tránh split-brain dataset."
  - "Web parser ưu tiên backend runtime envelope top-level {error, code, details}, nhưng vẫn giữ backward compatibility cho nested envelope cũ."
patterns-established:
  - "Performance widgets dùng cùng normalized filter semantics giữa metrics/trades/equity."
  - "Contract tests phải mock đúng runtime envelope backend, không dùng shape giả khác hợp đồng."
requirements-completed: [PERF-06, PERF-07, PERF-08]
duration: 13min
completed: 2026-04-20
---

# Phase 48 Plan 03: Gap Closure Summary

**Đồng bộ filter semantics cho equity runtime path và chuẩn hóa web error parsing theo backend envelope thật để đóng trực tiếp PERF-06/07/08.**

## Performance

- **Duration:** 13 min
- **Started:** 2026-04-20T14:05:31Z
- **Completed:** 2026-04-20T14:18:27Z
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments
- Đóng gap #1: `get_equity_curve` đã áp dụng đầy đủ filter dimensions (`symbol`, `strategy_id`, `timeframe`, `start/end`) trong cả snapshot query và fallback query.
- Đóng gap #2: `parseErrorMessage` parse đúng backend top-level envelope (`error`, `code`, `details`) và vẫn hỗ trợ nested legacy shape.
- Bổ sung/siết regression tests để đảm bảo hai gap trên bị bắt tự động nếu tái phát.

## Task Commits

1. **Task 1: Đóng gap equity filter-effect trong API runtime path** - `d1aa58f` (feat)
2. **Task 2: Đồng bộ web error parser với envelope backend thật** - `198cdfe` (fix)
3. **Task 3: Chạy verify bundle phase 48 cho gap closure** - Không phát sinh thay đổi file, thực thi verify commands theo plan

## Files Created/Modified
- `/d/Aureus/services/aureus-dashboard/api/main.py` - áp filter dimensions vào query của `get_equity_curve` cho snapshot/fallback.
- `/d/Aureus/services/aureus-dashboard/api/tests/test_performance_contract.py` - test regression xác nhận equity data thay đổi theo filter dimensions.
- `/d/Aureus/services/aureus-dashboard/api/tests/conftest.py` - fixture/query fake cập nhật để phản ánh semantics filter runtime mới.
- `/d/Aureus/services/aureus-dashboard/web/src/app/performance/page.tsx` - parser lỗi align backend envelope thật, giữ tương thích ngược.
- `/d/Aureus/services/aureus-dashboard/web/src/app/performance/__tests__/page.contract.test.tsx` - mock lỗi invalid-filter đổi sang runtime shape backend.

## Decisions Made
- Ưu tiên sửa đúng chỗ phát sinh inconsistency (`get_equity_curve`), không mở rộng endpoint hay analytics mới.
- Giữ parser backward-compatible để tránh break với payload cũ trong giai đoạn chuyển tiếp.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Thiếu runtime test dependency cho web contract tests**
- **Found during:** Task 2
- **Issue:** `npm run test:performance-contract` fail với `'vitest' is not recognized`.
- **Fix:** Chạy `npm --prefix /d/Aureus/services/aureus-dashboard/web install` để đảm bảo dependency test có sẵn trong môi trường chạy.
- **Files modified:** Không thay đổi source files thuộc plan scope.
- **Verification:** Web contract tests chạy pass sau khi cài dependency.
- **Committed in:** N/A (không phát sinh thay đổi tracked files)

---

**Total deviations:** 1 auto-fixed (Rule 3)
**Impact on plan:** Chỉ xử lý blocker môi trường verify, không mở rộng scope kỹ thuật.

## Issues Encountered
- GitNexus CLI hiện tại không expose command `detect_changes` như guideline trong CLAUDE.md; thay thế bằng `gitnexus impact` + kiểm soát file-level qua `git status`/staging discipline để giữ phạm vi surgical.

## Known Stubs
None.

## Next Phase Readiness
- Hai verification gaps còn lại của phase 48 đã có bằng chứng test tự động.
- PERF-06/07/08 đã có đường traceability pass path ở API + web contract tests.

## Self-Check: PASSED
- FOUND: /d/Aureus/.planning/phases/48-performance-backtest-api-wiring/48-03-SUMMARY.md
- FOUND: d1aa58f
- FOUND: 198cdfe
