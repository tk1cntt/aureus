---
phase: 48-performance-backtest-api-wiring
plan: 02
subsystem: ui
tags: [nextjs, react, vitest, performance-dashboard, api-contract]
requires:
  - phase: 48-01
    provides: performance API contract and structured invalid-filter errors
provides:
  - /performance page wiring aligned with phase-48 API contract
  - targeted contract test workflow for PERF-08
  - deterministic invalid-filter error-state rendering in UI
affects: [performance dashboard, contract verification, phase-48 closeout]
tech-stack:
  added: [vitest, jsdom, @testing-library/react]
  patterns: [single shared URLSearchParams for multi-endpoint fetch, structured API error envelope rendering]
key-files:
  created:
    - services/aureus-dashboard/web/src/app/performance/__tests__/page.contract.test.tsx
    - services/aureus-dashboard/web/vitest.config.ts
  modified:
    - services/aureus-dashboard/web/package.json
    - services/aureus-dashboard/web/package-lock.json
    - services/aureus-dashboard/web/src/app/performance/page.tsx
    - services/aureus-dashboard/web/src/app/performance/components/EquityChart.tsx
key-decisions:
  - "Dùng Vitest targeted runner cho PERF-08 thay vì build loop để giảm feedback latency."
  - "Ưu tiên error state rõ ràng khi API trả invalid_filter, không render dữ liệu stale."
  - "Giữ kiến trúc fetch song song hiện hữu nhưng thống nhất nguồn query params cho 3 endpoint."
patterns-established:
  - "Performance contract tests mock API envelope theo schema phase 48 để assert runtime behavior."
  - "Metrics render dùng coercion helper trước format để tránh NaN/toFixed crash với nullable fields."
requirements-completed: [PERF-08]
duration: 90min
completed: 2026-04-20
---

# Phase 48 Plan 02: Performance Web Contract Wiring Summary

**Performance page `/performance` đã được nối đúng contract API phase 48 với test contract success/error và cơ chế hiển thị lỗi invalid-filter rõ ràng, không rơi vào render số liệu sai.**

## Performance

- **Duration:** 90 min
- **Started:** 2026-04-20T12:29:00Z
- **Completed:** 2026-04-20T14:00:00Z
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments
- Bổ sung script `test:performance-contract` để chạy nhanh test contract PERF-08.
- Tạo bộ test contract cho 2 luồng bắt buộc: success path và invalid-filter error path.
- Cập nhật `page.tsx` để dùng chung filter semantics cho metrics/trades/equity, parse nullability an toàn, và render structured error state.

## Task Commits

Each task was committed atomically:

1. **Task 0: Tạo test runner script cho contract test PERF-08** - `a111573` (chore)
2. **Task 1: Viết contract tests cho `/performance` success + invalid-filter error** - `290d4e9` (test)
3. **Task 2: Cập nhật performance page theo contract API mới, thống nhất filter và nullability guards** - `a32ca5c` (feat)

## Files Created/Modified
- `/d/Aureus/.claude/worktrees/agent-aef229f2/services/aureus-dashboard/web/package.json` - thêm script test targeted và cấu hình test dependencies.
- `/d/Aureus/.claude/worktrees/agent-aef229f2/services/aureus-dashboard/web/package-lock.json` - lock dependency cho test runner.
- `/d/Aureus/.claude/worktrees/agent-aef229f2/services/aureus-dashboard/web/vitest.config.ts` - alias + jsdom env cho contract tests.
- `/d/Aureus/.claude/worktrees/agent-aef229f2/services/aureus-dashboard/web/src/app/performance/__tests__/page.contract.test.tsx` - contract tests cho shared filters và invalid-filter UI error.
- `/d/Aureus/.claude/worktrees/agent-aef229f2/services/aureus-dashboard/web/src/app/performance/page.tsx` - unified query builder, structured error handling, null-safe metric formatting, suspense wrapper.
- `/d/Aureus/.claude/worktrees/agent-aef229f2/services/aureus-dashboard/web/src/app/performance/components/EquityChart.tsx` - sửa type timestamp để build pass trên Next 16 + TS strict.

## Decisions Made
- Giữ kiến trúc hiện tại (parallel fetch + URL sync), chỉ bổ sung guard/error handling tối thiểu theo contract.
- Error từ API được ưu tiên hiển thị deterministic state thay vì fallback sang empty/stale data sections.
- Tách `PerformancePageContent` và bọc `Suspense` để đáp ứng yêu cầu prerender của Next 16 khi dùng `useSearchParams`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Cài test framework thiếu cho targeted contract test**
- **Found during:** Task 1
- **Issue:** repo web chưa có vitest/testing-library nên script test không chạy được.
- **Fix:** thêm `vitest`, `jsdom`, `@testing-library/react` và `vitest.config.ts` cho alias `@`.
- **Files modified:** `package.json`, `package-lock.json`, `vitest.config.ts`
- **Verification:** `npm --prefix /d/Aureus/.claude/worktrees/agent-aef229f2/services/aureus-dashboard/web run test:performance-contract` pass.
- **Committed in:** `290d4e9`

**2. [Rule 3 - Blocking] Sửa lỗi build type ở `EquityChart` chặn verify Task 2**
- **Found during:** Task 2 verify (`npm run build`)
- **Issue:** `time` truyền vào `lightweight-charts` sai type `Time`.
- **Fix:** dùng `UTCTimestamp` cast chuẩn cho `chartData.time`.
- **Files modified:** `src/app/performance/components/EquityChart.tsx`
- **Verification:** build pass.
- **Committed in:** `a32ca5c`

**3. [Rule 3 - Blocking] Sửa lỗi prerender Suspense cho `useSearchParams`**
- **Found during:** Task 2 verify (`npm run build`)
- **Issue:** Next 16 yêu cầu `useSearchParams()` nằm trong suspense boundary.
- **Fix:** tách `PerformancePageContent` và export wrapper `PerformancePage` bọc `<Suspense fallback={null}>`.
- **Files modified:** `src/app/performance/page.tsx`
- **Verification:** build pass.
- **Committed in:** `a32ca5c`

---

**Total deviations:** 3 auto-fixed (3 Rule 3 blocking)
**Impact on plan:** Các deviation đều là unblock cần thiết để hoàn tất verify bắt buộc, không mở rộng phạm vi tính năng.

## Issues Encountered
- GitNexus index initially stale + EPERM trên `AGENTS.md`; đã xử lý quyền file, re-run analyze và thực thi impact analysis trước các symbol chỉnh sửa.

## Next Phase Readiness
- PERF-08 có evidence tự động đầy đủ (targeted contract test + build pass).
- `/performance` đã sẵn sàng cho verification wave tiếp theo với semantics filter đồng nhất và error-state deterministic.

## Self-Check: PASSED
- FOUND: `/d/Aureus/.claude/worktrees/agent-aef229f2/.planning/phases/48-performance-backtest-api-wiring/48-02-SUMMARY.md`
- FOUND commit: `a111573`
- FOUND commit: `290d4e9`
- FOUND commit: `a32ca5c`
