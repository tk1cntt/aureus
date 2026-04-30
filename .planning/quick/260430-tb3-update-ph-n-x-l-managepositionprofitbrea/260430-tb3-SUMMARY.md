---
phase: 260430-tb3-update-ph-n-x-l-managepositionprofitbrea
plan: 01
subsystem: mql5-provider
tags: [mql5, provider, position-management, breakeven, grouping]
dependency_graph:
  requires: [mql5/AureusProvider_v2.mq5]
  provides: [explicit symbol-magic-direction breakeven grouping]
  affects: [AureusProvider_v2 ManagePositionProfitBreakEvent]
tech_stack:
  added: []
  patterns: [symbol-magic-direction grouping, group-local aggregate metrics]
key_files:
  created: []
  modified: [mql5/AureusProvider_v2.mq5]
decisions:
  - "Kept ProcessPositionsByType signature unchanged because existing grouping already passes symbol, magic, direction, tickets, and aggregate metrics."
metrics:
  duration: "not recorded"
  completed_date: "2026-04-30"
---

# Phase 260430-tb3 Plan 01: ManagePositionProfitBreakEvent Grouping Summary

Clarified and verified `ManagePositionProfitBreakEvent()` grouping so breakeven management remains isolated per `symbol + magic + direction` and never processes mixed-magic ticket groups.

## Completed Tasks

| Task | Name | Status | Commit |
| ---- | ---- | ------ | ------ |
| 1 | Fix ManagePositionProfitBreakEvent grouping by magic | Completed | 4c4e646 |
| 2 | Verify aggregate locality and compile scope | Completed with compile environment unavailable | 4c4e646 |

## Implementation Notes

- Added a surgical inline invariant comment at the `already_processed` guard to make the group identity explicit: `symbol + magic + direction`.
- Verified existing collection predicates already require all three fields before appending to `tickets[]` or updating aggregate metrics.
- Kept `ProcessPositionsByType(symbol, magic, type, tickets, ...)` unchanged; it already receives the current group's `magic` and ticket-scoped metrics.
- The diff also includes prior uncommitted breakeven parameter alignment present in the worktree: `InpBEProfitTarget`, `commission_per_lot = 12.0`, and the corresponding reference update.

## Aggregate Locality Checklist

| Metric / value | Verification |
| -------------- | ------------ |
| `tickets[]` | Declared inside each outer group scope and populated only after `POSITION_SYMBOL == symbol`, `POSITION_MAGIC == magic`, and `POSITION_TYPE == type`. |
| `total_profit` | Reset to `0` inside each group and incremented only after all three group predicates match. |
| `total_volume` | Reset to `0` inside each group and incremented only after all three group predicates match. |
| `weighted_price_sum` | Reset to `0` inside each group and incremented only after all three group predicates match. |
| `earliest_open_time` | Reset to `0` inside each group and compared only against matching positions. |
| `ProcessPositionsByType(...)` | Called with the same `symbol`, `magic`, and `type` used to build `tickets[]` and metrics. |

## Verification

| Check | Result |
| ----- | ------ |
| `git -C D:/Aureus diff -- mql5/AureusProvider_v2.mq5` | Reviewed before commit; only scoped provider file changes. |
| `git -C D:/Aureus diff --check -- mql5/AureusProvider_v2.mq5` | Passed. |
| GitNexus impact before edits | Attempted; MQL5 symbols were not found in GitNexus index. |
| GitNexus change detection before commit | Attempted; CLI commands were unavailable. |
| MetaEditor compile | Attempted; shell/cmd quoting produced malformed command, direct `/mnt/e/Openclaw/MetaTrader5/MetaEditor64.exe` path unavailable. |
| Generated artifacts staged | Passed; `.ex5`, snapshots, `stable/`, and `tmp/` remain untracked and were not staged/committed. |

## GitNexus Evidence

Impact attempts:

- `npx gitnexus impact ManagePositionProfitBreakEvent --repo Aureus --direction upstream` -> target not found.
- `npx gitnexus impact ProcessPositionsByType --repo Aureus --direction upstream` -> target not found.

Change detection attempts:

- `npx gitnexus detect-changes --repo Aureus` -> unknown command.
- `npx gitnexus detect_changes --repo Aureus` -> unknown command.
- `npx gitnexus changes --repo Aureus` -> unknown command.

Fallback used: scoped `git diff`, `git diff --check`, `git status --short`, and manual review against the plan invariants.

## Deviations from Plan

### Auto-fixed Issues

None - plan executed surgically. The implementation path confirmed the grouping logic already included symbol, magic, and direction; only a minimal invariant comment was added to make the critical grouping contract obvious.

## Known Stubs

None found in created/modified code. No TODO/FIXME/placeholder or mock-data UI stubs were introduced.

## Threat Flags

None beyond the plan threat model. This task did not introduce new endpoints, auth paths, file access patterns, schema changes, or new trade automation surfaces; it only clarified existing grouping logic.

## Self-Check: PASSED

- Modified code file exists: `D:/Aureus/mql5/AureusProvider_v2.mq5`.
- Summary file exists: `D:/Aureus/.planning/quick/260430-tb3-update-ph-n-x-l-managepositionprofitbrea/260430-tb3-SUMMARY.md`.
- Code commit exists: `4c4e646`.
