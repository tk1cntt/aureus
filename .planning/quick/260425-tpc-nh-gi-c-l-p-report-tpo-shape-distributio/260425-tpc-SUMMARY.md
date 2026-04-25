---
phase: quick-260425-tpc
plan: 01
subsystem: TPO architecture advisory
tags:
  - quick
  - documentation
  - tpo
  - architecture-advisory
dependency_graph:
  requires:
    - .planning/quick/260425-t9v-ph-n-t-ch-tpo-project-master-c-i-thi-n-c/260425-t9v-REPORT.md
    - services/aureus-signal/engine/signals/tpo.py
    - services/aureus-signal/engine/signals/tpo_context.py
    - services/aureus-signal/engine/signals/tpo_detectors.py
  provides:
    - independent advisory for TPO shape/distribution semantics
  affects:
    - future TPO implementation requirements and tests
tech_stack:
  added: []
  patterns:
    - documentation-only advisory
    - four-step architecture review
decisions:
  - Keep `_classify_shape` as visual-shape metadata and introduce future `distribution_regime` separately from `distr` only as context modifier.
key_files:
  created:
    - .planning/quick/260425-tpc-nh-gi-c-l-p-report-tpo-shape-distributio/260425-tpc-ARCHITECTURE-ADVISORY.md
    - .planning/quick/260425-tpc-nh-gi-c-l-p-report-tpo-shape-distributio/260425-tpc-SUMMARY.md
  modified: []
metrics:
  completed_date: 2026-04-25
  tasks_completed: 2
  duration: not recorded
---

# Quick 260425-tpc Summary: TPO Shape/Distribution Advisory

Tạo advisory độc lập bằng tiếng Việt để đánh giá report `260425-t9v` theo quy trình 4 bước, chốt best choice: giữ `_classify_shape` là visual-shape classifier và thêm `distribution_regime` riêng từ `distr = total_tpo_count / max_tpo_count` trong implementation tương lai.

## Tasks Completed

| Task | Name | Result |
|---|---|---|
| 1 | Viết advisory độc lập đúng 6 section bắt buộc | Created advisory with exactly the six required top-level sections in order. |
| 2 | Khóa best choice và future implementation basis | Best choice and requirements/test basis were made concrete for future implementation. |

## Verification

- Ran the Task 1 embedded Python verification: passed.
- Ran the Task 2 embedded Python verification: passed.
- Checked `git -C "D:/Aureus" status --short -- "services" ".planning/quick/260425-tpc-nh-gi-c-l-p-report-tpo-shape-distributio"`: no `services/` source modifications were reported; only the quick task directory is untracked.

## Decisions Made

- `_classify_shape` should remain visual-shape metadata for D/B/p/b, with future fixture/calibration improvements.
- `distr` should be a separate distribution intensity/regime input, not a direction signal.
- `distribution_regime` should use `TREND`, `NORMAL`, `NEUTRAL`, `UNKNOWN` with baseline lịch sử/rolling.
- Regime must not self-emit buy/sell, must not replace D1 bias, and must only modify scoring/tagging after price-relation setup is already valid.

## Deviations from Plan

None - plan executed as documentation/advisory only and source code was not modified.

## Known Stubs

None. The created advisory is a complete documentation artifact for future implementation basis.

## Threat Flags

None. No new network endpoints, auth paths, file access patterns, schema changes, or source trust boundaries were introduced.

## Commits

No task commits were created because user constraints explicitly state this is docs/advisory only and docs artifacts must not be committed here; orchestrator handles docs commit in Step 8.

## Self-Check: PASSED

- Advisory file exists at `D:/Aureus/.planning/quick/260425-tpc-nh-gi-c-l-p-report-tpo-shape-distributio/260425-tpc-ARCHITECTURE-ADVISORY.md`.
- Summary file exists at `D:/Aureus/.planning/quick/260425-tpc-nh-gi-c-l-p-report-tpo-shape-distributio/260425-tpc-SUMMARY.md`.
- Embedded automated checks passed.
- No source files under `D:/Aureus/services/` were modified.
