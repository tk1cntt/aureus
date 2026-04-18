---
phase: 44-profiling-baseline-performance
plan: 02
subsystem: structure-signal
tags: [performance, parity, replay-regression, numpy]

requires:
  - phase: 44.0-profiling-baseline-performance
    provides: runtime safety mode và parity fallback từ plan 44-01
provides:
  - Replay regression gate kiểm tra parity đầy đủ old/new path
  - Performance gate cứng: optimized_avg_ms <= old_avg_ms * 0.60
  - Hot-path StructureSignal tối ưu theo hướng array access
affects: [44-profiling-baseline-performance, structure-optimization-rollout, signal-engine-performance]

tech-stack:
  added: []
  patterns: [array-centric-hot-path, replay-parity-contract, perf-gate-40-percent]

key-files:
  created:
    - services/aureus-signal/tests/test_structure_replay_regression.py
  modified:
    - services/aureus-signal/engine/signals/structure.py
    - services/aureus-signal/tests/test_ob_numpy.py

key-decisions:
  - "Duy trì strict parity qua replay contract trước khi xét promote mode."
  - "Áp dụng A-first optimization (array access), không triển khai incremental scan B trong plan này."

patterns-established:
  - "Performance rollout gate: phải đạt >=40% giảm latency mới qua cổng plan."
  - "Mismatch context-first: fail message phải có symbol/t/diff_fields để debug nhanh."

requirements-completed: [PH44-PERF, PH44-PARITY]

duration: 9min
completed: 2026-04-18
---

# Phase 44 Plan 02: Profiling Baseline Performance Summary

**Đã triển khai tối ưu A-first cho StructureSignal và bổ sung replay regression gate để khóa cả parity lẫn mục tiêu hiệu năng giảm tối thiểu 40%.**

## Performance

- **Duration:** 9 min
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Tạo `test_structure_replay_regression.py` với dataset replay xác định và comparator old/new contract đầy đủ.
- Bổ sung hard gate hiệu năng `optimized_avg_ms <= old_avg_ms * 0.60`.
- Tối ưu hot-path `structure.py` theo hướng array access, giữ nguyên logic giao dịch cốt lõi.
- Cập nhật `test_ob_numpy.py` để khóa edge cases OB/swing sau chuyển hướng truy cập dữ liệu.

## Task Commits
1. **Task 1: Add replay regression parity + performance gate** - `a4cc15b`
2. **Task 2: Optimize structure hot path with array access** - `94cbe9e`

## Files Created/Modified
- `services/aureus-signal/tests/test_structure_replay_regression.py`
- `services/aureus-signal/engine/signals/structure.py`
- `services/aureus-signal/tests/test_ob_numpy.py`

## Verification
- `pytest services/aureus-signal/tests/test_structure_replay_regression.py -q -x` ✅
- `pytest services/aureus-signal/tests/test_ob_numpy.py services/aureus-signal/tests/test_structure_replay_regression.py -q -x` ✅
- `pytest services/aureus-signal/tests -k "structure and (parity or shadow or replay_regression or ob_numpy)" -q -x` ✅

## Impact Analysis
- Target theo plan: `StructureSignal._emit` (không tồn tại trong snapshot hiện tại)
- Fallback impact: `StructureSignal`
- Blast radius: risk LOW, direct callers 0, affected processes 0

## Deviations from Plan
- Thêm xử lý import path cho test replay để ổn định collection trong môi trường hiện tại.

## Self-Check: PASSED
- FOUND: `.planning/phases/44-profiling-baseline-performance/44-02-SUMMARY.md`
- FOUND: `a4cc15b`
- FOUND: `94cbe9e`

## Known Stubs
- None.

## Threat Flags
- None.
