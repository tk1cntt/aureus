---
phase: 33
plan: 01
type: execute
wave: 1
dependencies: []
files_modified:
  - services/aureus-dashboard/web/src/app/performance/page.tsx
  - services/aureus-dashboard/web/src/app/performance/components/MetricCard.tsx
  - services/aureus-dashboard/web/src/app/performance/components/FilterBar.tsx
  - services/aureus-dashboard/web/src/app/performance/components/PerformanceTable.tsx
  - services/aureus-dashboard/web/src/app/performance/components/EquityChart.tsx
  - services/aureus-dashboard/web/src/components/Sidebar.tsx
subsystem: frontend
tags:
  - performance
  - dashboard
  - ui
requirements:
  - PERF-08
provides:
  - performance-dashboard-ui
affects:
  - Sidebar navigation
tech-stack:
  added: []
  patterns:
    - Next.js App Router file-based routing
    - Native fetch with Promise.all parallel requests
    - URL search params for filter state
    - lightweight-charts v5.1.0 AreaSeries
    - Tailwind CSS v4 dark theme
key-files:
  created:
    - services/aureus-dashboard/web/src/app/performance/page.tsx
    - services/aureus-dashboard/web/src/app/performance/components/MetricCard.tsx
    - services/aureus-dashboard/web/src/app/performance/components/FilterBar.tsx
    - services/aureus-dashboard/web/src/app/performance/components/PerformanceTable.tsx
    - services/aureus-dashboard/web/src/app/performance/components/EquityChart.tsx
  modified:
    - services/aureus-dashboard/web/src/components/Sidebar.tsx
decisions:
  - Used lightweight-charts AreaSeries via chart.addSeries(AreaSeries, options) pattern (v5.1.0 API)
  - Filter state synchronized with URL search params via router.push
  - Parallel fetch with Promise.all for metrics, trades, equity-curve
  - MetricCard extracted from backtest page StatCard inline pattern
metrics:
  completed: "2026-04-07"
  tasks_completed: 4
  files_created: 5
  files_modified: 1
---

# Phase 33 Plan 01: Performance Dashboard UI Summary

**One-liner:** Performance dashboard at `/performance` with 6 metric cards, equity curve chart (lightweight-charts), filter bar with URL params, and paginated trade history table — all using existing dark theme patterns.

## Tasks Completed

| # | Task | Status | Commit |
|---|------|--------|--------|
| 1 | Add /performance nav link to Sidebar + create empty page shell | ✅ Done | 4f0633c |
| 2 | Create page shell + fetch data with parallel Promise.all | ✅ Done | 4f0633c |
| 3 | Create MetricCard, FilterBar, PerformanceTable, EquityChart components | ✅ Done | 4f0633c |
| 4 | Wire up URL params-based filtering + pagination + 6 metric cards | ✅ Done | 4f0633c |

## Key Decisions

1. **Chart API**: lightweight-charts v5.1.0 uses `chart.addSeries(AreaSeries, options)` — not `addAreaSeries()`. Fixed TypeScript error during implementation (Deviation Rule 1 - Bug).
2. **Filter State**: URL search params as source of truth, matching Next.js App Router conventions. FilterBar manages local state, parent page handles URL updates via `router.push`.
3. **Default Dates**: Start = 7 days ago, End = now — same pattern as backtest page.
4. **Pagination**: 20 rows/page, controlled via `currentPage` state that triggers refetch.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed lightweight-charts API mismatch**
- **Found during:** Task 3 (EquityChart creation)
- **Issue:** Plan specified `chart.addAreaSeries()` which doesn't exist in v5.1.0. The correct API is `chart.addSeries(AreaSeries, options)` as used in BacktestChart.tsx.
- **Fix:** Updated EquityChart.tsx to import `AreaSeries` from lightweight-charts and use `chart.addSeries(AreaSeries, {...options})`.
- **Files modified:** `services/aureus-dashboard/web/src/app/performance/components/EquityChart.tsx`
- **Commit:** 4f0633c

## Security Notes

- XSS mitigation: React auto-escapes all JSX content in MetricCard, PerformanceTable — no `dangerouslySetInnerHTML` used (T-33-04 mitigated).
- URL params: Filter values sent via `URLSearchParams` (safe encoding) to Phase 32 API which uses parameterized queries (T-33-01, T-33-02 mitigated).
- Trade data: Internal-only dashboard, no PII exposed (T-33-03 accepted).

## Known Stubs

None. All components wire to real Phase 32 API endpoints.

## Verification

- **TypeScript**: `npx tsc --noEmit` passes with zero errors ✅
- **Files created**: 5 new files, 1 modified file ✅
- **Commit**: Single commit with all 6 files ✅
- **Pattern consistency**: Follows backtest/page.tsx patterns for fetch, SymbolsContext, dark theme ✅
