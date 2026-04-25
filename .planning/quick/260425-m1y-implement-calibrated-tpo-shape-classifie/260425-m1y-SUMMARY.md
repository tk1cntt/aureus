---
phase: 260425-m1y-implement-calibrated-tpo-shape-classifie
plan: 01
subsystem: aureus-signal-tpo
tags: [quick, tpo, classifier, calibration]
dependency_graph:
  requires: [REQ-LQO-01, REQ-LQO-02, REQ-LQO-03, REQ-LQO-04, REQ-LQO-05]
  provides: [calibrated-tpo-shape-classifier]
  affects: [services/aureus-signal/engine/signals/tpo.py, services/aureus-signal/tests/test_tpo_signal.py]
tech_stack:
  added: []
  patterns: [deterministic-heuristic, data-quality-gate, confidence-margin]
key_files:
  created: []
  modified:
    - D:/Aureus/services/aureus-signal/engine/signals/tpo.py
    - D:/Aureus/services/aureus-signal/tests/test_tpo_signal.py
decisions:
  - Giữ runtime contract shape D/B/p/b và dùng confidence cap thay vì thêm trạng thái unknown/forming.
  - Dùng fallback GitNexus CLI/status + source search vì MCP GitNexus tools không có trong executor context.
metrics:
  duration: "unknown"
  completed_date: 2026-04-25
---

# Quick 260425-m1y: Implement Calibrated TPO Shape Classifier Summary

Calibrated deterministic TPO shape classifier with geometry-based D/B/p/b scoring, data-quality confidence caps, separated-peak B detection, and focused fixtures for sparse/outlier/tick-size/margin behavior.

## Completed Tasks

| Task | Name | Commit | Files |
| ---- | ---- | ------ | ----- |
| 1 | Add calibrated classifier fixture tests before changing runtime | 45987ac | D:/Aureus/services/aureus-signal/tests/test_tpo_signal.py |
| 2 | Implement calibrated deterministic heuristic inside _classify_shape only | 9141cce | D:/Aureus/services/aureus-signal/engine/signals/tpo.py, D:/Aureus/services/aureus-signal/tests/test_tpo_signal.py |
| 3 | Run focused regression checks and GitNexus change-scope verification | 8e97d09 | no code changes; empty verification commit |

## What Changed

- Added direct `_classify_shape` fixtures covering clear D, separated B, lumpy non-high-confidence B, p, b, empty/zero/sparse, low-count outlier, tick-size stability, and lower confidence for ambiguous/two-peak cases.
- Replaced score-only normalization with local deterministic metrics inside `_classify_shape`:
  - usable-bin, total-count, coverage, maturity, and data-quality confidence cap;
  - symmetry and compactness around POC for D-shape;
  - peak prominence, minimum separation, valley depth, and peak balance for B-shape;
  - bounded upper/lower mass and tail excess for p/b;
  - confidence derived from top-1/top-2 margin plus data-quality caps.
- Preserved public output contract: `shape` remains one of `D/B/p/b`, `shape_confidence_pct` remains `[0, 100]`, and `shape_scores_pct` keeps exactly keys `D/B/p/b` with percentage-like distribution for non-empty profiles.

## Verification

- `cd D:/Aureus && pytest services/aureus-signal/tests/test_tpo_signal.py -q` -> `17 passed in 0.76s`.
- Scope fallback: `git status --short` after commits showed only the untracked quick summary directory; no production/test code files remained modified.
- No DB e2e run because this quick task does not touch persistence, schema, migrations, or database-connected code.

## GitNexus / Impact Analysis

GitNexus MCP tools were not available in this executor context, so exact `gitnexus_impact()` and `gitnexus_detect_changes()` calls could not be executed.

Fallback actions performed:

- `npx gitnexus status` showed the index existed but became stale after commits. Initial `npx gitnexus analyze` attempt refreshed the index but exited with `EPERM` writing `D:/Aureus/AGENTS.md`; this limitation is environmental and was recorded instead of editing outside scope.
- Source search for `_classify_shape` found the direct production caller `TPOSignal._build_tpo_block` at `D:/Aureus/services/aureus-signal/engine/signals/tpo.py`, plus direct unit test calls in `D:/Aureus/services/aureus-signal/tests/test_tpo_signal.py`.
- Fallback blast radius: direct caller is `_build_tpo_block`; affected process is TPO indicator block construction consumed by `calculate()` outputs; risk assessed as medium because runtime contract is preserved but Telegram/indicator consumers can see calibrated confidence values.
- Fallback change-scope verification used `git diff --name-only`, scoped diffs, pytest, and `git status --short`; only the allowed files were modified for code/test implementation.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] GitNexus MCP unavailable / CLI analyze EPERM**
- **Found during:** Task 2 and Task 3
- **Issue:** Required MCP calls were not exposed. CLI fallback `npx gitnexus analyze` failed on `D:/Aureus/AGENTS.md` with `EPERM`.
- **Fix:** Used closest available checks: `npx gitnexus status`, source search for direct callers, scoped git diff/status, and focused pytest.
- **Files modified:** None for the fallback itself.
- **Commit:** N/A

**2. [Rule 1 - Test contract adjustment] Confidence is now calibrated separately from score distribution**
- **Found during:** Task 2
- **Issue:** Existing helper assumed `scores[shape] == confidence`; new requirement says confidence reflects winner margin and data-quality cap, not raw normalized score/probability.
- **Fix:** Adjusted focused test helper to assert valid shape/scores contract while allowing calibrated confidence to differ from raw score distribution.
- **Files modified:** D:/Aureus/services/aureus-signal/tests/test_tpo_signal.py
- **Commit:** 9141cce

## Known Stubs

None.

## Threat Flags

None. No new network endpoints, auth paths, file access patterns, database schemas, migrations, or trust-boundary-expanding runtime surfaces were introduced.

## Self-Check: PASSED

- Found modified code file: D:/Aureus/services/aureus-signal/engine/signals/tpo.py
- Found modified test file: D:/Aureus/services/aureus-signal/tests/test_tpo_signal.py
- Found commits: 45987ac, 9141cce, 8e97d09
- Focused tests passed: `17 passed`.
