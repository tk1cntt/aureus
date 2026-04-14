---
phase: 42-giam-rr-ratio-xuong-1-5-va-bo-sung-fixed-budget-entry
plan: 01
subsystem: signal-engine
tags: [backtest, rr-ratio, simulated-orders, seed-strategies]

# Dependency graph
requires:
  - phase: "41 (Entry price methods)"
    provides: "_calculate_entry_price methods ported to simulated_orders.py"
provides:
  - "RR 1.5 default fallback in simulated_orders.py _calculate_sl_tp"
  - "Consistent RR 1.5 across all 16 seed strategies"
affects:
  - "Phase 42-02 (RISK_FIXED_AMOUNT entry mode)"
  - "Backtest performance analysis (win rate vs RR 1.5)"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Uniform RR 1.5 for all strategies — no per-strategy override (D-20)"
    - "Seed config value takes priority over default fallback"

key-files:
  created: []
  modified:
    - services/aureus-signal/engine/simulated_orders.py
    - services/aureus-signal/engine/strategies/seed_strategies.py (verified, no changes needed)

key-decisions:
  - "RR 1.5 applied uniformly to all strategies including SESSION_SWEEP_BEAR (D-02, D-20)"
  - "seed_strategies.py already had all 16 strategies at value=1.5 — no edit needed, only verification"

patterns-established:
  - "Default fallback in _calculate_sl_tp = 1.5, matching seed strategy configs"
  - "No hardcoded 2.0 remaining anywhere in signal engine"

requirements_completed: []

# Metrics
duration: 5min
completed: 2026-04-14
---

# Phase 42 Plan 01: Giảm RR Ratio xuống 1.5 Summary

**Giảm default RR ratio fallback từ 2.0 xuống 1.5 trong simulated_orders.py, đảm bảo consistency với 16 seed strategies đã có value=1.5**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-04-14T10:00:00Z
- **Completed:** 2026-04-14T10:05:00Z
- **Tasks:** 1
- **Files modified:** 1 (simulated_orders.py)

## Accomplishments
- Default RR fallback trong `simulated_orders.py._calculate_sl_tp` đổi từ 2.0 → 1.5
- Docstring cập nhật phản ánh default ratio mới
- Xác nhận 16/16 seed strategies đều có `"value": 1.5` trong tp config
- Xác nhận không còn RR 2.0 nào trong toàn bộ aureus-signal codebase

## Task Commits

Each task was committed atomically:

1. **Task 1: Giảm default RR ratio trong simulated_orders.py** - `aa6dbca` (fix)

**Plan metadata:** TBD (docs: complete plan)

## Files Created/Modified
- `services/aureus-signal/engine/simulated_orders.py` - Default RR fallback 2.0 → 1.5, updated docstring

## Decisions Made
None - followed plan as specified. seed_strategies.py đã có sẵn RR 1.5 cho tất cả 16 strategy, chỉ cần verify.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## Known Stubs
None

## Threat Flags
None

## Self-Check: PASSED

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 42-02 (RISK_FIXED_AMOUNT entry mode) ready to execute
- RR 1.5 đã đồng nhất giữa seed config và backtest engine

---
*Phase: 42-giam-rr-ratio-xuong-1-5-va-bo-sung-fixed-budget-entry*
*Completed: 2026-04-14*
