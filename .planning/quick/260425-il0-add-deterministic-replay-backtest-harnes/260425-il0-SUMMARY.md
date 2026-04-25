---
phase: quick-260425-il0-add-deterministic-replay-backtest-harnes
plan: 260425-il0
subsystem: aureus-signal TPO calibration
tags: [tpo, replay, calibration, deterministic, in-memory]
dependency_graph:
  requires:
    - services/aureus-signal/engine/signals/tpo_detectors.py
    - services/aureus-signal/engine/signals/tpo_strategy.py
  provides:
    - replay_tpo_calibration
  affects:
    - services/aureus-signal/tests/test_tpo_replay.py
tech_stack:
  added:
    - Python pure in-memory replay helper
  patterns:
    - deterministic dict aggregation
    - pytest contract coverage
key_files:
  created:
    - services/aureus-signal/engine/signals/tpo_replay.py
    - services/aureus-signal/tests/test_tpo_replay.py
  modified: []
decisions:
  - Additive replay harness only; no production/live wiring or persistence edits.
  - Threshold sensitivity is computed per fixture row to expose conflict suppression without hiding emitted tag counts from non-conflicting rows.
metrics:
  completed_date: 2026-04-25
  tasks_completed: 3
  duration: not recorded
---

# Quick Task 260425-il0: Add Deterministic Replay Backtest Harness Summary

Pure in-memory TPO calibration replay harness now produces deterministic setup counts, regime breakdown, and threshold sensitivity reports using existing detector and strategy tag bridge contracts without touching production runtime or persistence.

## Completed Tasks

| Task | Name | Commit | Files |
|---|---|---|---|
| 1 | Add failing replay calibration contract tests | da91a72 | services/aureus-signal/tests/test_tpo_replay.py |
| 2 | Implement pure in-memory TPO replay report harness | c4beda0 | services/aureus-signal/engine/signals/tpo_replay.py, services/aureus-signal/tests/test_tpo_replay.py |
| 3 | Verify no production behavior or persistence scope changed | 952b912 | verification-only empty commit |

## What Changed

- Added `replay_tpo_calibration(rows, thresholds=(0.75,))` in `services/aureus-signal/engine/signals/tpo_replay.py`.
- Replay rows remain plain in-memory dictionaries and are not mutated.
- Report includes:
  - total rows and candidate count,
  - setup counts for `va_rejection`, `va_breakout_acceptance`, and `trend_pullback`, split by side/validity,
  - regime breakdown keyed by input labels including trend, range, high_volatility, and low_volatility,
  - threshold sensitivity keyed by stable threshold strings with emitted tag counts and suppression counts.
- Added focused pytest coverage for determinism, count shape, regime grouping, threshold sensitivity, and import-scope guardrails.

## Verification

```bash
cd D:/Aureus && python -m pytest services/aureus-signal/tests/test_tpo_replay.py services/aureus-signal/tests/test_tpo_detectors.py services/aureus-signal/tests/test_tpo_strategy_signal.py -q
# 20 passed in 0.11s
```

GitNexus status/check attempt:

```bash
cd D:/Aureus && npx gitnexus status
# Status: stale (indexed commit f96d9ba, current commit 725bfd5 at time of check)

cd D:/Aureus && npx gitnexus detect-changes
# error: unknown command 'detect-changes'
```

Fallback scoped diff over the task commits:

```bash
cd D:/Aureus && git diff --name-only HEAD~2..HEAD -- services/aureus-signal/engine/signals services/aureus-signal/tests services/aureus-signal/engine/strategies db prisma migrations
# services/aureus-signal/engine/signals/tpo_replay.py
# services/aureus-signal/tests/test_tpo_replay.py
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Adjusted fixture rows to avoid unintended detector overlap**
- **Found during:** Task 2
- **Issue:** Initial deterministic fixture unintentionally emitted extra valid VA rejection / trend pullback candidates, making expected calibration counts ambiguous.
- **Fix:** Tuned fixture close/level values so each required valid/invalid/conflict scenario is explicit and stable.
- **Files modified:** services/aureus-signal/tests/test_tpo_replay.py
- **Commit:** c4beda0

**2. [Rule 2 - Critical Functionality] Count threshold conflict sensitivity per replay row**
- **Found during:** Task 2
- **Issue:** Batch-level threshold aggregation suppressed all tags when any row had conflicting sides, hiding non-conflicting emitted tag counts.
- **Fix:** Evaluate `tpo_strategy_tags_from_candidates` per row for each threshold and aggregate emitted/suppressed counts across rows.
- **Files modified:** services/aureus-signal/engine/signals/tpo_replay.py
- **Commit:** c4beda0

## GitNexus / Impact Notes

- GitNexus MCP tools were not available in this execution environment.
- CLI `npx gitnexus status` was attempted and reported a stale index.
- CLI `npx gitnexus detect-changes` was attempted before verification/commit points but this installed CLI exposed no `detect-changes` command.
- No existing functions/classes/methods were edited; implementation was additive new module/test only.
- Fallback scope verification confirmed only replay harness/test files changed; no DB/schema/migration/seed strategy/trade execution runtime files changed.

## Known Stubs

None.

## Threat Flags

None.

## Auth Gates

None.

## Self-Check: PASSED

- Created file exists: `D:/Aureus/services/aureus-signal/engine/signals/tpo_replay.py`.
- Created file exists: `D:/Aureus/services/aureus-signal/tests/test_tpo_replay.py`.
- Commits exist: `da91a72`, `c4beda0`, `952b912`.
- Summary intentionally left uncommitted per user/orchestrator constraint.
