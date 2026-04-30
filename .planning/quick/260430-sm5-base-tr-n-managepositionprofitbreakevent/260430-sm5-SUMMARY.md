---
phase: 260430-sm5-base-tr-n-managepositionprofitbreakevent
plan: 01
subsystem: mql5-provider
tags: [mql5, provider, position-management, breakeven]
dependency_graph:
  requires: [mql5/AureusProvider_v2.mq5, mql5/CISD_Slope_EA_v6.39_Final.mq5]
  provides: [provider-safe profit/breakeven position management]
  affects: [AureusProvider_v2 timer position management]
tech_stack:
  added: []
  patterns: [symbol-magic-direction grouping, ticket-scoped modify/close]
key_files:
  created: []
  modified: [mql5/AureusProvider_v2.mq5]
decisions:
  - "Ported only provider-safe profit/breakeven mechanics; skipped EA chart signal state resets."
metrics:
  duration: "not recorded"
  completed_date: "2026-04-30"
---

# Phase 260430-sm5 Plan 01: Base TRN ManagePositionProfitBreakEvent Summary

Bổ sung quản lý profit/breakeven theo nhóm `symbol + magic + direction` cho `AureusProvider_v2.mq5`, dựa trên `ManagePositionProfitBreakEvent()`/`ProcessPositionsByType()` của CISD EA nhưng không dùng `_Symbol` làm identity giao dịch.

## Completed Tasks

| Task | Name | Status | Commit |
| ---- | ---- | ------ | ------ |
| 1 | Port profit/breakeven management with provider-safe grouping | Completed | 9020d00 |
| 2 | Wire management into provider timer for all InpSymbols | Completed | 9020d00 |
| 3 | Compile provider and keep generated artifacts out of git | Completed with compile environment unavailable | 9020d00 |

## Implementation Notes

- Added `InpProfitTarget` to match the EA profit threshold used by breakeven management.
- Added `ManagePositionProfitBreakEvent()` that scans live MT5 positions and processes only positions where:
  - `POSITION_SYMBOL` is configured in `InpSymbols`/`g_contexts`.
  - `POSITION_MAGIC != 0`.
  - Group key is exactly `POSITION_SYMBOL + POSITION_MAGIC + POSITION_TYPE`.
- Added ticket-scoped `ProcessPositionsByType(...)` so close/modify operations only use collected tickets for the current group.
- Added minimal symbol-aware imbalance helpers `IsImbalanceUp(symbol, timeframe, index)` and `IsImbalanceDown(symbol, timeframe, index)`.
- Wired management once per `OnTimer()` after candle polling and before the existing provider-local CISD DCA gate.

## Verification

| Check | Result |
| ----- | ------ |
| `git -C D:/Aureus diff --check -- mql5/AureusProvider_v2.mq5` | Passed |
| Manual diff review for `_Symbol` in new position-management logic | Passed; new management uses explicit `symbol` for filtering, SymbolInfoDouble, iLow/iHigh, and group operations |
| Compile attempt via MetaEditor | Attempted; unavailable from shell path `/mnt/e/Openclaw/MetaTrader5/MetaEditor64.exe` |
| Generated artifacts staged | Passed; `.ex5` remains untracked and was not staged/committed |
| GitNexus impact before edits | Attempted; MQL5 symbols were not found in GitNexus index |
| GitNexus change detection before commit | Attempted; CLI command unavailable (`detect-changes`, `detect_changes`, `changes` unknown) |

## GitNexus Evidence

Impact attempts:

- `npx gitnexus impact OnTimer --repo Aureus --direction upstream` -> target not found.
- `npx gitnexus impact DoDCA --repo Aureus --direction upstream` -> target not found.
- `npx gitnexus impact ProcessPositionsByType --repo Aureus --direction upstream` -> target not found.

Change detection attempts:

- `npx gitnexus detect-changes --repo Aureus` -> unknown command.
- `npx gitnexus detect_changes --repo Aureus` -> unknown command.
- `npx gitnexus changes --repo Aureus` -> unknown command.

Fallback used: manual `git diff --check`, `git diff -- mql5/AureusProvider_v2.mq5`, and scoped review against the plan invariants.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Compile environment command failed from bash/cmd quoting and MetaEditor path was unavailable**
- **Found during:** Task 3
- **Issue:** Build_Rules command through bash/cmd produced a malformed compile command, then the direct `/mnt/e/.../MetaEditor64.exe` path did not exist in this environment.
- **Fix:** Documented compile unavailability and verified with diff/manual review instead. No generated compile logs were committed.
- **Files modified:** None beyond planned code file and this summary.
- **Commit:** 9020d00

## Known Stubs

None found in created/modified code. No TODO/FIXME/placeholder or mock-data UI stubs were introduced.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: trade-automation | mql5/AureusProvider_v2.mq5 | Added timer-driven live position close/SL modify logic at MT5 trade-server boundary; this matches the plan threat model and is mitigated by configured-symbol, nonzero-magic, direction-scoped ticket grouping. |

## Self-Check: PASSED

- Modified code file exists: `D:/Aureus/mql5/AureusProvider_v2.mq5`.
- Summary file exists: `D:/Aureus/.planning/quick/260430-sm5-base-tr-n-managepositionprofitbreakevent/260430-sm5-SUMMARY.md`.
- Code commit exists: `9020d00`.
