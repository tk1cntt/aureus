---
phase: 260501-eka-implement-history-based-cooldown-in-aure
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - mql5/AureusProvider_v2.mq5
autonomous: true
requirements:
  - QUICK-260501-EKA
must_haves:
  truths:
    - "AureusProvider_v2 bootstrap cooldown state from MT5 deal history during OnInit for configured InpSymbols, scoped by symbol + magic + direction."
    - "A single SL close sets a 30-minute cooldown only for that exact symbol + magic + direction scope."
    - "Multiple closes in the same symbol + magic + direction scope within 2 seconds set a 60-minute cooldown only for that scope."
    - "OPEN_ORDER for an unsupported symbol remains provider-local ignored without terminal NACK."
    - "OPEN_ORDER for a supported symbol whose symbol + magic + direction scope is cooling down receives NACK reason HISTORY_COOLDOWN_ACTIVE before ACK/order side effects."
    - "CLOSE_ORDER, REQUEST_* commands, and backfill commands are not blocked by cooldown logic."
    - "Bootstrap, realtime cooldown set, and cooldown rejection produce clear logs."
  artifacts:
    - path: "mql5/AureusProvider_v2.mq5"
      provides: "Provider-local history cooldown structs/state helpers, OnInit bootstrap, OnTradeTransaction update, and ExecuteOpenOrder enforcement"
      contains: "HISTORY_COOLDOWN_ACTIVE"
  key_links:
    - from: "OnInit"
      to: "history cooldown state array"
      via: "bootstrap helper scans HistorySelect/HistoryDealsTotal after InpSymbols are parsed"
      pattern: "Bootstrap.*History.*Cooldown|HistoryCooldown.*Bootstrap"
    - from: "OnTradeTransaction"
      to: "history cooldown state array"
      via: "DEAL_ENTRY_OUT close deal updates cooldown by symbol + magic + original direction"
      pattern: "Set.*Cooldown|Update.*Cooldown"
    - from: "ExecuteOpenOrder"
      to: "SendNACK"
      via: "supported-symbol cooldown check before ACK and RecordCmdId"
      pattern: "HISTORY_COOLDOWN_ACTIVE"
---

<objective>
Implement history-based cooldown trong `mql5/AureusProvider_v2.mq5`, tương tự ý tưởng `ManagePositionByHistory` từ `mql5/CISD_Slope_EA_v6.39_Final.mq5` nhưng viết lại provider-safe, không copy nguyên xi.

Purpose: Ngăn Aureus mở lại lệnh quá sớm sau SL/DCA-close burst, nhưng chỉ khóa đúng scope `symbol + magic + direction` để không ảnh hưởng strategy/symbol/side khác.
Output: Một thay đổi surgical trong `AureusProvider_v2.mq5` gồm state array cooldown, bootstrap history ở `OnInit`, realtime update ở `OnTradeTransaction`, và enforce trong `ExecuteOpenOrder`.
</objective>

<execution_context>
@D:/Aureus/.claude/get-shit-done/workflows/execute-plan.md
@D:/Aureus/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@D:/Aureus/CLAUDE.md
@D:/Aureus/.planning/STATE.md
@D:/Aureus/mql5/AureusProvider_v2.mq5
@D:/Aureus/mql5/CISD_Slope_EA_v6.39_Final.mq5

<locked_decisions>
- Implement chức năng tương tự `ManagePositionByHistory` từ `mql5/CISD_Slope_EA_v6.39_Final.mq5` vào `mql5/AureusProvider_v2.mq5` nhưng KHÔNG copy nguyên xi.
- Scope phải là `symbol + magic + direction`, không khóa toàn symbol/không dùng `_Symbol`.
- V1 có: state array cooldown, bootstrap từ history ở `OnInit`, realtime update từ `OnTradeTransaction`, enforce trong `ExecuteOpenOrder`.
- Rules V1: single SL => cooldown 30 phút cho scope; multiple close same scope trong 2 giây => cooldown 60 phút cho scope. Chưa implement slow TP nếu không cần.
- Unsupported symbol vẫn provider-local ignore, không terminal NACK.
- Supported symbol đúng provider nhưng đang cooldown thì `OPEN_ORDER` bị NACK reason `HISTORY_COOLDOWN_ACTIVE`.
- Không block `CLOSE_ORDER`/`REQUEST_*`/backfill.
- Cần log rõ khi bootstrap/set cooldown/reject.
</locked_decisions>

