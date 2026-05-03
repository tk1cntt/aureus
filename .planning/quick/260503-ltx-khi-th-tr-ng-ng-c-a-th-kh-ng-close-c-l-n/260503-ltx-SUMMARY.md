---
phase: 260503-ltx-khi-th-tr-ng-ng-c-a-th-kh-ng-close-c-l-n
plan: 01
subsystem: mql5-provider
tags:
  - quick
  - mql5
  - position-management
  - market-closed-guard
dependency_graph:
  requires:
    - mql5/AureusProvider_v2.mq5
  provides:
    - Scoped market-closed close retry guard
  affects:
    - ClosePositionTickets
    - ManagePositionProfitBreakEvent close paths
tech_stack:
  added: []
  patterns:
    - Provider-local bounded guard keyed by symbol+magic+direction
key_files:
  created: []
  modified:
    - mql5/AureusProvider_v2.mq5
decisions:
  - Scope market-closed close guard by symbol, magic, and direction.
  - Use 5 minute TTL from TimeCurrent() so management recovers without restart.
metrics:
  completed_date: 2026-05-03
  tasks_completed: 2
  duration: unknown
---

# Quick 260503-ltx Summary: Market-Closed Close Retry Guard

## One-liner

MT5 provider now suppresses repeated close attempts for same symbol+magic+direction for 5 minutes after `TRADE_RETCODE_MARKET_CLOSED`, while keeping failed-close retcode/comment logs.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add market-closed close guard in existing close helper | 9731162 | mql5/AureusProvider_v2.mq5 |
| 2 | Verify MQL5 source and compile path | 9731162 | mql5/AureusProvider_v2.mq5 |

## Changes

- Added `MarketClosedCloseGuardState` provider-local state keyed by `symbol`, `magic`, `direction`.
- Added helper functions to find, ensure, check, and set market-closed close guard state.
- Initialized guard array in `OnInit()`.
- Updated `ClosePositionTickets()`:
  - Checks active guard before `LogManagementDecision(... action="CLOSE" ...)` to avoid CLOSE spam.
  - Calls `trade.PositionClose(ticket)` with return-value handling.
  - Logs failed close with ticket, retcode, `RetcodeToReason(retcode)`, and `trade.ResultComment()`.
  - Sets 5 minute guard on `TRADE_RETCODE_MARKET_CLOSED` or `10018` and stops remaining close attempts for group.

## Verification

- Source assertions passed with Node:
  - `TRADE_RETCODE_MARKET_CLOSED` / `10018` present.
  - `trade.ResultRetcode()` present.
  - `trade.ResultComment()` present.
  - Guard exists inside `ClosePositionTickets()`.
  - Guard check occurs before CLOSE decision logging.
- `git diff --name-only` after task commit showed no tracked working-tree diff.
- `git diff --check -- mql5/AureusProvider_v2.mq5` completed with only existing CRLF warning.

## GitNexus Notes

### Impact Analysis

Command:

```bash
cd "D:/Aureus" && npx gitnexus impact --repo Aureus --direction upstream ClosePositionTickets
```

Output:

```json
{
  "error": "Target 'ClosePositionTickets' not found"
}
```

Limitation: GitNexus index does not expose this MQL5 helper symbol, so implementation relied on source-level inspection as plan allowed.

### Detect Changes

Command:

```bash
cd "D:/Aureus" && npx gitnexus detect_changes --scope all
```

Output:

```text
error: unknown command 'detect_changes'
```

Limitation: installed GitNexus CLI has `query`, `context`, `impact`, and `cypher`, but no `detect_changes` command.

## Compile Limitation

MQL5 compiler was not available on CLI PATH.

Command:

```bash
command -v metaeditor64.exe || command -v MetaEditor64.exe || command -v metaeditor.exe || command -v MetaEditor.exe || true
```

Output was empty, so MetaEditor/MetaTrader CLI compile could not be attempted. Source-level verification completed instead.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Replaced unavailable `python3` source check with Node**
- **Found during:** Task 1 verification
- **Issue:** `/usr/bin/bash: line 13: python3: command not found`
- **Fix:** Re-ran equivalent source assertions with Node.
- **Files modified:** None
- **Commit:** 9731162

## Known Stubs

None.

## Threat Flags

None.

## Self-Check: PASSED

- Found modified file: `mql5/AureusProvider_v2.mq5`
- Found commit: `9731162`
- Summary created at requested path.
