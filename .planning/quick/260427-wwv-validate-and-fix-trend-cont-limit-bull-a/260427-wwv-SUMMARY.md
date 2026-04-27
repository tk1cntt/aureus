---
phase: quick-260427-wwv-validate-and-fix-trend-cont-limit-bull-a
plan: 01
subsystem: aureus-signal
tags: [strategy-seed, order-plan, entry-pivot-limit, db-verification]
dependency_graph:
  requires: [services/aureus-signal/engine/strategies/seed_strategies.py, services/aureus-signal/engine/orders.py, services/aureus-signal/engine/snapshot_utils.py]
  provides: [validated TREND_CONT_LIMIT_BULL/TREND_CONT_LIMIT_BEAR seed configs]
  affects: [aureus_strategy_templates.config, aureus_symbol_strategies]
tech_stack:
  added: []
  patterns: [TDD regression, WSL pytest, container DB seed verification]
key_files:
  created: []
  modified:
    - services/aureus-signal/tests/test_strategy_seed_sync.py
    - services/aureus-signal/engine/strategies/seed_strategies.py
decisions:
  - Add explicit entry_value=PIVOT to the two ENTRY_PIVOT_LIMIT seed declarations so accepted order-plan snapshots satisfy the required non-empty key contract without changing runtime fallback behavior.
metrics:
  duration: PT0H
  completed_at: "2026-04-27T16:46:33Z"
---

# Quick 260427-wwv: Validate and Fix Trend Continuation Limit Bull/Bear Summary

TREND_CONT_LIMIT_BULL and TREND_CONT_LIMIT_BEAR now have explicit pivot-limit seed config completeness while preserving ENTRY_PIVOT_LIMIT runtime semantics.

## Objective

Kiểm tra và sửa đúng trọng tâm 2 seed strategy `TREND_CONT_LIMIT_BULL` và `TREND_CONT_LIMIT_BEAR` để đảm bảo khai báo seed khớp runtime order creation và seed được vào DB active.

## Tasks Completed

| Task | Status | Commit | Notes |
|------|--------|--------|-------|
| Task 1: Audit two LIMIT trend seed declarations against runtime contracts | Completed | 2624432 | Added failing regression/audit test proving missing `entry_value` in both LIMIT trend declarations. |
| Task 2: Fix only proven config/runtime gaps for the two strategies | Completed | f332187 | Added `entry_value: "PIVOT"` only to the two targeted seed declarations. |
| Task 3: Seed runtime DB and verify both strategies are active | Completed | f332187 | Seeded via `aureus-signal-dev` container and verified active DB rows for all configured symbols. |

## Audit Findings

- `services/aureus-signal/engine/snapshot_utils.py` defines `REQUIRED_ORDER_PLAN_KEYS` including non-empty `entry_value` for accepted traces/order-plan snapshots.
- `services/aureus-signal/engine/strategies/template.py` forwards `trade_execution.entry_value` into the built order plan.
- Before the fix, both `TREND_CONT_LIMIT_BULL` and `TREND_CONT_LIMIT_BEAR` had `entry_type=LIMIT` and `entry_method=ENTRY_PIVOT_LIMIT`, but no `entry_value`, so the order-plan snapshot could be incomplete even though the entry price is computed later from pivots.
- `services/aureus-signal/engine/orders.py` already preserves required semantics: `ENTRY_PIVOT_LIMIT` returns BUY LL below current and SELL HH above current, and returns `None` when no valid pivot exists rather than falling back to market/current.

## Changes Made

- Added TDD regression coverage in `services/aureus-signal/tests/test_strategy_seed_sync.py` asserting both trend limit strategies declare:
  - correct BUY/SELL direction,
  - `entry_type=LIMIT`,
  - `entry_method=ENTRY_PIVOT_LIMIT`,
  - `entry_value=PIVOT`,
  - valid sizing, SL `PIVOT_POINT`, TP `RR_RATIO`, trailing, required CHOCH sequence, and opposite CHOCH early exit.
- Added `entry_value: "PIVOT"` to only:
  - `TREND_CONT_LIMIT_BULL`,
  - `TREND_CONT_LIMIT_BEAR`.

## GitNexus Evidence

- `npx gitnexus status` reported stale index: indexed commit `aebb665`, current commit `47e345d`.
- Attempted `npx gitnexus analyze`; it failed with `EPERM: operation not permitted, open 'D:\Aureus\AGENTS.md'`.
- Ran `npx gitnexus impact seed_system_strategies --repo Aureus --direction upstream` successfully:
  - impactedCount: 14
  - risk: CRITICAL
  - direct callers: 8
  - affected processes: 20
  - direct callers include `run_strategy_executor`, `run_signal_engine`, `run_backtest_engine`, reload listeners, dry-run script, and manual seed runner.
