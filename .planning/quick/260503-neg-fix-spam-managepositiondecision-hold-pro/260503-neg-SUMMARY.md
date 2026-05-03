---
phase: 260503-neg-fix-spam-managepositiondecision-hold-pro
plan: 01
subsystem: mql5-provider
tags: [quick, mql5, logging, hold-suppression]
dependency_graph:
  requires: [mql5/AureusProvider_v2.mq5]
  provides: [provider-local-hold-decision-log-suppression]
  affects: [provider-position-management, mt5-journal]
tech_stack:
  added: []
  patterns: [provider-local state, symbol-magic-direction-reason log key]
key_files:
  created:
    - .planning/quick/260503-neg-fix-spam-managepositiondecision-hold-pro/260503-neg-SUMMARY.md
  modified:
    - mql5/AureusProvider_v2.mq5
decisions:
  - "Suppress only repeated HOLD decision logs for profile_fallback and legacy_no_rule_matched, keyed by symbol+magic+direction+reason."
metrics:
  completed_date: 2026-05-03
  tasks_completed: 3
---

# Quick 260503-neg Summary: HOLD decision spam suppression

## One-liner

`AureusProvider_v2.mq5` giờ chỉ in lần đầu cho HOLD `profile_fallback` và `legacy_no_rule_matched` trên mỗi `symbol+magic+direction+reason`, giữ nguyên log close/error/non-HOLD.

## Tasks Completed

| Task | Kết quả | Commit |
|---|---|---|
| Task 1 | Thêm `HoldDecisionLogState` và `ShouldSuppressRepeatedHoldDecisionLog(...)` tại ranh giới `LogManagementDecision`. | `c4e20f3` |
| Task 2 | Chạy source assertions, diff check, GitNexus detect fallback, MetaEditor availability check. | `c4e20f3` |
| Task 3 | Ghi summary với scope, verification, limitation. | docs only, không commit theo constraint |

## Files Changed

- `D:/Aureus/mql5/AureusProvider_v2.mq5`
- `D:/Aureus/.planning/quick/260503-neg-fix-spam-managepositiondecision-hold-pro/260503-neg-SUMMARY.md`

## Behavior Changed

- `LogManagementDecision(... action="HOLD", reason="profile_fallback", ...)` in lần đầu cho mỗi `symbol+magic+direction+reason`, lần sau bị suppress.
- `LogManagementDecision(... action="HOLD", reason="legacy_no_rule_matched", ...)` in lần đầu cho mỗi `symbol+magic+direction+reason`, lần sau bị suppress.
- `CLOSE` action không bị suppress vì helper trả `false` khi `action != "HOLD"`.
- HOLD reason khác không bị suppress.
- `PrintFormat("[ManagePositionDecision] ...")` giữ nguyên format cho log được emit.
- Target details `ticket` và `target_sl` giữ nguyên cho non-suppressed logs.

## Preserved Logs

- `CLOSE` decision logs vẫn visible.
- Market-close first detection `[MarketClosedCloseGuard] Set guard ...` vẫn visible.
- Close failure `[ManagePositionProfitBreakEvent] Close failed ...` vẫn visible.
- Error logs như `ORDER_FAILED`, `unknown_profile`, `HistoryCooldown` vẫn untouched.
- Non-HOLD decisions vẫn visible.

## Verification

| Check | Result |
|---|---|
| GitNexus impact before edit | Limitation: `npx gitnexus impact --repo Aureus --direction upstream LogManagementDecision` returned `{ "error": "Target 'LogManagementDecision' not found" }`. MQL5 symbol not indexed. |
| Task 1 source assertions | Passed: `hold decision suppression source assertions passed` |
| Task 1 diff check | Passed: `git diff --check -- mql5/AureusProvider_v2.mq5` |
| Task 2 narrow assertions | Passed: `narrow logging scope assertions passed` |
| MetaEditor availability | Not found in PATH: `MetaEditor64.exe`, `metaeditor64.exe`, `MetaEditor.exe`, `metaeditor.exe`. Compile not run. |
| GitNexus detect changes | Limitation: `npx gitnexus detect_changes --scope all` and `npx gitnexus detect-changes --repo Aureus --scope all` both returned unknown command. |
| Scope fallback | `git diff --check` passed; committed tracked source file only: `mql5/AureusProvider_v2.mq5`. |
| Unrelated untracked files | Preserved uncommitted: `mql5/AureusProvider_v2.ex5`, `stable/`. |

## Deviations from Plan

None - plan scope executed as written. Environment limitations documented for GitNexus MQL5 symbol lookup, GitNexus detect command, and MetaEditor compile availability.

## Auth Gates

None.

## Known Stubs

None.

## Threat Flags

None. No new endpoint, auth path, file access path, schema change, or external sink. Change only reduces low-value MT5 journal noise.

## Deferred Issues

- GitNexus CLI does not expose `detect_changes` / `detect-changes` command in this environment.
- MetaEditor CLI unavailable in PATH, so MQL5 compile not run.
- Untracked unrelated/generated files remain uncommitted per constraint: `mql5/AureusProvider_v2.ex5`, `stable/`.

## Self-Check: PASSED

- Summary file exists: `D:/Aureus/.planning/quick/260503-neg-fix-spam-managepositiondecision-hold-pro/260503-neg-SUMMARY.md`
- Code commit exists: `c4e20f3`
- Modified source exists: `D:/Aureus/mql5/AureusProvider_v2.mq5`
