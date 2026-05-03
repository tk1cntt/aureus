---
phase: 260503-ltx-khi-th-tr-ng-ng-c-a-th-kh-ng-close-c-l-n
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - mql5/AureusProvider_v2.mq5
autonomous: true
requirements:
  - QUICK-260503-LTX
must_haves:
  truths:
    - "Khi MT5 trả về TRADE_RETCODE_MARKET_CLOSED cho close position, provider không lặp lại quản lý close cùng symbol+magic+direction trong lúc market vẫn đóng."
    - "Log `Closing stale profitable single position.` hoặc action CLOSE tương đương không spam liên tục sau lỗi `CTrade::OrderSend ... [market closed]`."
    - "Các close failure khác vẫn được log rõ ràng và không bị nuốt lỗi."
    - "Khi market mở lại hoặc guard hết hạn, logic quản lý position tiếp tục hoạt động bình thường."
  artifacts:
    - path: "mql5/AureusProvider_v2.mq5"
      provides: "Market-closed close retry guard trong helper đóng lệnh hiện có"
      contains: "TRADE_RETCODE_MARKET_CLOSED"
  key_links:
    - from: "ClosePositionTickets"
      to: "trade.PositionClose"
      via: "retcode/comment inspection after failed close"
      pattern: "trade\.ResultRetcode\(\)"
    - from: "ProcessLegacyPositionsByType"
      to: "ClosePositionTickets"
      via: "legacy_stale_profitable_single path"
      pattern: "legacy_stale_profitable_single"
---

<objective>
Chặn vòng lặp close lệnh khi thị trường đóng cửa trong `mql5/AureusProvider_v2.mq5`.

Purpose: Khi provider quản lý position và close bị MT5 từ chối vì market closed, timer/management loop không tiếp tục spam close cùng nhóm lệnh.
Output: Một sửa đổi surgical trong close helper hiện có, có log guard rõ, không refactor profile logic khác.
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

GitNexus impact note: `npx gitnexus impact --repo Aureus --direction upstream ClosePositionTickets` returned `Target 'ClosePositionTickets' not found`. Limitation: GitNexus index does not expose this MQL5 helper symbol. Executor must report this exact limitation before editing and rely on source-level call search/read for MQL5.

Known source anchors:
- `RetcodeToReason(10018)` already returns `MARKET_CLOSED`.
- `ClosePositionTickets(...)` currently logs CLOSE then loops `trade.PositionClose(tickets[i]);` without checking return value/retcode.
- Callers include management profile paths at `ProcessLegacyPositionsByType`, `ProcessConservativePositionsByType`, `ProcessTrendRunnerPositionsByType`, `ProcessBreakoutProtectPositionsByType`, `ProcessBasketEscapePositionsByType`.
- User symptom: `Closing stale profitable single position.` repeats, followed by `CTrade::OrderSend ... [market closed]`.
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add market-closed close guard in existing close helper</name>
  <files>mql5/AureusProvider_v2.mq5</files>
  <behavior>
    - When `trade.PositionClose(ticket)` returns false and `trade.ResultRetcode()` equals `TRADE_RETCODE_MARKET_CLOSED` or retcode `10018`, set a guard for `symbol+magic+pos_type_str` so later management loops skip close attempts for that group while guard active.
    - Guard key must include symbol, magic, direction/profile scope enough to avoid blocking unrelated symbol/magic/direction groups.
    - Guard must expire automatically, preferably based on `TimeCurrent()` plus a short bounded TTL such as 5 minutes, so provider recovers without manual restart after market reopens.
    - Non-market-closed close failures must still log ticket, retcode, reason via `RetcodeToReason`, and `trade.ResultComment()`.
  </behavior>
  <action>Before editing, run GitNexus impact for `ClosePositionTickets`; if not found, report exact CLI output limitation from context. Inspect `ClosePositionTickets` and callers. Add minimal state/helper code in `mql5/AureusProvider_v2.mq5` only: a small struct/array or equivalent to track market-closed close guard by `symbol`, `magic`, `direction`, `until`. At start of `ClosePositionTickets`, if guard active for current group, log one concise skip message and return false before `LogManagementDecision(... action="CLOSE" ...)` so stale-close action does not spam. During close loop, check `bool ok = trade.PositionClose(tickets[i])`; on false inspect `trade.ResultRetcode()` and `trade.ResultComment()`. If market closed, set/update guard and stop processing remaining tickets for that group. Keep existing success path behavior otherwise. Do not modify profile thresholds, DCA logic, socket logic, or unrelated management code.</action>
  <verify>
    <automated>cd /mnt/d/Aureus && python3 - <<'PY'