- `npx gitnexus query "strategy seed order plan ENTRY_PIVOT_LIMIT" --repo Aureus` found seed and strategy/order-plan related flows.
- GitNexus `detect_changes` CLI command was unavailable (`unknown command 'detect_changes'` and `unknown command 'detect-changes'`), so pre-commit scope verification used targeted `git diff` limited to the intended test file and seed file.

## Verification

### RED

Command:

```bash
wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus && ./.venv/bin/python -m pytest services/aureus-signal/tests/test_strategy_seed_sync.py::test_trend_cont_limit_seed_declarations_match_runtime_contract -q"
```

Result: failed as expected with `KeyError: 'entry_value'`.

### GREEN / Focused Tests

Command:

```bash
wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus && ./.venv/bin/python -m pytest services/aureus-signal/tests/test_strategy_seed_sync.py::test_trend_cont_limit_seed_declarations_match_runtime_contract services/aureus-signal/tests/test_entry_price_methods.py -q"
```

Result: `13 passed in 7.09s`.

### Broader Focused Suite

Command:

```bash
wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus && ./.venv/bin/python -m pytest services/aureus-signal/tests -q -k 'entry_pivot_limit or order_plan or seed_strategies or strategy'"
```

Result: `191 passed, 1 skipped, 468 deselected`, with one pre-existing unrelated failure:

- `services/aureus-signal/tests/test_strategy_seed_sync.py::test_runbook_contract`
- reason: missing `.planning/phases/46-strategy-seed-sync/46-ROLLBACK-RUNBOOK.md`
- This file is outside quick task scope and was not changed.

### DB / Runtime Seed Verification

Command:

```bash
wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus && docker compose -f docker-compose.dev.yml ps && docker exec aureus-signal-dev python -m engine.strategies.seed_strategies && docker exec -i aureus_timescaledb_dev psql -U aureus -d aureus -c \"SELECT t.name, ss.symbol, ss.is_active, t.config->'trade_execution'->>'direction' AS direction, t.config->'trade_execution'->>'entry_type' AS entry_type, t.config->'trade_execution'->>'entry_method' AS entry_method, t.config->'trade_execution'->>'entry_value' AS entry_value FROM aureus_strategy_templates t JOIN aureus_symbol_strategies ss ON ss.strategy_id = t.id WHERE t.name IN ('TREND_CONT_LIMIT_BULL','TREND_CONT_LIMIT_BEAR') ORDER BY t.name, ss.symbol;\""
```

Result: docker services were up; seed completed; DB query returned 16 rows across AUDUSD, BTCUSD, ETHUSD, EURUSD, GBPUSD, USDJPY, USTEC, XAUUSD. All rows had:

- `is_active = t`
- BULL: `direction=BUY`, `entry_type=LIMIT`, `entry_method=ENTRY_PIVOT_LIMIT`, `entry_value=PIVOT`
- BEAR: `direction=SELL`, `entry_type=LIMIT`, `entry_method=ENTRY_PIVOT_LIMIT`, `entry_value=PIVOT`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical functionality] Added explicit pivot entry value for required order-plan key**
- **Found during:** Task 1 audit/TDD regression
- **Issue:** The two targeted seed configs did not set `entry_value`, while accepted order-plan snapshots require the key to be present and non-empty.
- **Fix:** Added `entry_value: "PIVOT"` to `TREND_CONT_LIMIT_BULL` and `TREND_CONT_LIMIT_BEAR` only.
- **Files modified:** `services/aureus-signal/engine/strategies/seed_strategies.py`, `services/aureus-signal/tests/test_strategy_seed_sync.py`
- **Commit:** f332187

## Deferred Issues

- Pre-existing/out-of-scope test failure: `.planning/phases/46-strategy-seed-sync/46-ROLLBACK-RUNBOOK.md` is missing, causing `test_runbook_contract` to fail in broader `-k strategy` runs. This quick task did not modify phase 46 docs.
- GitNexus CLI limitations in this environment:
  - `npx gitnexus analyze` failed due `EPERM` on `D:\Aureus\AGENTS.md`.
  - `npx gitnexus detect_changes` / `detect-changes` are not recognized by the installed CLI.

## Known Stubs

None found in files modified by this quick task.

## Threat Flags

None. No new endpoint, auth path, file access pattern, or schema trust boundary was introduced. Existing code seed declaration to database boundary was verified by tests and DB query.

## Self-Check: PASSED

- Created/modified files exist:
  - `D:/Aureus/services/aureus-signal/tests/test_strategy_seed_sync.py`
  - `D:/Aureus/services/aureus-signal/engine/strategies/seed_strategies.py`
  - `D:/Aureus/.planning/quick/260427-wwv-validate-and-fix-trend-cont-limit-bull-a/260427-wwv-SUMMARY.md`
- Commits exist:
  - `2624432` test regression commit
  - `f332187` seed config fix commit
- DB verification returned active BULL/BEAR LIMIT strategy rows with `ENTRY_PIVOT_LIMIT` and `entry_value=PIVOT`.
