---
phase: 260503-ltx-khi-th-tr-ng-ng-c-a-th-kh-ng-close-c-l-n
verified: 2026-05-03T00:00:00Z
status: human_needed
score: 4/4 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Compile mql5/AureusProvider_v2.mq5 in MetaEditor/MetaTrader"
    expected: "EA compiles without MQL5 syntax/type errors."
    why_human: "MetaEditor compiler not available on CLI PATH in verifier environment."
  - test: "Run provider while market closed with close-eligible position group"
    expected: "First close failure logs retcode/comment and sets guard; later timer loops log guard skip and do not emit repeated action CLOSE for same symbol+magic+direction until TTL expires."
    why_human: "Requires MT5 runtime, broker/server market-closed retcode, and live/ticked timer behavior."
---

# Quick 260503-ltx Verification Report

**Task Goal:** Khi thị trường đóng cửa thì không close được lệnh nhưng bị lặp lại liên tục. Thêm điều kiện để stop không xử lý nữa khi close trả về market closed trong AureusProvider_v2.
**Verified:** 2026-05-03T00:00:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Khi MT5 trả về TRADE_RETCODE_MARKET_CLOSED cho close position, provider không lặp lại quản lý close cùng symbol+magic+direction trong lúc market vẫn đóng. | VERIFIED | `ClosePositionTickets` checks `IsMarketClosedCloseGuardActive(symbol, magic, pos_type_str, guardUntil)` before close decision, returns `false` on active guard, and sets guard when `trade.ResultRetcode()` equals `TRADE_RETCODE_MARKET_CLOSED` or `10018`. |
| 2 | Log `Closing stale profitable single position.` hoặc action CLOSE tương đương không spam liên tục sau lỗi `CTrade::OrderSend ... [market closed]`. | VERIFIED | Guard check occurs before `LogManagementDecision(... "CLOSE" ...)`, so active guard skips before action CLOSE logging. Skip log uses `[MarketClosedCloseGuard] Skip close ... reason=MARKET_CLOSED`. |
| 3 | Các close failure khác vẫn được log rõ ràng và không bị nuốt lỗi. | VERIFIED | Failed `trade.PositionClose` path always reads `trade.ResultRetcode()`, maps via `RetcodeToReason(retcode)`, reads `trade.ResultComment()`, and prints ticket/retcode/reason/comment before market-closed-specific guard branch. Non-market-closed failures continue loop. |
| 4 | Khi market mở lại hoặc guard hết hạn, logic quản lý position tiếp tục hoạt động bình thường. | VERIFIED | Guard TTL set by `TimeCurrent() + 5 * 60`; active check returns true only while `guardUntil > TimeCurrent()`. Expired guard no longer blocks `ClosePositionTickets`. |

**Score:** 4/4 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `D:/Aureus/mql5/AureusProvider_v2.mq5` | Market-closed close retry guard in existing close helper | VERIFIED | File exists. Contains `MarketClosedCloseGuardState`, guard array, find/ensure/active/set helpers, `TRADE_RETCODE_MARKET_CLOSED`, `10018`, `trade.ResultRetcode()`, `trade.ResultComment()`. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `ClosePositionTickets` | `trade.PositionClose` | retcode/comment inspection after failed close | WIRED | `bool ok = trade.PositionClose(tickets[i]);` then on failure reads `trade.ResultRetcode()` and `trade.ResultComment()`. |
| `ProcessLegacyPositionsByType` | `ClosePositionTickets` | `legacy_stale_profitable_single` path | WIRED | Legacy single stale profitable path calls `ClosePositionTickets(... "legacy_stale_profitable_single", "P-08")`. |
| Management profile close paths | `ClosePositionTickets` | severe risk/basket recovery paths | WIRED | Conservative/trend_runner/breakout_protect/basket_escape close paths still call shared helper, so guard applies to all close attempts in helper. |

### Guard Scope and Recovery

