---
phase: 260503-mjm-market-closed-guard-v-n-spam-log-hold-pr
plan: 01
subsystem: mql5-provider-position-management
tags:
  - mql5
  - market-closed-guard
  - position-management
requires:
  - QUICK-260503-MJM
provides:
  - Pre-close market/session guard before PositionClose
  - Quiet group skip while market-closed guard active
affects:
  - mql5/AureusProvider_v2.mq5
tech_stack:
  added: []
  patterns:
    - provider-local scoped guard by symbol+magic+direction
key_files:
  created: []
  modified:
    - mql5/AureusProvider_v2.mq5
decisions:
  - Reused existing 5-minute scoped market-closed guard instead of adding new state.
  - Kept broker retcode failure logging as race-condition fallback.
metrics:
  tasks: 3
  completed_date: 2026-05-03
---

# Phase 260503-mjm Plan 01: Market Closed Guard Summary

Pre-close market/session guard now stops broker close attempts before `trade.PositionClose`, and active scoped guard now skips group processing before fallback/HOLD/no-rule logs.

## Completed Tasks

| Task | Name | Commit | Files |
|---|---|---|---|
| 1 | Add pre-close market tradability guard | 9dc70c5 | mql5/AureusProvider_v2.mq5 |
| 2 | Skip guarded groups before fallback and HOLD logs | 7a66fd1 | mql5/AureusProvider_v2.mq5 |
| 3 | Verify source scope and compile availability | none | no source changes |

## What Changed

- Added `IsSymbolCloseAvailableNow(symbol, reason)` near existing market-closed guard helpers.
- `ClosePositionTickets` now checks active guard silently, then checks symbol trade mode/session before `LogManagementDecision(... "CLOSE" ...)` and before `trade.PositionClose(...)`.
- When close unavailable, existing `SetMarketClosedCloseGuard(symbol, magic, pos_type_str)` is used and function returns without broker close call.
- `ProcessPositionsByType` now computes direction once and returns early on active guard before `ResolveManagementProfile` and any `LogManagementDecision` call.
- Existing non-market-closed close failure logging remains in place for broker-side race conditions.

## Verification

| Check | Result |
|---|---|
| GitNexus impact `ClosePositionTickets` | Limitation: `npx gitnexus impact --repo Aureus --direction upstream ClosePositionTickets` returned `{ "error": "Target 'ClosePositionTickets' not found" }` |
| GitNexus impact `ProcessPositionsByType` | Limitation: `npx gitnexus impact --repo Aureus --direction upstream ProcessPositionsByType` returned `{ "error": "Target 'ProcessPositionsByType' not found" }` |
| Source assertion: pre-close guard before CLOSE log and `trade.PositionClose` | Passed: `pre-close guard assertions passed` |
| Source assertion: group skip before `ResolveManagementProfile`/`LogManagementDecision` | Passed: `group early-skip assertions passed` |
| `git diff --check -- mql5/AureusProvider_v2.mq5` | Passed |
| MetaEditor CLI availability | Not found: `command -v metaeditor64.exe || command -v MetaEditor64.exe || command -v metaeditor.exe || command -v MetaEditor.exe || true` produced no output. Compile not available in this environment. |
| GitNexus detect changes | Limitation: `npx gitnexus detect_changes --scope all` returned `error: unknown command 'detect_changes'` |
| Scope | Only tracked source change committed: `mql5/AureusProvider_v2.mq5` |

## Deviations from Plan

None - plan executed as written, except environment limitations documented for GitNexus MQL5 symbol lookup, GitNexus detect command, and MetaEditor compile availability.

## Auth Gates

None.

## Known Stubs

None.

## Threat Flags

None.

## Deferred Issues

- Untracked pre-existing/generated files remain uncommitted per constraints: `mql5/AureusProvider_v2.ex5`, `stable/`.
- Plan directory was already untracked before summary creation; docs commit intentionally skipped per user constraint.

## Self-Check: PASSED

- `mql5/AureusProvider_v2.mq5` exists.
- Commit `9dc70c5` exists.
- Commit `7a66fd1` exists.
- Summary written to `.planning/quick/260503-mjm-market-closed-guard-v-n-spam-log-hold-pr/260503-mjm-SUMMARY.md`.
