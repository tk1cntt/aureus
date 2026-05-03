---
phase: 260503-neg-fix-spam-managepositiondecision-hold-pro
verified: 2026-05-03T09:58:47Z
status: human_needed
score: 5/5 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Compile mql5/AureusProvider_v2.mq5 with MetaEditor/MetaEditor64"
    expected: "MQL5 compile succeeds with no errors after HoldDecisionLogState and ShouldSuppressRepeatedHoldDecisionLog additions"
    why_human: "MetaEditor CLI not available in PATH in verifier environment"
---

# Quick 260503-neg: HOLD Decision Spam Suppression Verification Report

**Task Goal:** Fix spam `ManagePositionDecision` HOLD/profile_fallback/legacy_no_rule_matched logs in `AureusProvider_v2`; repeated HOLD low-value decision logs must be suppressed or rate-limited by `symbol+magic+direction+reason` without affecting non-HOLD, close, error, or market-closed first-detection logs.
**Verified:** 2026-05-03T09:58:47Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | Repeated `ManagePositionDecision` HOLD logs for `reason=profile_fallback` do not spam every tick for same `symbol+magic+direction+reason`. | VERIFIED | `ProcessPositionsByType` calls `LogManagementDecision(..., "HOLD", "profile_fallback", ...)`; `LogManagementDecision` routes matching HOLD reason through `ShouldSuppressRepeatedHoldDecisionLog`; helper returns `true` when existing `symbol+magic+direction+reason` key found. |
| 2 | Repeated `ManagePositionDecision` HOLD logs for `reason=legacy_no_rule_matched` do not spam every tick for same `symbol+magic+direction+reason`. | VERIFIED | `ProcessLegacyPositionsByType` calls `LogManagementDecision(..., "HOLD", "legacy_no_rule_matched", ...)`; helper suppresses repeat when same `symbol`, `magic`, `direction`, and `reason` already recorded. |
| 3 | First occurrence remains visible for diagnostics. | VERIFIED | `ShouldSuppressRepeatedHoldDecisionLog` appends new key then returns `false`; `PrintFormat("[ManagePositionDecision]...")` executes on first key occurrence. |
| 4 | CLOSE actions, market-close first detection logs, close failure/error logs, and non-HOLD decisions remain visible. | VERIFIED | Helper has `if(action != "HOLD") return false`; `LogManagementDecision(... "CLOSE" ...)` remains before `trade.PositionClose`; `[MarketClosedCloseGuard] Set guard` `PrintFormat` remains in `SetMarketClosedCloseGuard`; close failure `PrintFormat("[ManagePositionProfitBreakEvent] Close failed ...")` remains. |
| 5 | Scope stays surgical: only provider MQL5 source plus summary/verification artifacts. | VERIFIED | Plan artifacts exist; source change localized around `HoldDecisionLogState`, `g_holdDecisionLogs`, helper, and `LogManagementDecision`. `git status --short` shows untracked quick directory, generated `mql5/AureusProvider_v2.ex5`, and `stable/`; no verifier commit made. |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `D:/Aureus/mql5/AureusProvider_v2.mq5` | Provider-local HOLD decision log suppression for repeated low-value reasons; contains `LogManagementDecision`. | VERIFIED | File exists. Contains `HoldDecisionLogState`, `g_holdDecisionLogs`, `ShouldSuppressRepeatedHoldDecisionLog`, and guarded `LogManagementDecision`. Not stub: real array-backed key store and early return before print. Wired: all decision call sites already flow through `LogManagementDecision`. |
| `D:/Aureus/.planning/quick/260503-neg-fix-spam-managepositiondecision-hold-pro/260503-neg-SUMMARY.md` | Execution summary with verification, GitNexus limitation, compile limitation, changed scope. | VERIFIED | File exists. Documents GitNexus impact limitation, detect command limitation, MetaEditor unavailable, scope, preserved logs, and changed behavior. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `LogManagementDecision` | `PrintFormat([ManagePositionDecision])` | HOLD-only repeated reason suppression before print | WIRED | `if(action == "HOLD" && (reason == "profile_fallback" || reason == "legacy_no_rule_matched") && ShouldSuppressRepeatedHoldDecisionLog(...)) return;` occurs before single `[ManagePositionDecision]` `PrintFormat`. |
| `ProcessPositionsByType` | `LogManagementDecision(profile_fallback)` | Same `symbol+magic+direction+reason` emits once | WIRED | `ProcessPositionsByType` calls `LogManagementDecision(symbol, magic, pos_type_str, profile, "HOLD", "profile_fallback", ...)`; helper key includes `symbol`, `magic`, `direction`, `reason`. |
| `ProcessLegacyPositionsByType` | `LogManagementDecision(legacy_no_rule_matched)` | Same `symbol+magic+direction+reason` emits once | WIRED | Legacy call remains `LogManagementDecision(symbol, magic, pos_type_str, PROFILE_LEGACY, "HOLD", "legacy_no_rule_matched", ...)`; helper key includes required fields. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|---|---|---|---|---|
| `D:/Aureus/mql5/AureusProvider_v2.mq5` | `action`, `reason`, `symbol`, `magic`, `direction` into `LogManagementDecision` | Runtime position management call sites (`ProcessPositionsByType`, `ProcessLegacyPositionsByType`, close/modify helpers) | Yes | FLOWING — suppression uses actual parameters passed by existing management flow, not hardcoded test values. |
| `D:/Aureus/mql5/AureusProvider_v2.mq5` | `g_holdDecisionLogs[]` | First target HOLD log inserts key; repeated target HOLD checks same array | Yes | FLOWING — helper records real runtime key and suppresses only repeat target reasons. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Source proves narrow suppression and preserved logs | `python` source assertion over `D:/Aureus/mql5/AureusProvider_v2.mq5` | PASS: single decision format, helper action/reason guards, key contains symbol/magic/direction/reason, print after suppress, close log call, market-closed guard print, close failure log, `trade.PositionClose` all present | PASS |
| MQL5 diff has no whitespace errors | `git -C "D:/Aureus" diff --check -- "mql5/AureusProvider_v2.mq5"` | PASS: no output | PASS |
| MetaEditor availability | `command -v MetaEditor64.exe || command -v metaeditor64.exe || command -v MetaEditor.exe || command -v metaeditor.exe || true` | No executable found | SKIP — human compile needed |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| `QUICK-260503-NEG` | `D:/Aureus/.planning/quick/260503-neg-fix-spam-managepositiondecision-hold-pro/260503-neg-PLAN.md` | Reduce repeated HOLD `profile_fallback` / `legacy_no_rule_matched` log noise without hiding close/error/non-HOLD/market-close first detection logs. | SATISFIED | All five observable truths verified in source. Compile remains human check because MetaEditor unavailable. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---|---|---|---|
| `D:/Aureus/mql5/AureusProvider_v2.mq5` | 1187 | Grep matched `return StringToDouble(...)` during broad empty-return scan | INFO | False positive; not stub, unrelated parser return. No TODO/FIXME/placeholder/empty handler found in changed area. |

### Human Verification Required

#### 1. MQL5 compile

**Test:** Compile `D:/Aureus/mql5/AureusProvider_v2.mq5` with MetaEditor/MetaEditor64.
**Expected:** Compile succeeds with no MQL5 errors after adding `HoldDecisionLogState` and `ShouldSuppressRepeatedHoldDecisionLog`.
**Why human:** MetaEditor CLI not available in PATH in verifier environment.

### Gaps Summary

No automated goal gaps found. Runtime-source behavior satisfies requested suppression and preservation rules. Status remains `human_needed` only because MQL5 compile could not run here.

### Notes

- GitNexus limitation documented in summary: MQL5 `LogManagementDecision` target not found by GitNexus impact; detect command unavailable. Accepted for verification because user focus allows GitNexus limitations if documented.
- Verifier did not commit.

---

_Verified: 2026-05-03T09:58:47Z_
_Verifier: Claude (gsd-verifier)_
