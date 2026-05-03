---
phase: 260503-o5w-ki-m-tra-ngh-a-log-managepositiondecisio
plan: 01
subsystem: mql5-provider
tags: [quick, mql5, logging, hold-suppression]
dependency_graph:
  requires: [mql5/AureusProvider_v2.mq5, 260503-neg-summary]
  provides: [breakout-protect-hold-log-suppression, manage-position-log-report]
  affects: [provider-position-management, mt5-journal]
tech_stack:
  added: []
  patterns: [symbol-magic-direction-reason log key]
key_files:
  created:
    - .planning/quick/260503-o5w-ki-m-tra-ngh-a-log-managepositiondecisio/260503-o5w-REPORT.md
    - .planning/quick/260503-o5w-ki-m-tra-ngh-a-log-managepositiondecisio/260503-o5w-SUMMARY.md
  modified:
    - mql5/AureusProvider_v2.mq5
decisions:
  - "Suppress repeated HOLD reason breakout_profit_below_protection_threshold via existing symbol+magic+direction+reason helper; preserve CLOSE/error/non-HOLD logs."
metrics:
  completed_date: 2026-05-03
  tasks_completed: 3
---

# Quick 260503-o5w Summary: ManagePositionDecision breakout HOLD log analysis and suppression

## One-liner

`breakout_profit_below_protection_threshold` giờ được suppress như repeated HOLD theo key hiện có, sau khi report xác minh log là trạng thái below-threshold bình thường của `breakout_protect`, không phải lỗi close/SL.

## Tasks Completed

| Task | Kết quả | Commit |
|---|---|---|
| Task 1 | Xác minh source path `OnTimer -> ManagePositionProfitBreakEvent -> ProcessPositionsByType -> ProcessBreakoutProtectPositionsByType -> LogManagementDecision`, threshold `positions_count * InpBEProfitTarget / 2`, và nguyên nhân lặp. | source-read only |
| Task 2 | Tạo report tiếng Việt giải thích meaning, root cause spam, BTCUSD/ETHUSD condition, fix recommendation, validation, limitations. | docs only, không commit theo constraint |
| Task 3 | Thêm `breakout_profit_below_protection_threshold` vào repeated HOLD suppression helper/allowlist, giữ nguyên CLOSE/error/non-HOLD logs. | `7cabd74` |

## Files Changed

- `D:/Aureus/mql5/AureusProvider_v2.mq5`
- `D:/Aureus/.planning/quick/260503-o5w-ki-m-tra-ngh-a-log-managepositiondecisio/260503-o5w-REPORT.md`
- `D:/Aureus/.planning/quick/260503-o5w-ki-m-tra-ngh-a-log-managepositiondecisio/260503-o5w-SUMMARY.md`

## Behavior Changed

- Repeated `HOLD` log with reason `breakout_profit_below_protection_threshold` is emitted once per `symbol+magic+direction+reason`, then suppressed.
- Existing repeated HOLD suppression for `profile_fallback` and `legacy_no_rule_matched` remains.
- `action != "HOLD"` gate remains, so `CLOSE`, `MOVE_SL`, `TRAIL_SL`, close failure, market guard, `ORDER_FAILED`, unknown profile, and other non-HOLD logs remain visible.
- Trade management thresholds and position management actions were not changed.

## Verification

| Check | Result |
|---|---|
| Task 1 source anchors | Passed: `source evidence anchors present` |
| Report assertions | Passed: `report assertions passed` |
| GitNexus impact before edit | Limitation: `npx gitnexus impact --repo Aureus --direction upstream ShouldSuppressRepeatedHoldDecisionLog` returned `{ "error": "Target 'ShouldSuppressRepeatedHoldDecisionLog' not found" }`; MQL5 symbol not indexed by current CLI. |
| Source helper assertions | Passed with adjusted whitespace-tolerant regex: helper body contains new reason, `action != "HOLD"`, existing reasons, and ManagePositionDecision print remains. |
| Diff check | Passed: `git -C /d/Aureus diff --check -- mql5/AureusProvider_v2.mq5 ...` returned success. |
| MetaEditor compile | Limitation: `MetaEditor64.exe`, `metaeditor64.exe`, `MetaEditor.exe`, `metaeditor.exe` not found in PATH. Compile not run. |
| GitNexus detect changes before commit | Limitation: `npx gitnexus detect_changes --scope all` and `npx gitnexus detect-changes --repo Aureus --scope all` returned unknown command. |
| Unrelated untracked files | Preserved uncommitted: `D:/Aureus/mql5/AureusProvider_v2.ex5`, `D:/Aureus/stable/`. |

## Deviations from Plan

None - plan executed as written. Environment limitations documented for GitNexus MQL5 symbol lookup, GitNexus detect command availability, and MetaEditor compile availability.

## Auth Gates

None.

## Known Stubs

None.

## Threat Flags

None. No new endpoint, auth path, file access path, schema change, or external trust boundary added. Change only reduces repeated low-value MT5 journal output for one HOLD reason.

## Deferred Issues

- Pre-existing modified file outside this quick remained untouched and uncommitted: `D:/Aureus/services/aureus-signal/engine/orders.py`.
- Pre-existing untracked files remained untouched and uncommitted: `D:/Aureus/mql5/AureusProvider_v2.ex5`, `D:/Aureus/stable/`.

## Self-Check: PASSED

- Summary file exists: `D:/Aureus/.planning/quick/260503-o5w-ki-m-tra-ngh-a-log-managepositiondecisio/260503-o5w-SUMMARY.md`
- Report file exists: `D:/Aureus/.planning/quick/260503-o5w-ki-m-tra-ngh-a-log-managepositiondecisio/260503-o5w-REPORT.md`
- Code commit exists: `7cabd74`
- Modified source exists: `D:/Aureus/mql5/AureusProvider_v2.mq5`
