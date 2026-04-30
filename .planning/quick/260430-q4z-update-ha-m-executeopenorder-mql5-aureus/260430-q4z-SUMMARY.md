---
phase: 260430-q4z-update-ha-m-executeopenorder-mql5-aureus
plan: 01
completed: 2026-04-30
commit: 29a903e
tags: [mql5, provider, open-order, duplicate-guard]
key_files:
  created:
    - mql5/compile_aureusprovider_v2.log
  modified:
    - mql5/AureusProvider_v2.mq5
---

# Quick Task 260430-q4z Summary

## One-liner

`ExecuteOpenOrder` now rejects same-symbol same-magic active strategy orders before ACK, command recording, order validation, or order send.

## Completed Tasks

| Task | Status | Evidence |
|------|--------|----------|
| Analyze blast radius and insertion point | Completed | Direct search found `ExecuteOpenOrder` called only from `ProcessIncomingCommands` for `OPEN_ORDER`; insertion point confirmed after required field/idempotency/symbol checks and before `SendACK(cmdId)` / `RecordCmdId(cmdId)`. |
| Add same-symbol same-magic guard | Completed | Added position scan via `PositionsTotal`/`PositionGetTicket`/`PositionSelectByTicket` and pending order scan via `OrdersTotal`/`OrderGetTicket`/`OrderSelect`, both requiring symbol and magic equality before `SendNACK(cmdId, "STRATEGY_ORDER_EXISTS")`. |
| Compile and verify scope | Completed | `mql5/compile_aureusprovider_v2.log` reports `Result: 0 errors, 0 warnings`; `git diff` scope was limited to provider source plus compile log before commit. |

## Implementation Notes

- The guard is intentionally inline and local to `ExecuteOpenOrder` to keep the change surgical.
- Same magic on a different symbol remains allowed because both scans require `POSITION_SYMBOL`/`ORDER_SYMBOL` to equal the requested `symbol`.
- Same symbol with a different magic remains allowed because both scans require `POSITION_MAGIC`/`ORDER_MAGIC` to equal the requested `magic`.
- Reject path calls only `SendNACK(cmdId, "STRATEGY_ORDER_EXISTS")` and returns before `TerminalInfoInteger(TERMINAL_TRADE_ALLOWED)`, `SendACK`, `RecordCmdId`, `OrderCheck`, `OrderSend`, or `ORDER_OPENED` side effects.

## Verification

- Static search:
  - `STRATEGY_ORDER_EXISTS` is located before `SendACK(cmdId)` and `RecordCmdId(cmdId)` in `ExecuteOpenOrder`.
  - Position scan compares `PositionGetString(POSITION_SYMBOL) == symbol` and `PositionGetInteger(POSITION_MAGIC) == magic`.
  - Pending order scan compares `OrderGetString(ORDER_SYMBOL) == symbol` and `OrderGetInteger(ORDER_MAGIC) == magic`.
- MetaEditor compile:
  - Command used from this checkout: `/e/Openclaw/MetaTrader5/MetaEditor64.exe /compile:"D:\Aureus\mql5\AureusProvider_v2.mq5" /log:"D:\Aureus\mql5\compile_aureusprovider_v2.log"`
  - Result: `0 errors, 0 warnings`.

## GitNexus / Scope Evidence

- GitNexus MCP tools were not available in this agent toolset.
- CLI fallback attempt `npx --prefix "D:/Aureus" gitnexus detect-changes` failed because multiple repositories were indexed and required `--repo`.
- CLI fallback attempt `npx --prefix "D:/Aureus" gitnexus detect-changes --repo Aureus` exited with segmentation fault from `npx`.
- Direct-search fallback evidence:
  - `ExecuteOpenOrder` definition at `mql5/AureusProvider_v2.mq5` line ~1599.
  - Only direct call found in provider is from `ProcessIncomingCommands` after matching `"OPEN_ORDER"`.
  - Scope diff before commit contained only `mql5/AureusProvider_v2.mq5` and `mql5/compile_aureusprovider_v2.log`.

## Deviations from Plan

### Auto-fixed / Operational Deviations

**1. [Rule 3 - Blocking] MetaEditor command quoting**
- **Found during:** Task 3
- **Issue:** The `cmd /c` quoting form produced `'ompile:D:' is not recognized` under bash on Windows.
- **Fix:** Invoked MetaEditor directly via `/e/Openclaw/MetaTrader5/MetaEditor64.exe` with Windows paths for `/compile` and `/log`.
- **Files modified:** None beyond planned compile log.
- **Commit:** 29a903e

**2. [Rule 3 - Blocking] Compile log is gitignored**
- **Found during:** Commit step
- **Issue:** `mql5/compile_aureusprovider_v2.log` is ignored but required as a plan artifact.
- **Fix:** Staged the specific log artifact with `git add -f`.
- **Files modified:** `mql5/compile_aureusprovider_v2.log`
- **Commit:** 29a903e

## Known Stubs

None found in modified provider source.

## Threat Flags

None beyond the plan threat model; the change reduces OPEN_ORDER duplicate side effects at the existing provider order-execution boundary.

## Self-Check: PASSED

- Provider source modified: `D:/Aureus/mql5/AureusProvider_v2.mq5`
- Compile log created: `D:/Aureus/mql5/compile_aureusprovider_v2.log`
- Code commit exists: `29a903e`
