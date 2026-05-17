---
phase: 260517-tne-implement-safe-stale-single-handling-tro
verified: 2026-05-17T00:00:00Z
status: passed
score: 4/4 must-haves verified
overrides_applied: 0
---

# Quick 260517-tne Verification Report

**Task Goal:** Implement safe stale single handling trong `ProcessLegacyPositionsByType` theo report 260517-sf2. Mặc định: `net_profit >= InpBEProfitTarget` thì HOLD/không close; `0 < net_profit < InpBEProfitTarget` thì `MovePositionsSL` về breakeven nếu SL chưa bảo vệ, không close market; giữ logic âm hiện tại. Build/verify MQL5 theo `mql5/Build_Rules.md`.
**Verified:** 2026-05-17T00:00:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Legacy single stale position with `net_profit >= InpBEProfitTarget` is not closed by market order. | VERIFIED | `mql5/AureusProvider_v2.mq5:2117-2124` stale single branch logs `HOLD` reason `legacy_stale_profit_target_reached` and returns; no `ClosePositionTickets` in branch. |
| 2 | Legacy single stale position with `0 < net_profit < InpBEProfitTarget` moves SL toward breakeven when SL is not already protective, instead of market close. | VERIFIED | `mql5/AureusProvider_v2.mq5:2117-2139` computes `weighted_avg_open_price`, checks BUY/SELL protective SL, logs HOLD when protective, otherwise calls `MovePositionsSL(... PROFILE_LEGACY ..., weighted_avg_open_price, "MOVE_SL", "legacy_stale_single_breakeven_protect", "P-08")`. |
| 3 | Legacy loss handling and basket recovery logic remain unchanged. | VERIFIED | `mql5/AureusProvider_v2.mq5:2107-2115` retains `ClosePositionTickets(... "severe_risk_guard", "P-05/P-06")` and `ClosePositionTickets(... "legacy_basket_recovery_profit", "P-07")` before stale single branch. |
| 4 | `AureusProvider_v2.mq5` builds with MetaEditor using `mql5/Build_Rules.md`. | VERIFIED | `mql5/AureusProvider_v2_compile.log:52` says `Result: 0 errors, 0 warnings, 3234 msec elapsed`. |

**Score:** 4/4 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `mql5/AureusProvider_v2.mq5` | Safe `ProcessLegacyPositionsByType` stale single handling | VERIFIED | Exists; gsd artifact check passed. Function substantive at lines 2094-2143 with hold, SL-protect, retained close paths. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `ManagePositionProfitBreakEvent` | `ProcessLegacyPositionsByType` | `ProcessPositionsByType` legacy/default route | VERIFIED | Lines 2408 -> 2304-2339: manager calls `ProcessPositionsByType`; default/legacy path calls `ProcessLegacyPositionsByType`. gsd path resolver failed because quick plan used repo-relative path outside current worktree, manual check passed. |
| `ProcessLegacyPositionsByType` | `MovePositionsSL` | near-breakeven stale single protection | VERIFIED | Line 2138 calls `MovePositionsSL(symbol, magic, target_type, PROFILE_LEGACY, ...)` with reason `legacy_stale_single_breakeven_protect`. |
| `ProcessLegacyPositionsByType` | `ClosePositionTickets` | retained negative risk guard and basket recovery only | VERIFIED | Lines 2109 and 2114 retain close calls for `severe_risk_guard` and `legacy_basket_recovery_profit`; stale profitable single branch has no close call and no `legacy_stale_profitable_single` reason. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|---|---|---|---|---|
| `ProcessLegacyPositionsByType` | `net_profit`, `tickets`, `weighted_price_sum`, `total_volume`, `earliest_open_time` | `ManagePositionProfitBreakEvent` aggregates live MT5 positions at lines 2379-2408; `CalculatePositionGroupCosts` computes net profit at lines 2101-2105. | Yes | FLOWING |
| `ProcessLegacyPositionsByType` | `current_sl` | `PositionSelectByTicket(tickets[0])` then `PositionGetDouble(POSITION_SL)` at lines 2126-2128. | Yes | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Static stale single assertions | Python checked function body for hold target, breakeven move, protective BUY/SELL checks, absence of `legacy_stale_profitable_single`, retained close reasons. | All checks `True`. | PASS |
| MetaEditor compile | Compile log read from `D:/Aureus/mql5/AureusProvider_v2_compile.log`. | `Result: 0 errors, 0 warnings`. | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| `QUICK-260517-TNE` | `260517-tne-PLAN.md` | Safe legacy stale single handling and clean MQL5 build. | SATISFIED | All four must-haves verified; compile log clean. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---:|---|---|---|
| `mql5/AureusProvider_v2.mq5` | 1274 | grep matched `return StringToDouble(...)` due broad `return` scan context | Info | Not stub; unrelated parser return. No TODO/FIXME/placeholder or `legacy_stale_profitable_single` found. |

### Human Verification Required

None.

### Gaps Summary

No blocking gaps. Goal achieved: profitable legacy stale single no longer market-closes; small-profit stale single protects via breakeven SL only when needed; loss and basket close paths remain; MQL5 compile clean.

---

_Verified: 2026-05-17T00:00:00Z_
_Verifier: Claude (gsd-verifier)_