<interfaces>
Existing relevant `AureusProvider_v2.mq5` symbols and flow:
```mql5
int OnInit();
int FindContextIndex(string symbol);
void SendNACK(string cmdId, string reason);
void ExecuteOpenOrder(const string &raw);
void ExecuteCloseOrder(const string &raw);
void ExecuteTradeHistoryRequest(const string &raw);
void ProcessSingleCommand(const string &raw);
void OnTradeTransaction(const MqlTradeTransaction& trans,
                        const MqlTradeRequest& request,
                        const MqlTradeResult& result);
```

Current `ExecuteOpenOrder` order of side effects to preserve:
1. Parse command fields.
2. Validate required fields.
3. Reject duplicate command.
4. Unsupported symbol: log and return without `SendNACK`.
5. Reject duplicate active strategy order.
6. Check terminal trade allowed.
7. `SendACK(cmdId)` and `RecordCmdId(cmdId)`.
8. Build/check/send MT5 trade request.

Cooldown enforcement must be inserted after unsupported-symbol provider-local ignore and before duplicate active strategy/ACK/order side effects, so supported cooldown scopes get `SendNACK(cmdId, "HISTORY_COOLDOWN_ACTIVE")` and no command is ACKed/executed.

Source inspiration from `CISD_Slope_EA_v6.39_Final.mq5`:
```mql5
void ManagePositionByHistory()
  {
   TradeHistoryInfo latest_trades[];
   int latest_trade_found_count = GetLatestCompletedTrades(_Symbol, latest_trades);
   if(latest_trade_found_count > 0 && !PositionSelect(_Symbol))
     {
      if(latest_trade_found_count == 1 && latest_trades[0].close_reason == DEAL_REASON_SL)
        {
         g_last_m30_processed_bar_time = latest_trades[0].close_time + 30 * 60;
         g_last_h1_processed_bar_time = latest_trades[0].close_time + 30 * 60;
        }
      if((latest_trade_found_count == 1 && latest_trades[0].close_reason == DEAL_REASON_TP && latest_trades[0].close_time - latest_trades[0].open_time >= 30 * 60) || latest_trade_found_count > 1)
        {
         g_last_h1_processed_bar_time = latest_trades[0].close_time + 60 * 60;
        }
     }
  }
```
Use this only as behavior inspiration. Do not copy the whole implementation or `_Symbol` assumptions.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="false">
  <name>Task 1: Add provider-local history cooldown state and bootstrap helpers</name>
  <files>D:/Aureus/mql5/AureusProvider_v2.mq5</files>
  <action>
Before editing, satisfy the GitNexus project rule: run `gitnexus_impact` for each existing symbol you will modify (`OnInit`, `ExecuteOpenOrder`, `OnTradeTransaction`; include helper symbols if indexed). If GitNexus does not index MQL5 symbols or the tool is unavailable for these symbols, document the fallback in the summary and keep the change surgical.

Add a minimal provider-local cooldown data model near existing structs/globals: a struct keyed by `symbol`, `magic`, and `direction` with `cooldown_until`, last close metadata needed for the 2-second multi-close rule, and a processed close deal id list/count to avoid double-processing bootstrap/realtime history. Add small helper functions with clear names, for example `FindHistoryCooldownIndex`, `EnsureHistoryCooldownState`, `DirectionFromCloseDealType`, `SetHistoryCooldown`, `ApplyCloseDealToHistoryCooldown`, and `BootstrapHistoryCooldowns`.

Implementation details:
- Scope identity is exactly `symbol + magic + direction`; direction is original position direction, so close deal `DEAL_TYPE_BUY` means original `SELL`, close deal `DEAL_TYPE_SELL` means original `BUY`, matching existing `OnTradeTransaction` logic.
- Bootstrap must run from `OnInit` after `InpSymbols` parsing/state initialization. It must scan recent relevant history with `HistorySelect`, ignore manual magic `0`, ignore symbols not in `InpSymbols`, and apply the same rules as realtime.
- Bootstrap should only set active cooldowns whose `cooldown_until > TimeCurrent()`.
- Single SL (`DEAL_REASON_SL`) sets 30 minutes from close time.
- Multiple closes in same scope within 2 seconds sets 60 minutes from the latest close time, regardless of SL/TP reason.
- Do not implement slow TP cooldown unless needed for the above rules.
- Logs must be explicit and include scope and reason, e.g. bootstrap start/end and `Set cooldown symbol=... magic=... direction=... until=... reason=single_sl|multi_close_2s source=bootstrap|realtime`.
- Do not use `_Symbol` for cooldown scope.
  </action>
  <verify>
    <automated>cd D:/Aureus && python - <<'PY'
