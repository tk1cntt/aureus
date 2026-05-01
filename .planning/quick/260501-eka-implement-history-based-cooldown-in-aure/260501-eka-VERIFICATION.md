---
phase: 260501-eka-implement-history-based-cooldown-in-aure
verified: 2026-05-01T03:36:03Z
status: passed
score: 8/8 must-haves verified
overrides_applied: 0
---

# Quick 260501-eka Verification Report

**Task Goal:** Implement history-based cooldown in `AureusProvider_v2` scoped by symbol + magic + direction.
**Verified:** 2026-05-01T03:36:03Z
**Status:** passed

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Cooldown scope is symbol + magic + direction, not whole symbol/_Symbol. | VERIFIED | `HistoryCooldownState` stores `symbol`, `magic`, `direction`; `FindHistoryCooldownIndex`, `EnsureHistoryCooldownState`, and `IsHistoryCooldownActive` all key by these three fields. Cooldown helpers do not use `_Symbol` for scope. |
| 2 | Bootstrap from history in OnInit. | VERIFIED | `OnInit` parses `InpSymbols`, initializes `g_contexts` and `g_historyCooldowns`, then calls `BootstrapHistoryCooldowns()`. Bootstrap uses `HistorySelect`, `HistoryDealsTotal`, and applies deals through `ApplyCloseDealToHistoryCooldown(..., "bootstrap")`. |
| 3 | Realtime update from OnTradeTransaction on DEAL_ENTRY_OUT. | VERIFIED | `OnTradeTransaction` returns unless `trans.type == TRADE_TRANSACTION_DEAL_ADD` and `DEAL_ENTRY == DEAL_ENTRY_OUT`, then calls `ApplyCloseDealToHistoryCooldown(trans.deal, "realtime")`. |
| 4 | ExecuteOpenOrder rejects supported symbol/scope active cooldown with NACK HISTORY_COOLDOWN_ACTIVE. | VERIFIED | `ExecuteOpenOrder` checks `FindContextIndex(symbol) < 0` first, then calls `IsHistoryCooldownActive(symbol, magic, direction, cooldownUntil)` before duplicate active order checks, terminal trade checks, `SendACK`, and `RecordCmdId`; active cooldown logs rejection and calls `SendNACK(cmdId, "HISTORY_COOLDOWN_ACTIVE")`. |
| 5 | Unsupported symbol remains local ignore/no terminal NACK. | VERIFIED | Unsupported `OPEN_ORDER` branch logs `SYMBOL_NOT_ALLOWED`, has `SendNACK` commented out, and returns before cooldown check. |
| 6 | CLOSE_ORDER/REQUEST/backfill are not blocked. | VERIFIED | `HISTORY_COOLDOWN_ACTIVE` and `IsHistoryCooldownActive` appear only in `ExecuteOpenOrder`; `ExecuteCloseOrder`, request handlers, and backfill paths do not call cooldown enforcement. |
| 7 | Single SL close sets 30m cooldown. | VERIFIED | `ApplyCloseDealToHistoryCooldown` checks `reason == DEAL_REASON_SL` and calls `SetHistoryCooldown(idx, closeTime + 30 * 60, "single_sl", source)`. |
| 8 | Multiple same-scope close within 2 seconds sets 60m cooldown. | VERIFIED | Same helper compares current close time to `g_historyCooldowns[idx].last_close_time` within `<= 2` seconds for the same symbol + magic + direction state and calls `SetHistoryCooldown(idx, closeTime + 60 * 60, "multi_close_2s", source)`. |

**Score:** 8/8 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `D:/Aureus/mql5/AureusProvider_v2.mq5` | Provider-local history cooldown structs/state helpers, OnInit bootstrap, OnTradeTransaction update, and ExecuteOpenOrder enforcement | VERIFIED | File contains `HistoryCooldownState`, `g_historyCooldowns`, helper functions, `BootstrapHistoryCooldowns`, realtime apply call, and `HISTORY_COOLDOWN_ACTIVE` NACK path. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `OnInit` | history cooldown state array | bootstrap helper scans `HistorySelect`/`HistoryDealsTotal` after `InpSymbols` parsing | WIRED | `ArrayResize(g_historyCooldowns, 0)` and `BootstrapHistoryCooldowns()` occur after symbol parsing/context initialization; bootstrap iterates history deals. |
| `OnTradeTransaction` | history cooldown state array | `DEAL_ENTRY_OUT` close deal updates cooldown by symbol + magic + original direction | WIRED | `DirectionFromCloseDealType` maps close deal type to original direction; realtime call passes the deal ticket into the shared apply helper. |
| `ExecuteOpenOrder` | `SendNACK` | supported-symbol cooldown check before ACK and `RecordCmdId` | WIRED | Cooldown check is after unsupported-symbol ignore and before `SendACK(cmdId)`/`RecordCmdId(cmdId)`. |

### Data-Flow Trace

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `AureusProvider_v2.mq5` | `g_historyCooldowns[].cooldown_until` | MT5 history deals via `HistoryDealGet*` during bootstrap and realtime transaction handling | Yes | FLOWING |
| `ExecuteOpenOrder` | `cooldownUntil` | `IsHistoryCooldownActive(symbol, magic, direction, cooldownUntil)` reads state populated from actual close deals | Yes | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Static invariant: required tokens and ordering | Read/inspection of `AureusProvider_v2.mq5` | Required helpers, constants, and order of unsupported-symbol check -> cooldown NACK -> ACK verified in code | PASS |
| MT5 runtime cooldown behavior | Not run | Requires MetaTrader terminal/history/order event simulation | SKIPPED |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| QUICK-260501-EKA | `260501-eka-PLAN.md` | Implement history-based cooldown scoped by symbol + magic + direction in `AureusProvider_v2` | SATISFIED | All focus truths and plan must-haves verified in `AureusProvider_v2.mq5`. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `D:/Aureus/mql5/AureusProvider_v2.mq5` | N/A | None blocking for cooldown goal | Info | No placeholder, whole-symbol cooldown, or unwired cooldown enforcement found. |

### Human Verification Required

None for automated code-level goal verification. MT5 runtime smoke testing would still be useful for broker/compiler-specific behavior, but no code-level uncertainty blocks this verification.

### Gaps Summary

No gaps found. The implementation satisfies the requested history-based cooldown behavior with symbol + magic + direction scope, bootstrap and realtime data flow, scoped `OPEN_ORDER` rejection, and no blocking of unsupported symbols or non-open command flows.

---

_Verified: 2026-05-01T03:36:03Z_
_Verifier: Claude (gsd-verifier)_
