---
phase: 260425-t9v-ph-n-t-ch-tpo-project-master-c-i-thi-n-c
plan: 01
subsystem: TPO advisory
tags: [quick, tpo, analysis, advisory]
dependency_graph:
  requires:
    - D:/Aureus/services/aureus-signal/engine/signals/tpo.py
    - D:/Aureus/services/aureus-signal/engine/signals/tpo_detectors.py
    - D:/Aureus/services/aureus-signal/engine/signals/tpo_context.py
    - D:/Aureus/tpo_project-master/tpo_helper.py
  provides:
    - D:/Aureus/.planning/quick/260425-t9v-ph-n-t-ch-tpo-project-master-c-i-thi-n-c/260425-t9v-REPORT.md
  affects: []
tech_stack:
  added: []
  patterns:
    - report-only advisory
key_files:
  created:
    - D:/Aureus/.planning/quick/260425-t9v-ph-n-t-ch-tpo-project-master-c-i-thi-n-c/260425-t9v-REPORT.md
    - D:/Aureus/.planning/quick/260425-t9v-ph-n-t-ch-tpo-project-master-c-i-thi-n-c/260425-t9v-SUMMARY.md
  modified: []
decisions:
  - Treat tpo_project-master distr/daytype as a separate future distribution_regime dimension, not as a replacement for Aureus D/B/p/b shape.
  - Recommend distr cao to TREND, distr trung bình to NORMAL, distr thấp to NEUTRAL only as context/confidence metadata guarded by price relation.
metrics:
  completed_date: 2026-04-25
  tasks_completed: 2
  files_created: 2
---

# Quick 260425-t9v: TPO Shape + Distribution Advisory Summary

Báo cáo phân tích chỉ ra vì sao classifier D/B/p/b hiện tại có thể sinh output kiểu D/p/50% gây nghi ngờ nhưng không crash pipeline, và đề xuất tách `distr/daytype` của `tpo_project-master` thành dimension `distribution_regime` riêng cho Aureus.

## Tasks Completed

| Task | Name | Status | Commit |
|---|---|---|---|
| 1 | Inspect reference TPO distribution logic and current classifier semantics | Completed | N/A - report-only, docs artifacts not committed per constraint |
| 2 | Define distr mapping recommendation for Aureus TPO semantics | Completed | N/A - report-only, docs artifacts not committed per constraint |

## Deliverables

- `D:/Aureus/.planning/quick/260425-t9v-ph-n-t-ch-tpo-project-master-c-i-thi-n-c/260425-t9v-REPORT.md`

## Key Findings

- `TPOSignal._classify_shape` normalizes competing heuristic scores into relative percentages; `shape_scores_pct` is not calibrated probability.
- Confidence is separately capped by data quality, margin, immature usable bins, and partial B evidence.
- D can dominate from symmetry + compactness even when profile is visually ambiguous.
- p/b can win from skew/tail-share evidence without any historical daytype/distribution concept.
- `tpo_project-master` provides useful `distr/daytype` reference logic, but not a direct D/B/p/b classifier.

## Recommendations

- Keep D/B/p/b shape classification separate from `distribution_regime`/`day_type`.
- Map `distr cao → TREND`, `distr trung bình → NORMAL`, `distr thấp → NEUTRAL` after calibration against recent history.
- Use distribution regime as confidence/context metadata only; do not emit buy/sell tags without price relation to POC/VAH/VAL.
- Require unit, integration, detector, and replay/backtest tests before any future source-code implementation.

## Deviations from Plan

None - plan executed as report/advisory only.

## Auth Gates

None.

## Known Stubs

None. The produced artifact is an advisory report, not executable code or UI wiring.

## Threat Flags

None. No source code, endpoints, auth paths, file access logic, or schema trust boundaries were introduced.

## Verification

Commands run successfully:

```bash
test -f "D:/Aureus/.planning/quick/260425-t9v-ph-n-t-ch-tpo-project-master-c-i-thi-n-c/260425-t9v-REPORT.md" && grep -E "_classify_shape|D/p|50%|d_score|p_score|confidence|tpo_project-master" "D:/Aureus/.planning/quick/260425-t9v-ph-n-t-ch-tpo-project-master-c-i-thi-n-c/260425-t9v-REPORT.md"

grep -E "distr cao|TREND|distr trung bình|NORMAL|distr thấp|NEUTRAL|future implementation|test" "D:/Aureus/.planning/quick/260425-t9v-ph-n-t-ch-tpo-project-master-c-i-thi-n-c/260425-t9v-REPORT.md"
```

Report length check: 200 lines, exceeding the 80-line minimum artifact requirement.

## Self-Check: PASSED

- Created report exists: `D:/Aureus/.planning/quick/260425-t9v-ph-n-t-ch-tpo-project-master-c-i-thi-n-c/260425-t9v-REPORT.md`.
- Created summary exists: `D:/Aureus/.planning/quick/260425-t9v-ph-n-t-ch-tpo-project-master-c-i-thi-n-c/260425-t9v-SUMMARY.md`.
- No source code was modified intentionally.
- Docs artifacts were not committed, per quick-task constraint.