from pathlib import Path
p=Path('mql5/AureusProvider_v2.mq5')
s=p.read_text(encoding='utf-8', errors='ignore')
required=['HISTORY_COOLDOWN_ACTIVE','BootstrapHistoryCooldown','ApplyCloseDealToHistoryCooldown','SetHistoryCooldown','DEAL_REASON_SL','30 * 60','60 * 60']
missing=[x for x in required if x not in s]
assert not missing, missing
assert 'FindContextIndex(symbol)' in s
PY</automated>
  </verify>
  <done>`AureusProvider_v2.mq5` has a minimal cooldown state array and bootstrap helper path that can set 30/60-minute cooldowns per `symbol + magic + direction`, without `_Symbol`-scoped locking or copied CISD code.</done>
</task>

<task type="auto" tdd="false">
  <name>Task 2: Wire realtime cooldown updates and OPEN_ORDER enforcement</name>
  <files>D:/Aureus/mql5/AureusProvider_v2.mq5</files>
  <action>
Modify only the necessary existing functions.

In `OnInit`, call the bootstrap helper after configured symbols and cooldown arrays are initialized. In `OnTradeTransaction`, after the close deal is selected and after magic/symbol/direction are known, apply realtime cooldown update for provider-supported symbols before/around `PushOrderClosed`; keep existing ORDER_CLOSED behavior intact.

In `ExecuteOpenOrder`, insert cooldown enforcement only for supported symbols after the existing unsupported-symbol provider-local ignore block and before duplicate active strategy order checks, terminal trade checks, `SendACK`, and `RecordCmdId`. If the exact `symbol + magic + direction` scope has `cooldown_until > TimeCurrent()`, log a clear reject line and call `SendNACK(cmdId, "HISTORY_COOLDOWN_ACTIVE")`, then return. Do not record the command id for this NACK unless the existing NACK pattern for pre-ACK rejects does so; match current style.

Preserve these behaviors exactly:
- Unsupported symbol continues to log and return without terminal NACK.
- `CLOSE_ORDER`, `REQUEST_POSITIONS`, `REQUEST_ORDERS`, `REQUEST_TRADE_HISTORY`, `REQUEST_BACKFILL`, and `REQUEST_BACKFILL_COUNT` do not call cooldown checks.
- Duplicate active order rejection remains scoped by symbol + magic + side and still returns `STRATEGY_ORDER_EXISTS` when cooldown is not active.
- Existing terminal event gate and `ORDER_OPENED`/`ORDER_FAILED` behavior remain unchanged.
  </action>
  <verify>
    <automated>cd D:/Aureus && python - <<'PY'
from pathlib import Path
s=Path('mql5/AureusProvider_v2.mq5').read_text(encoding='utf-8', errors='ignore')
open_fn=s[s.index('void ExecuteOpenOrder'):s.index('//+------------------------------------------------------------------+\n//| Execute CLOSE_ORDER command')]
unsupported=open_fn.index('SYMBOL_NOT_ALLOWED')
cooldown=open_fn.index('HISTORY_COOLDOWN_ACTIVE')
ack=open_fn.index('SendACK(cmdId)')
assert unsupported < cooldown < ack, (unsupported, cooldown, ack)
assert 'ExecuteCloseOrder' in s and 'HISTORY_COOLDOWN_ACTIVE' not in s[s.index('void ExecuteCloseOrder'):s.index('//+------------------------------------------------------------------+\n//| Execute REQUEST_ORDERS command')]
assert 'OnTradeTransaction' in s and 'ApplyCloseDealToHistoryCooldown' in s[s.index('void OnTradeTransaction'):s.index('//+------------------------------------------------------------------+\n//| Timer event')]
PY</automated>
  </verify>
  <done>Realtime close deals update cooldown state; only supported-symbol `OPEN_ORDER` for an active scoped cooldown is rejected with `HISTORY_COOLDOWN_ACTIVE`; all non-open command flows remain unaffected.</done>
