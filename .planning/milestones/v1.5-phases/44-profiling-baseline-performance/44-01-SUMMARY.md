---
phase: 44-profiling-baseline-performance
plan: 01
subsystem: testing
tags: [pytest, contract-test, structure-parity, runtime-mode]

requires:
  - phase: 44.0-profiling-baseline-performance
    provides: profiling baseline and instrumentation context for structure optimization rollout
provides:
  - Contract tests for runtime mode flag parsing (`off|shadow|on`) and safe fallback behavior
  - Runtime safety gate to compare new/old structure outputs in `shadow` and force fallback in mismatch cases
  - Whitelisted environment mode parser with default-to-off behavior
affects: [44-profiling-baseline-performance, structure-optimization-rollout, signal-engine-safety]

tech-stack:
  added: []
  patterns: [shadow-compare-before-cutover, env-flag-whitelist-guard, contract-parity-fallback]

key-files:
  created:
    - services/aureus-signal/tests/test_structure_mode_flag.py
    - services/aureus-signal/tests/test_structure_parity_shadow.py
  modified:
    - services/aureus-signal/engine/signals/structure.py

key-decisions:
  - "Dùng mode runtime `off|shadow|on` với whitelist chặt để tránh mode không hợp lệ gây thay đổi hành vi ngầm."
  - "Trong `shadow`/`on`, luôn so sánh contract old/new và fallback về old path khi mismatch để bảo toàn an toàn vận hành."

patterns-established:
  - "Safety rollout pattern: chạy shadow parity trước khi bật mode on."
  - "Contract-first pattern: viết test mode/parity trước rồi mới triển khai runtime logic."

requirements-completed: []

duration: 2min
completed: 2026-04-18
---

# Phase 44 Plan 01: Profiling Baseline Performance Summary

**Cơ chế runtime safety mode cho structure parity đã được bổ sung cùng bộ contract test để đảm bảo fallback an toàn khi old/new mismatch.**

## Performance

- **Duration:** 2 min
- **Started:** 2026-04-17T18:08:14Z
- **Completed:** 2026-04-17T18:09:56Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Bổ sung contract test cho mode flag (`off|shadow|on`) và default fallback khi config không hợp lệ.
- Bổ sung contract test parity cho luồng shadow và hành vi fallback khi có mismatch old/new.
- Triển khai parser `AUREUS_STRUCTURE_OPT_MODE` theo whitelist và logic comparator/fallback trong `structure.py`.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add failing contract tests for mode and parity** - `eb69b3b` (test)
2. **Task 2: Implement runtime safety modes and parity fallback** - `b24ecb4` (feat)

**Plan metadata:** pending (summary recovery only)

## Files Created/Modified
- `services/aureus-signal/tests/test_structure_mode_flag.py` - Test contract cho parse mode whitelist/default behavior.
- `services/aureus-signal/tests/test_structure_parity_shadow.py` - Test contract parity old/new và fallback khi mismatch.
- `services/aureus-signal/engine/signals/structure.py` - Parser mode runtime + comparator/fallback logic cho shadow/on.

## Decisions Made
- Dùng 3 mode runtime `off|shadow|on` thay vì toggle nhị phân để kiểm soát rollout an toàn theo từng bước.
- Ưu tiên “correctness-first”: mismatch ở shadow/on luôn fallback old path thay vì tiếp tục đẩy output mới.

## Deviations from Plan
None - summary này chỉ khôi phục artifact còn thiếu dựa trên các commit task đã tồn tại (`eb69b3b`, `b24ecb4`), không thay đổi implementation.

## Issues Encountered
- Không tìm thấy file `44-01-PLAN.md` tại đường dẫn phase hiện tại; summary được tái dựng từ commit history và file thay đổi thực tế của plan 44-01.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Runtime safety gate và parity test đã sẵn sàng cho các bước tối ưu tiếp theo trong phase 44.
- Có thể dùng mode `shadow` để quan sát mismatch trước khi chuyển sang `on`.

---
*Phase: 44-profiling-baseline-performance*
*Completed: 2026-04-18*

## Self-Check: PASSED
- FOUND: `/d/Aureus/.planning/phases/44-profiling-baseline-performance/44-01-SUMMARY.md`
- FOUND: `eb69b3b`
- FOUND: `b24ecb4`

## Known Stubs
- None.

## Threat Flags
- None.