| Check | Status | Evidence |
|-------|--------|----------|
| Scoped by symbol | VERIFIED | Guard state stores and matches `symbol`. |
| Scoped by magic | VERIFIED | Guard state stores and matches `magic`. |
| Scoped by direction | VERIFIED | Guard state stores and matches `direction` using `pos_type_str` (`BUY`/`SELL`). |
| Bounded TTL | VERIFIED | `SetMarketClosedCloseGuard` uses `TimeCurrent() + 5 * 60`. |
| Recoverable after expiry | VERIFIED | `IsMarketClosedCloseGuardActive` only blocks if `guardUntil > TimeCurrent()`. |
| Not global | VERIFIED | Guard lookup requires all three key fields; unrelated symbol/magic/direction groups unaffected. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Only source file changed in task commit | `git -C "D:/Aureus" diff --name-only HEAD~1..HEAD` | `mql5/AureusProvider_v2.mq5` | PASS |
| Whitespace diff check | `git -C "D:/Aureus" diff --check -- mql5/AureusProvider_v2.mq5` | No output, exit 0 | PASS |
| GitNexus impact limitation reproduced | `cd "D:/Aureus" && npx gitnexus impact --repo Aureus --direction upstream ClosePositionTickets` | `{ "error": "Target 'ClosePositionTickets' not found" }` | PASS |
| GitNexus detect_changes limitation reproduced | `cd "D:/Aureus" && npx gitnexus detect_changes --scope all` | `error: unknown command 'detect_changes'` | PASS |
| MetaEditor compile availability | `command -v metaeditor64.exe || command -v MetaEditor64.exe || command -v metaeditor.exe || command -v MetaEditor.exe || true` | No output | SKIP |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| QUICK-260503-LTX | `D:/Aureus/.planning/quick/260503-ltx-khi-th-tr-ng-ng-c-a-th-kh-ng-close-c-l-n/260503-ltx-PLAN.md` | Stop repeated close attempts when MT5 close returns market closed, scoped and recoverable, source-only change. | SATISFIED | Guard added in `ClosePositionTickets`, scoped by symbol+magic+direction, TTL 5 minutes, only commit diff file is `mql5/AureusProvider_v2.mq5`. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None in modified source slice | N/A | N/A | N/A | No TODO/FIXME/placeholder or empty-handler stub found in guard implementation. |

### GitNexus and Compile Limitations

| Limitation | Status | Evidence |
|------------|--------|----------|
| GitNexus impact cannot resolve MQL5 helper symbol | DOCUMENTED | Plan and summary document `Target 'ClosePositionTickets' not found`; verifier reproduced same output. |
| GitNexus detect_changes CLI unavailable | DOCUMENTED | Summary documents unknown command; verifier reproduced `error: unknown command 'detect_changes'`. |
| MQL5 compiler unavailable on CLI PATH | DOCUMENTED | Summary documents empty compiler lookup; verifier reproduced no MetaEditor command in PATH. |

### Working Tree Scope Note

`git -C "D:/Aureus" status --short` shows untracked `D:/Aureus/.planning/quick/260503-ltx-khi-th-tr-ng-ng-c-a-th-kh-ng-close-c-l-n/`, `D:/Aureus/mql5/AureusProvider_v2.ex5`, and `D:/Aureus/stable/`. Commit-scope check for task commit shows only `D:/Aureus/mql5/AureusProvider_v2.mq5` changed. The requested VERIFICATION.md creation adds this quick planning file and does not alter source.

### Human Verification Required

#### 1. MetaEditor compile

**Test:** Compile `D:/Aureus/mql5/AureusProvider_v2.mq5` in MetaEditor/MetaTrader.
**Expected:** EA compiles without MQL5 syntax/type errors.
**Why human:** MetaEditor compiler unavailable on verifier CLI PATH.

#### 2. MT5 market-closed runtime behavior

**Test:** Run provider with close-eligible position group while broker returns market-closed for close attempts.
**Expected:** First failed close logs ticket/retcode/reason/comment and sets guard. Later timer loops for same symbol+magic+direction skip close before action CLOSE logging until 5 minute TTL expires. Unrelated symbol/magic/direction groups still attempt normal close. Non-market-closed failures still log retcode/comment.
**Why human:** Requires MT5 runtime, broker retcode behavior, and timer-loop observation.

### Gaps Summary

No automated code gaps found. Phase goal achieved at source level. Status remains `human_needed` because compile and live MT5 market-closed behavior cannot be verified in current CLI environment.

---

_Verified: 2026-05-03T00:00:00Z_
_Verifier: Claude (gsd-verifier)_