</task>

<task type="auto" tdd="false">
  <name>Task 3: Compile/verify surgically and record GitNexus fallback/scope</name>
  <files>D:/Aureus/mql5/AureusProvider_v2.mq5</files>
  <action>
Run the strongest available local verification without changing unrelated files. Prefer an MQL5 compile if this environment has MetaEditor/compiler available; otherwise perform static checks only and document compile limitation in the summary.

Required checks:
- Search/read the modified sections and confirm no `_Symbol` is used in cooldown helper/enforcement scope.
- Confirm logs exist for bootstrap, cooldown set, and cooldown reject.
- Confirm unsupported symbol branch still returns without `SendNACK`.
- Run `gitnexus_detect_changes()` before any commit if committing is requested; if GitNexus cannot analyze MQL5 changes, document fallback and use `git diff -- mql5/AureusProvider_v2.mq5` to confirm only expected file/symbol areas changed.
- Do not commit unless explicitly asked by the user.
  </action>
  <verify>
    <automated>cd D:/Aureus && git diff -- mql5/AureusProvider_v2.mq5</automated>
    <automated>cd D:/Aureus && python - <<'PY'
from pathlib import Path
s=Path('mql5/AureusProvider_v2.mq5').read_text(encoding='utf-8', errors='ignore')
for token in ['Bootstrap','Set cooldown','Reject OPEN_ORDER','HISTORY_COOLDOWN_ACTIVE']:
    assert token in s, token
# Check unsupported symbol block still does not SendNACK before return.
fn=s[s.index('void ExecuteOpenOrder'):]
block=fn[fn.index('SYMBOL_NOT_ALLOWED')-300:fn.index('SYMBOL_NOT_ALLOWED')+500]
assert 'SendNACK' not in block or '// SendNACK' in block, block
PY</automated>
  </verify>
  <done>Diff is limited to `mql5/AureusProvider_v2.mq5`, cooldown behavior is statically verified, and summary states GitNexus impact/detect_changes results or MQL5 indexing fallback.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Gateway -> MT5 provider `OPEN_ORDER` | Untrusted/remote order command requests can trigger trading side effects. |
| MT5 deal history -> provider cooldown state | Broker terminal history data drives local throttling decisions. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-260501-eka-01 | Tampering | `ExecuteOpenOrder` cooldown gate | mitigate | Evaluate cooldown after parsing command but before ACK/order side effects; key by parsed `symbol + magic + direction`, not mutable global `_Symbol`. |
| T-260501-eka-02 | Denial of Service | Cooldown state array | mitigate | Cooldown applies only to exact supported scope and expires by `cooldown_until`; unsupported symbols remain ignored without terminal NACK. |
| T-260501-eka-03 | Repudiation | Bootstrap/realtime decisions | mitigate | Log bootstrap/set/reject with symbol, magic, direction, until time, reason, and source. |
</threat_model>

<verification>
Overall verification:
- Static checks in each task pass.
- If available, compile `mql5/AureusProvider_v2.mq5` in MetaEditor/MT5 and resolve compile errors without touching unrelated files.
- Manual MT5 smoke expectation: after a supported scope has SL close, next `OPEN_ORDER` for same symbol/magic/direction before 30 minutes returns NACK `HISTORY_COOLDOWN_ACTIVE`; opposite direction or different magic/symbol is not blocked.
</verification>

<success_criteria>
- `AureusProvider_v2.mq5` implements history cooldown with full fidelity to locked decisions.
- No full-symbol lock and no `_Symbol` dependency for cooldown scope.
- No slow TP cooldown implemented.
- Unsupported symbols remain provider-local ignored.
- `CLOSE_ORDER`, `REQUEST_*`, and backfill are not blocked.
- Logs are clear enough to diagnose bootstrap, cooldown set, and reject.
</success_criteria>

<output>
After completion, create `D:/Aureus/.planning/quick/260501-eka-implement-history-based-cooldown-in-aure/260501-eka-SUMMARY.md`.
</output>