from pathlib import Path
p=Path('mql5/AureusProvider_v2.mq5')
s=p.read_text(encoding='utf-8')
assert 'TRADE_RETCODE_MARKET_CLOSED' in s or '10018' in s
assert 'trade.ResultRetcode()' in s
assert 'trade.ResultComment()' in s
assert 'market_closed' in s.lower() or 'MARKET_CLOSED' in s
idx=s.index('bool ClosePositionTickets')
body=s[idx:s.index('bool MovePositionsSL', idx)]
assert 'PositionClose' in body and 'ResultRetcode' in body
assert body.find('LogManagementDecision') > body.find('market') or 'Is' in body
PY</automated>
  </verify>
  <done>`ClosePositionTickets` skips repeated close attempts for active market-closed guard, sets guard when close retcode is market closed, logs other close failures with retcode/comment, and leaves other management logic untouched.</done>
</task>

<task type="auto">
  <name>Task 2: Verify MQL5 source and compile path</name>
  <files>mql5/AureusProvider_v2.mq5</files>
  <action>Run source-level checks proving guard exists inside close path and no unrelated files changed. Try to compile `mql5/AureusProvider_v2.mq5` if MetaEditor/MetaTrader compiler is available in environment. If no MQL5 compiler exists on CLI, state exact limitation in summary and include source-level verification output instead. Do not introduce test files unless existing repo already has MQL5 compile/test harness.</action>
  <verify>
    <automated>git diff -- mql5/AureusProvider_v2.mq5 && git diff --name-only</automated>
    <automated>npx gitnexus detect_changes --scope all</automated>
  </verify>
  <done>Diff only touches `mql5/AureusProvider_v2.mq5`; source checks pass; compile succeeds if compiler available, otherwise summary states compiler unavailable and source-level verification completed.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| MT5 trade server → provider close result | External broker/server retcode controls provider retry behavior. |
| Provider timer loop → trade server | Automated management loop can repeatedly send close requests. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-260503-LTX-01 | D | `ClosePositionTickets` | mitigate | Add bounded market-closed guard to prevent repeated `PositionClose` requests for same symbol+magic+direction while market is closed. |
| T-260503-LTX-02 | R | close failure logging | mitigate | Log retcode reason and `trade.ResultComment()` for failed closes so skipped retries remain auditable. |
| T-260503-LTX-03 | E | close guard scope | mitigate | Scope guard by symbol+magic+direction, not global, so unrelated management groups keep normal permission to close. |
</threat_model>

<verification>
- Source contains market-closed detection using MT5 retcode `TRADE_RETCODE_MARKET_CLOSED`/`10018`.
- `ClosePositionTickets` checks active guard before CLOSE decision logging.
- Failed close path logs retcode/reason/comment.
- `git diff --name-only` lists only `mql5/AureusProvider_v2.mq5`.
- MQL5 compile attempted if compiler exists; limitation documented if unavailable.
</verification>

<success_criteria>
- Repeated `Closing stale profitable single position.` / CLOSE action does not loop continuously after MT5 market-closed close response.
- Market-closed condition stops close processing for affected group for bounded TTL.
- Other symbols/magic/directions and non-market-closed failures remain observable and unaffected.
- No database changes.
</success_criteria>

<output>
After completion, create `D:/Aureus/.planning/quick/260503-ltx-khi-th-tr-ng-ng-c-a-th-kh-ng-close-c-l-n/260503-ltx-SUMMARY.md`.
</output>
