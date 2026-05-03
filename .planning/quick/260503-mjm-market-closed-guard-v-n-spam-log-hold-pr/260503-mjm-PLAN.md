---
phase: 260503-mjm-market-closed-guard-v-n-spam-log-hold-pr
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - mql5/AureusProvider_v2.mq5
autonomous: true
requirements:
  - QUICK-260503-MJM
must_haves:
  truths:
    - "Provider pre-checks symbol tradability/session state before any market-close-sensitive close attempt, so market-closed state is handled before trade.PositionClose instead of relying on close failure logging."
    - "When market closed or close guard active for a symbol+magic+direction group, group processing returns early and does not emit repeated ManagePositionDecision HOLD/profile_fallback/no_rule logs on every tick/timer."
    - "Existing market-closed guard remains scoped by symbol+magic+direction and recovers after bounded TTL; unrelated groups are not blocked."
    - "Non-market-closed close failures still log retcode/comment and are not hidden."
  artifacts:
    - path: "mql5/AureusProvider_v2.mq5"
      provides: "Pre-close market tradability guard and quiet group skip in AureusProvider_v2"
      contains: "ClosePositionTickets"
    - path: "mql5/AureusProvider_v2.mq5"
      provides: "Group-level early return before profile fallback/HOLD logging"
      contains: "ProcessPositionsByType"
  key_links:
    - from: "ProcessPositionsByType"
      to: "market-closed guard helpers"
      via: "early group skip before ResolveManagementProfile and LogManagementDecision"
      pattern: "IsMarketClosedCloseGuardActive"
    - from: "ClosePositionTickets"
      to: "trade.PositionClose"
      via: "tradability/session pre-check before close call"
      pattern: "PositionClose"
    - from: "symbol tradability pre-check"
      to: "SetMarketClosedCloseGuard"
      via: "guard set before returning early when symbol cannot close"
      pattern: "SetMarketClosedCloseGuard"
---

<objective>
Chặn spam close/HOLD khi market closed trong `mql5/AureusProvider_v2.mq5` bằng pre-check trước close và early skip group.

Purpose: user thấy market closed guard/log vẫn spam; cần stop xử lý group sớm khi symbol không thể close, không gọi `trade.PositionClose()` để lấy lỗi market closed làm hành vi chính.
Output: một thay đổi source MQL5 surgical trong `mql5/AureusProvider_v2.mq5`, không đổi DB, không đổi service Python.
</objective>

<execution_context>
@D:/Aureus/.claude/get-shit-done/workflows/execute-plan.md
@D:/Aureus/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@D:/Aureus/.planning/STATE.md
@D:/Aureus/CLAUDE.md
@D:/Aureus/RUN_SERVICES.md
@D:/Aureus/mql5/AureusProvider_v2.mq5
@D:/Aureus/.planning/quick/260503-ltx-khi-th-tr-ng-ng-c-a-th-kh-ng-close-c-l-n/260503-ltx-SUMMARY.md
@D:/Aureus/.planning/quick/260503-ltx-khi-th-tr-ng-ng-c-a-th-kh-ng-close-c-l-n/260503-ltx-VERIFICATION.md

Important prior result: quick `260503-ltx` added close-failure-based guard in `ClosePositionTickets`, but user correction says do not rely on close failure logging as main behavior. This plan must add pre-check before `trade.PositionClose()` and quiet group skip before `ManagePositionDecision` HOLD/profile_fallback/no_rule logs.

Existing source landmarks from `mql5/AureusProvider_v2.mq5`:
- `MarketClosedCloseGuardState g_marketClosedCloseGuards[]` already exists.
- `IsMarketClosedCloseGuardActive(symbol, magic, direction, guardUntil)` checks scoped TTL.
- `SetMarketClosedCloseGuard(symbol, magic, direction)` sets 5 minute guard and logs once only if extending.
- `ClosePositionTickets(...)` currently checks existing guard before CLOSE log, then calls `trade.PositionClose(tickets[i])` and sets guard on retcode `TRADE_RETCODE_MARKET_CLOSED` or `10018`.
- `ProcessPositionsByType(...)` currently resolves profile and may log `profile_fallback` before delegating to profile handlers.
- Profile handlers currently log HOLD/no_rule reasons even when guard is active unless caller returns early.

GitNexus requirement:
- Before editing any MQL5 function, run impact analysis for target symbols. Try:
  - `npx gitnexus impact --repo Aureus --direction upstream ClosePositionTickets`
  - `npx gitnexus impact --repo Aureus --direction upstream ProcessPositionsByType`
  - If adding helper, no pre-existing symbol impact exists; document new helper.
