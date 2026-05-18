# Quick Task 260518-9yd: Move SL Safety - Summary

**Date:** 2026-05-18
**Status:** Complete
**Code Commit:** eb164e8

## What Changed

Updated `mql5/AureusProvider_v2.mq5` in `MovePositionsSL`.

Shared SL modify safety now applies to all existing `MovePositionsSL` callers:

- Legacy stale breakeven protect
- Trend Runner structure trailing
- Breakout Protect stale breakeven protect
- Breakout Protect structure protection

## Safety Rules Added

Per-ticket no-downgrade guard:

- BUY skips modify when `current_sl > 0 && proposed_sl_price <= current_sl`.
- SELL skips modify when `current_sl > 0 && proposed_sl_price >= current_sl`.

Broker distance precheck:

- Reads `SYMBOL_TRADE_STOPS_LEVEL` and `SYMBOL_TRADE_FREEZE_LEVEL`.
- Uses max of stop/freeze level as required points.
- BUY SL must be below current bid by required distance.
- SELL SL must be above current ask by required distance.
- Invalid/frozen target skips before `trade.PositionModify(...)`.

Retcode handling:

- Failed modify logs `retcode`, `RetcodeToReason(retcode)`, and broker comment.
- `TRADE_RETCODE_NO_CHANGES` / `10025` treated as safe skip, not success.
- Function still returns `success_count > 0`; only actual modified tickets count.

Strategy semantics unchanged:

- No new SL route added to Conservative.
- No new SL route added to Basket Escape.
- Existing callers remain unchanged.

## GitNexus Gate

Official `gitnexus_impact` tool unavailable in this harness.

CLI fallback attempted before edit:

```bash
npx gitnexus impact MovePositionsSL --direction upstream --repo Aureus
```

Result:

```json
{"error":"Target 'MovePositionsSL' not found"}
```

Fallback blast radius before edit:

- Direct callers:
  - `ProcessLegacyPositionsByType`
  - `ProcessTrendRunnerPositionsByType`
  - `ProcessBreakoutProtectPositionsByType`
- Upstream route:
  - `ManagePositionProfitBreakEvent -> ProcessPositionsByType -> profile-specific Process* -> MovePositionsSL`
- Risk: Medium, shared SL modify behavior changes for existing move callers only.

GitNexus detect changes:

- Official tool unavailable in harness.
- CLI `npx gitnexus detect-changes --scope all` attempted and failed: unknown command.
- `npx gitnexus analyze` attempted and failed with `EPERM: open 'D:\Aureus\AGENTS.md'`.
- Fallback scope verification used `git diff -- mql5/AureusProvider_v2.mq5` and `git status --short`.

## Verification

Static verify passed:

```text
MovePositionsSL static safety checks passed
```

Build command:

```powershell
powershell.exe -NoProfile -Command "& 'E:\Openclaw\MetaTrader5\MetaEditor64.exe' /compile:'D:\Aureus\mql5\AureusProvider_v2.mq5' /log:'D:\Aureus\mql5\AureusProvider_v2_compile.log'"
```

Build result:

```text
Result: 0 errors, 0 warnings
```

## Scope

Expected source change:

- `mql5/AureusProvider_v2.mq5`

Unrelated pre-existing dirty/untracked files were not staged:

- `AGENTS.md`
- `CLAUDE.md`
- `mql5/AureusProvider_v2.ex5`
- `services/aureus-signal/scripts/snapshots/`
- `stable/`

## DB E2E

Skipped. No database code or schema touched.
