---
phase: quick-260427-wky-fix-strategy-executor-none-entry-price-c
plan: 01
subsystem: aureus-signal strategy executor
tags: [strategy-executor, entry-price, regression]
dependency_graph:
  requires:
    - services/aureus-signal/engine/orders.py
  provides:
    - None entry_price rejection guard before strategy match publish
  affects:
    - services/aureus-signal/engine/strategy_executor.py
tech_stack:
  added: []
  patterns:
    - focused async helper for publish preparation
key_files:
  created:
    - services/aureus-signal/tests/test_strategy_executor_entry_price_rejection.py
  modified:
    - services/aureus-signal/engine/strategy_executor.py
decisions:
  - Do not invent fallback entry prices; skip rejected entries with warning.
metrics:
  completed_date: 2026-04-27
  tasks_completed: 3
  tests: 11 passed
---

# Quick 260427-wky Summary: Fix Strategy Executor None Entry Price Crash

Executor hiện tôn trọng contract `_calculate_entry_price(...) -> None` bằng cách skip strategy match trước `_calculate_sl_tp`, `float(computed_ep)`, và publish downstream.

## Completed Tasks

| Task | Status | Commit | Notes |
|------|--------|--------|-------|
| Task 1: Add regression test | Complete | 108c154 | Test mới fail RED vì helper chưa tồn tại, sau Task 2 pass. |
| Task 2: Guard strategy executor publish path | Complete | 09f5cb4 | Thêm guard `computed_ep is None` với warning `ENTRY_PRICE_UNAVAILABLE`. |
| Task 3: Verify scope and runtime-facing evidence | Complete | 09f5cb4 | Targeted pytest pass; GitNexus detect fallback documented below. |

## What Changed

- Added `prepare_and_publish_strategy_match(...)` to isolate executor-side publish preparation and make rejection behavior directly testable.
- Added guard for `computed_ep is None` before SL/TP calculation, float conversion, and `publish_strategy_match(...)`.
- Warning log includes executor symbol prefix, strategy identifier/name, entry method, and explicit `ENTRY_PRICE_UNAVAILABLE` reason.
- Valid numeric/string entry prices keep the existing behavior: SL/TP calculation, `entry_price` float cast, `indicator_snapshot` assignment, and publish.

## Verification

```bash
wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus/.claude/worktrees/agent-aec9bc78 && /mnt/d/Aureus/.venv/bin/python -m pytest services/aureus-signal/tests/test_strategy_executor_entry_price_rejection.py services/aureus-signal/tests/test_signal_event_publisher.py -q"
```

Result: `11 passed in 7.69s`.

GitNexus impact analysis:

```bash
npx gitnexus impact run_strategy_executor --repo Aureus --direction upstream
```

Result: LOW risk; 1 direct upstream caller/importer: `services/aureus-signal/main_executor.py`; no affected processes/modules reported.

GitNexus detect-changes limitation:

```bash
npx gitnexus detect-changes --repo Aureus
```

Result: CLI returned `unknown command 'detect-changes'`. Fallback used targeted `git diff --stat HEAD~2..HEAD` and targeted pytest; only expected files changed:

- `services/aureus-signal/engine/strategy_executor.py`
- `services/aureus-signal/tests/test_strategy_executor_entry_price_rejection.py`

Runtime service restart/log inspection was not run because unit-level verification covered the crash path and no service runtime state was required for this quick task.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Worktree was soft-reset into staged delete/add state**
- **Found during:** Initial setup after branch-base correction.
- **Issue:** The requested soft reset left many files staged as deleted/added and target files were not readable from the worktree path.
- **Fix:** Restored the target files, then performed a hard reset to the required base commit after confirming the soft-reset state was unusable for execution.
- **Files modified:** Worktree index only; no source change retained from this correction.
- **Commit:** N/A

**2. [Rule 3 - Blocking] Plan pytest path targets main checkout, not isolated worktree**
- **Found during:** Task 1 verification.
- **Issue:** The plan command `cd /mnt/d/Aureus` could not see the new worktree-only test file.
- **Fix:** Ran pytest from `/mnt/d/Aureus/.claude/worktrees/agent-aec9bc78` while using root venv `/mnt/d/Aureus/.venv/bin/python`.
- **Files modified:** None.
- **Commit:** N/A

## Known Stubs

None. Empty dict/list values in the regression test are intentional minimal fixtures for executor state, active signals, and recent candles; they do not flow to UI rendering and do not block the plan goal.

## Threat Flags

None. No new network endpoints, auth paths, file access patterns, schema changes, or trust boundaries were introduced.

## Self-Check: PASSED

- Found created file: `D:/Aureus/.claude/worktrees/agent-aec9bc78/services/aureus-signal/tests/test_strategy_executor_entry_price_rejection.py`
- Found modified file: `D:/Aureus/.claude/worktrees/agent-aec9bc78/services/aureus-signal/engine/strategy_executor.py`
- Found commit: `108c154`
- Found commit: `09f5cb4`