- If GitNexus reports target not found for MQL5 symbols, record exact output in summary and proceed with source inspection. Previous quick showed `Target 'ClosePositionTickets' not found`.
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add pre-close market tradability guard</name>
  <files>mql5/AureusProvider_v2.mq5</files>
  <behavior>
    - Source check: a helper exists that checks `SymbolInfoInteger(symbol, SYMBOL_TRADE_MODE)` and rejects disabled/close-prohibited modes before close.
    - Source check: helper checks current session/tradability using MQL5 symbol/session APIs where available, without inventing broker-specific constants.
    - Source check: `ClosePositionTickets` calls this helper before `LogManagementDecision(... "CLOSE" ...)` and before `trade.PositionClose(...)`.
    - Source check: when helper says close unavailable, code calls `SetMarketClosedCloseGuard(symbol, magic, pos_type_str)` and returns without calling `trade.PositionClose`.
  </behavior>
  <action>Run GitNexus impact for `ClosePositionTickets` before edit. Add small helper near existing market-closed guard helpers, for example `bool IsSymbolCloseAvailableNow(string symbol, string &reason)`, using MQL5 symbol trade mode/session information to determine whether close can be attempted now. Keep helper provider-local and surgical. In `ClosePositionTickets`, call helper after existing active-guard check and before `LogManagementDecision(... "CLOSE" ...)`. If close unavailable, set existing scoped market-closed guard and return `false` without calling `trade.PositionClose`. Do not remove existing retcode/comment failure logging; it remains fallback for race conditions where pre-check passes but server still returns market closed. Do not add broad abstractions or touch unrelated DCA/order-open code.</action>
  <verify>
    <automated>cd "D:/Aureus" && npx gitnexus impact --repo Aureus --direction upstream ClosePositionTickets</automated>
    <automated>cd "D:/Aureus" && node -e "const fs=require('fs'); const s=fs.readFileSync('mql5/AureusProvider_v2.mq5','utf8'); const close=s.slice(s.indexOf('bool ClosePositionTickets'), s.indexOf('bool MovePositionsSL')); const helper=/bool\s+IsSymbolCloseAvailableNow\s*\(/.test(s); const tradeMode=/SYMBOL_TRADE_MODE/.test(s); const pre=close.indexOf('IsSymbolCloseAvailableNow')>=0 && close.indexOf('IsSymbolCloseAvailableNow')<close.indexOf('LogManagementDecision') && close.indexOf('LogManagementDecision')<close.indexOf('trade.PositionClose'); const guard=close.indexOf('SetMarketClosedCloseGuard')>=0 && close.indexOf('SetMarketClosedCloseGuard')<close.indexOf('trade.PositionClose'); if(!helper||!tradeMode||!pre||!guard){throw new Error(JSON.stringify({helper,tradeMode,pre,guard}));} console.log('pre-close guard assertions passed');"</automated>
  </verify>
  <done>`ClosePositionTickets` pre-checks market close/trade-mode state and returns before CLOSE log/`trade.PositionClose` when symbol cannot close; existing failure logging still handles server-side race retcodes.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Skip guarded groups before fallback and HOLD logs</name>
  <files>mql5/AureusProvider_v2.mq5</files>
  <behavior>
    - Source check: `ProcessPositionsByType` computes direction string and checks `IsMarketClosedCloseGuardActive(symbol, magic, pos_type_str, guardUntil)` before `ResolveManagementProfile`.
    - Source check: active guard returns early from group processing before any `LogManagementDecision` call in `ProcessPositionsByType`.
    - Source check: skip logging is bounded/non-spammy; do not print per timer forever for same active guard. Accept no log on active guard, or log only when guard is newly set/extended.
    - Source check: normal unguarded groups still route to conservative/trend_runner/breakout_protect/basket_escape/legacy handlers unchanged.
  </behavior>
  <action>Run GitNexus impact for `ProcessPositionsByType` before edit. Modify `ProcessPositionsByType` only enough to compute `pos_type_str` once at function start, check active market-closed guard before `ResolveManagementProfile`, and return early when active. Do not call `LogManagementDecision` on active guard. This specifically prevents repeated `profile_fallback`, `legacy_no_rule_matched`, and other HOLD/no_rule logs while same symbol+magic+direction is guarded. Keep profile routing behavior identical when no guard is active.</action>
  <verify>
    <automated>cd "D:/Aureus" && npx gitnexus impact --repo Aureus --direction upstream ProcessPositionsByType</automated>
    <automated>cd "D:/Aureus" && node -e "const fs=require('fs'); const s=fs.readFileSync('mql5/AureusProvider_v2.mq5','utf8'); const fn=s.slice(s.indexOf('void ProcessPositionsByType'), s.indexOf('//+------------------------------------------------------------------+\n//| Manage profit/breakeven')); const guard=fn.indexOf('IsMarketClosedCloseGuardActive')>=0; const beforeResolve=fn.indexOf('IsMarketClosedCloseGuardActive')<fn.indexOf('ResolveManagementProfile'); const beforeLog=fn.indexOf('IsMarketClosedCloseGuardActive')<fn.indexOf('LogManagementDecision'); const hasReturn=/IsMarketClosedCloseGuardActive[\s\S]*?return\s*;/.test(fn); if(!guard||!beforeResolve||!beforeLog||!hasReturn){throw new Error(JSON.stringify({guard,beforeResolve,beforeLog,hasReturn}));} console.log('group early-skip assertions passed');"</automated>
  </verify>
  <done>Active market-closed guard stops group processing before profile fallback/HOLD/no_rule logs; unguarded groups keep existing management behavior.</done>
</task>

<task type="auto">
  <name>Task 3: Verify source scope and compile availability</name>
  <files>mql5/AureusProvider_v2.mq5</files>
  <action>Run source-level checks and compile attempt. Use MetaEditor/MetaTrader CLI if available on PATH. If unavailable, document exact command and empty/not-found output in summary. Run `git diff --check -- mql5/AureusProvider_v2.mq5`. Run GitNexus detect changes if tool exists; if installed CLI lacks command, document exact limitation. Do not create or modify verification docs unless execute-plan summary requires it.</action>
  <verify>
    <automated>cd "D:/Aureus" && git diff --check -- mql5/AureusProvider_v2.mq5</automated>
    <automated>cd "D:/Aureus" && command -v metaeditor64.exe || command -v MetaEditor64.exe || command -v metaeditor.exe || command -v MetaEditor.exe || true</automated>
    <automated>cd "D:/Aureus" && (npx gitnexus detect_changes --scope all || true)</automated>
  </verify>
  <done>Only `mql5/AureusProvider_v2.mq5` source changed; source assertions pass; compile attempted when MetaEditor exists or limitation documented; GitNexus limitations documented if MQL5 symbols or detect_changes unavailable.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| MT5 provider -> broker trade server | `trade.PositionClose` crosses from local EA logic to broker execution; market/session state can change between checks. |
| Timer/tick loop -> provider logs | Repeated `ManagePositionProfitBreakEvent` can spam logs if guarded state does not stop group processing early. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-260503-MJM-01 | D | `ClosePositionTickets` | mitigate | Pre-check symbol trade/session availability before `trade.PositionClose`, set scoped guard, and return early to avoid repeated broker calls during market close. |
| T-260503-MJM-02 | D | `ProcessPositionsByType` | mitigate | Check active scoped guard before profile resolution and `LogManagementDecision` HOLD/fallback/no_rule logging. |
| T-260503-MJM-03 | R | close failure logging | mitigate | Keep existing retcode/comment logging for race conditions where pre-check passes but broker rejects close; do not hide non-market-closed failures. |
</threat_model>

<verification>
Overall verification:
- GitNexus impact attempted for `ClosePositionTickets` and `ProcessPositionsByType`; exact limitation documented if MQL5 symbols not indexed.
- Node source assertions prove pre-check occurs before CLOSE log and `trade.PositionClose`.
- Node source assertions prove active guard returns from `ProcessPositionsByType` before `ResolveManagementProfile`/`LogManagementDecision`.
- `git diff --check -- mql5/AureusProvider_v2.mq5` passes except acceptable existing CRLF warning if any.
- MetaEditor compile attempted if CLI available; if not, summary records limitation and human compile required.
</verification>

<success_criteria>
- Market closed / close unavailable state stops close path before `trade.PositionClose` and before repeated CLOSE decision logs.
- Active guard for same symbol+magic+direction stops group management before repeated HOLD/profile_fallback/no_rule logs.
- Scope remains `mql5/AureusProvider_v2.mq5` only.
- Existing non-market-closed close failure diagnostics remain visible.
</success_criteria>

<output>
After completion, create `D:/Aureus/.planning/quick/260503-mjm-market-closed-guard-v-n-spam-log-hold-pr/260503-mjm-SUMMARY.md`.
</output>
