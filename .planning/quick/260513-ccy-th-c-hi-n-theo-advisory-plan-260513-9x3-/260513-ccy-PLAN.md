---
phase: 260513-ccy-th-c-hi-n-theo-advisory-plan-260513-9x3-
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - mql5/AureusProvider_v2.mq5
autonomous: false
requirements:
  - Q-260513-CCY
user_setup:
  - service: MetaTrader 5 / MetaEditor
    why: "MQL5 compile/runtime pending fill smoke cần terminal/MetaEditor nếu shell không có compiler"
    env_vars: []
    dashboard_config:
      - task: "Compile mql5/AureusProvider_v2.mq5 trong MetaEditor nếu command-line MetaEditor không khả dụng"
        location: "Local MT5 MetaEditor"
      - task: "Run pending LIMIT/STOP fill smoke against connected gateway"
        location: "Local MT5 terminal"
must_haves:
  truths:
    - "Market order path behavior giữ nguyên: ExecuteOpenOrder MARKET vẫn emit ORDER_OPENED, không thêm ORDER_FILLED cho market open."
    - "Pending placement path có log cmd_id, orderType, request.action, request.type, result.retcode, result.order, result.price, và order-exists check sau success."
    - "Pending fill path trong OnTradeTransaction log được từng gate chính trước PushOrderFilled: transaction type, HistoryDealSelect fail, DEAL_ENTRY, DEAL_MAGIC, DEAL_ORDER, DEAL_TYPE, socket connected, HistoryOrderSelect, ORDER_TYPE, isPendingFill, mapping result."
    - "Mapping miss không tự chặn ORDER_FILLED nếu pending fill đã được chứng minh bằng order history/type."
    - "PushOrderFilled log được kết quả g_socket.SendJSON nếu SendJSON trả bool/status, hoặc log rõ SendJSON status unsupported nếu API không expose status."
  artifacts:
    - path: "mql5/AureusProvider_v2.mq5"
      provides: "Minimal observability patch cho pending placement/fill gates"
      contains: "ExecuteOpenOrder"
    - path: "mql5/AureusProvider_v2.mq5"
      provides: "ORDER_FILLED send result visibility"
      contains: "PushOrderFilled"
  key_links:
    - from: "ExecuteOpenOrder pending branch"
      to: "OrderSelect + StorePendingOrderMapping + PushOrderOpened"
      via: "result.order from OrderSend success"
      pattern: "OrderSelect\\(\\(ulong\\)result\\.order[\\s\\S]{0,800}StorePendingOrderMapping\\(\\(long\\)result\\.order"
    - from: "OnTradeTransaction DEAL_ENTRY_IN"
      to: "PushOrderFilled"
      via: "HistoryOrderSelect(DEAL_ORDER) pending ORDER_TYPE gate"
      pattern: "HistoryOrderSelect.*ORDER_TYPE.*isPendingFill"
    - from: "PushOrderFilled"
      to: "gateway socket"
      via: "g_socket.SendJSON(json) result or unsupported-status logging"
      pattern: "SendJSON\\(json\\).*PENDING_FILL_SEND|PENDING_FILL_SEND.*SendJSON\\(json\\)|SendJSON status unsupported"
---

<objective>
Tạo patch observability tối thiểu cho `mql5/AureusProvider_v2.mq5` theo advisory `260513-9x3`: thấy rõ pending placement và pending fill bị dừng ở gate nào, không thêm fallback rộng, không đổi DB/journal/gateway, không làm market-order path đổi semantic.

Purpose: chứng minh pending ORDER_FILLED mất ở provider gate hay gateway/journal trước khi sửa behavior rộng.
Output: một source patch MQL5 nhỏ + verification strategy compile/static/runtime smoke.
</objective>

<execution_context>
@D:/Aureus/.claude/get-shit-done/workflows/execute-plan.md
@D:/Aureus/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@D:/Aureus/CLAUDE.md
@D:/Aureus/.planning/STATE.md
@D:/Aureus/.planning/quick/260513-9x3-t-review-l-i-plan-pending-order-fill-v-i/260513-9x3-ARCHITECTURE-ADVISORY.md
@D:/Aureus/mql5/AureusProvider_v2.mq5

Relevant source anchors from current file:
- `PushOrderFilled` at `mql5/AureusProvider_v2.mq5:1543` builds ORDER_FILLED JSON, calls `g_socket.SendJSON(json)`, then logs pushed without checking return.
- `ExecuteOpenOrder` at `mql5/AureusProvider_v2.mq5:2826` handles MARKET and pending. MARKET branch emits ORDER_OPENED. Pending branch currently runs only when `result.retcode == TRADE_RETCODE_DONE`, stores mapping at line 3284, emits ORDER_OPENED at line 3285.
- `OnTradeTransaction` at `mql5/AureusProvider_v2.mq5:3723` returns silently on non-DEAL_ADD, HistoryDealSelect fail, entry not IN/OUT, magic 0, socket disconnected, non-pending `ORDER_TYPE`; calls PushOrderFilled at line 3809.

GitNexus requirement:
- Before editing `ExecuteOpenOrder`, run `gitnexus_impact({target: "ExecuteOpenOrder", direction: "upstream"})` and report direct callers, affected processes, risk.
- Before editing `OnTradeTransaction`, run `gitnexus_impact({target: "OnTradeTransaction", direction: "upstream"})` and report direct callers, affected processes, risk.
- Before editing `PushOrderFilled`, run `gitnexus_impact({target: "PushOrderFilled", direction: "upstream"})` and report direct callers, affected processes, risk.
- If GitNexus cannot find/index MQL5 symbols, document exact limitation in summary and use direct source evidence above.
- Before commit, run `gitnexus_detect_changes()` per project rule if available.
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add pending placement diagnostics without changing market path</name>
  <files>D:/Aureus/mql5/AureusProvider_v2.mq5</files>
  <action>Run GitNexus impact for `ExecuteOpenOrder` first. In `ExecuteOpenOrder`, add debug-only logs around pending order placement only (`orderType != "MARKET"`). Use stable diagnostic prefixes exactly: `[PENDING_PLACEMENT_TRACE]` for request/result/order-exists context and `[PENDING_PLACEMENT_GATE]` for success/failure gate decisions. Log `cmd_id`, `symbol`, `direction`, `orderType`, `request.action`, `request.type`, `request.price`, `request.sl`, `request.tp`, `result.retcode`, `result.order`, `result.price`. After pending `OrderSend` success and before/around `StorePendingOrderMapping((long)result.order`, check whether `result.order > 0` and `OrderSelect((ulong)result.order)` succeeds; log order-exists result and selected `ORDER_TYPE` if available. Ensure `OrderSelect((ulong)result.order)` appears within 800 characters before `StorePendingOrderMapping((long)result.order` so static verification proves mapping stores only after explicit selected-order visibility. Do not add broad accepted retcodes, do not change `result.retcode == TRADE_RETCODE_DONE` behavior, do not touch MARKET branch except unavoidable shared local logging variables.</action>
  <verify>
    <automated>python - <<'PY'
from pathlib import Path
import re
p = Path('D:/Aureus/mql5/AureusProvider_v2.mq5')
s = p.read_text(encoding='utf-8', errors='ignore')
assert '[PENDING_PLACEMENT_TRACE]' in s
assert '[PENDING_PLACEMENT_GATE]' in s
for token in ['request.action', 'request.type', 'result.retcode', 'result.order', 'result.price']:
    assert token in s, token
assert 'orderType == "MARKET"' in s
m = re.search(r'OrderSelect\(\(ulong\)result\.order\)[\s\S]{0,800}StorePendingOrderMapping\(\(long\)result\.order', s)
assert m, 'OrderSelect((ulong)result.order) must appear near StorePendingOrderMapping((long)result.order)'
print('static placement diagnostics ok')
PY</automated>
  </verify>
  <done>Pending placement emits `[PENDING_PLACEMENT_TRACE]` and `[PENDING_PLACEMENT_GATE]` evidence for request/result/order existence; MARKET branch still emits ORDER_OPENED only through existing flow and no new pending fallback behavior exists.</done>
</task>

<task type="auto">
  <name>Task 2: Add OnTradeTransaction pending-fill gate diagnostics</name>
  <files>D:/Aureus/mql5/AureusProvider_v2.mq5</files>
  <action>Run GitNexus impact for `OnTradeTransaction` first. Add debug logs at every current early-return gate relevant to pending fill: non-`TRADE_TRANSACTION_DEAL_ADD`, `HistoryDealSelect(trans.deal)` fail, `DEAL_ENTRY` not IN/OUT, `DEAL_MAGIC == 0`, `DEAL_ORDER`, `!g_socket.IsConnected()`, `HistoryOrderSelect(orderTicket)` result, `ORDER_TYPE`, `isPendingFill == false`, and `PopPendingOrderMapping` result. Use stable diagnostic prefixes exactly: `[PENDING_FILL_TRACE]` for observed values and `[PENDING_FILL_GATE]` for pass/fail gate decisions. Preserve behavior: same returns remain returns; no retry, queue, replay, DB call, or broad fallback. Ensure mapping miss is logged but not made a blocker beyond existing logic, because current code already calls PushOrderFilled after pending proof even when `hasPendingMapping=false`.</action>
  <verify>
    <automated>python - <<'PY'
from pathlib import Path
s = Path('D:/Aureus/mql5/AureusProvider_v2.mq5').read_text(encoding='utf-8', errors='ignore')
assert '[PENDING_FILL_TRACE]' in s
assert '[PENDING_FILL_GATE]' in s
for token in ['HistoryDealSelect(trans.deal)', 'DEAL_ENTRY', 'DEAL_MAGIC', 'DEAL_ORDER', 'HistoryOrderSelect', 'isPendingFill', 'PopPendingOrderMapping', 'g_socket.IsConnected()']:
    assert token in s, token
assert 'PushOrderFilled(symbol' in s
print('static fill gate diagnostics ok')
PY</automated>
  </verify>
  <done>Pending fill path logs `[PENDING_FILL_TRACE]` and `[PENDING_FILL_GATE]` evidence before each relevant silent return while preserving current decision tree and no fallback send for unproven fills.</done>
</task>

<task type="auto">
  <name>Task 3: Add PushOrderFilled send-result visibility</name>
  <files>D:/Aureus/mql5/AureusProvider_v2.mq5</files>
  <action>Run GitNexus impact for `PushOrderFilled` first. Inspect `g_socket.SendJSON(json)` signature/usage in `mql5/AureusProvider_v2.mq5`. If `SendJSON` returns bool/status, store result in a local variable in `PushOrderFilled` and log send success/failure with stable prefix `[PENDING_FILL_SEND]`, including pending_order_id, position_ticket, deal_ticket, symbol. If `SendJSON` API does not expose status, keep existing call and add explicit `[PENDING_FILL_SEND] SendJSON status unsupported` log with same identifiers after the call. Do not change DB/journal SQL. Do not add ORDER_FILLED for market order opens.</action>
  <verify>
    <automated>python - <<'PY'
from pathlib import Path
import re
s = Path('D:/Aureus/mql5/AureusProvider_v2.mq5').read_text(encoding='utf-8', errors='ignore')
assert 'void PushOrderFilled' in s
assert '"type":"ORDER_FILLED"' in s
assert 'g_socket.SendJSON(json)' in s
assert '[PENDING_FILL_SEND]' in s, 'missing send-result/status diagnostic prefix'
assert re.search(r'\[PENDING_FILL_SEND\][\s\S]{0,500}(send|SendJSON|status|success|fail|unsupported)', s), 'missing explicit send result/status/unsupported log'
assert '[PENDING_FILL_TRACE]' in s
assert '[PENDING_FILL_GATE]' in s
assert '[PENDING_PLACEMENT_TRACE]' in s
assert '[PENDING_PLACEMENT_GATE]' in s
print('static provider send visibility ok')
PY</automated>
  </verify>
  <done>`PushOrderFilled` has explicit `[PENDING_FILL_SEND]` status visibility: send result when API supports it, or explicit unsupported-status limitation when API does not.</done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Task 4: Verify compile strategy and pending fill smoke</name>
  <files>D:/Aureus/mql5/AureusProvider_v2.mq5</files>
  <action>Verify source edits from Tasks 1-3 after automation completes: pending placement diagnostics, pending fill gate diagnostics, and PushOrderFilled send-result/status visibility. This checkpoint must not require code edits; all source modifications belong to auto tasks before this gate.</action>
  <verify>
    <automated>bash -lc 'if command -v wine >/dev/null 2>&1; then echo "MetaEditor compile may need local path discovery"; else echo "MetaEditor unavailable in shell; human compile required"; fi'</automated>
  </verify>
  <done>Executor has run all static Python checks from Tasks 1-3 and tried command-line MetaEditor compile if installed/discoverable. If MetaEditor CLI unavailable, human compiles `D:/Aureus/mql5/AureusProvider_v2.mq5` in MetaEditor, runs one market order regression confirming no new ORDER_FILLED from MARKET open path, then runs one pending LIMIT/STOP fill smoke confirming MT5 log includes `[PENDING_PLACEMENT_TRACE]`, `[PENDING_PLACEMENT_GATE]`, `[PENDING_FILL_TRACE]`, `[PENDING_FILL_GATE]`, and `[PENDING_FILL_SEND]` before gateway outcome analysis. Resume with `approved` plus compile/smoke result, or paste compile/runtime issues.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Gateway -> MT5 provider | Untrusted JSON command crosses socket into `ExecuteOpenOrder`. |
| MT5 provider -> Gateway | Lifecycle event JSON crosses socket through `PushOrderFilled`. |
| Broker/MT5 history -> provider | Trade transaction/history data drives pending fill classification. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-260513-CCY-01 | T | `ExecuteOpenOrder` diagnostics | mitigate | Log only request/result fields already used for trade lifecycle; do not alter order request or retcode handling. |
| T-260513-CCY-02 | R | `OnTradeTransaction` early returns | mitigate | Add stable gate logs for each return so pending fill drop has audit trail. |
| T-260513-CCY-03 | I | MT5 debug logs | accept | Logs include order ids, magic, trace/cmd context already internal operational data; no new secrets or credentials logged. |
| T-260513-CCY-04 | D | Extra logging volume | mitigate | Gate logs only for trade transactions and debug mode where existing code uses `InpDebugMode`; keep messages compact. |
| T-260513-CCY-05 | E | Broad fill fallback | mitigate | Plan explicitly forbids broad fallback, DB mutation, or emitting ORDER_FILLED for unproven market/DCA entries. |
</threat_model>

<verification>
1. Static Python checks above pass.
2. If GitNexus finds MQL5 symbols, impact results for `ExecuteOpenOrder`, `OnTradeTransaction`, `PushOrderFilled` are recorded in summary.
3. If GitNexus cannot find MQL5 symbols, summary records limitation and direct source anchors used.
4. If MetaEditor CLI is unavailable in shell, human compile/runtime smoke remains blocking checkpoint; no claim compiled.
5. Runtime smoke must cover one market order regression and one pending LIMIT/STOP fill event.
</verification>

<success_criteria>
- `mql5/AureusProvider_v2.mq5` has minimal observability only.
- Market path behavior unchanged: no new ORDER_FILLED from MARKET open path.
- Pending placement logs request/result/order existence evidence using `[PENDING_PLACEMENT_TRACE]` and `[PENDING_PLACEMENT_GATE]`.
- Pending placement static verify proves `OrderSelect((ulong)result.order)` appears near `StorePendingOrderMapping((long)result.order`.
- Pending fill logs exact gate evidence before PushOrderFilled or before return using `[PENDING_FILL_TRACE]` and `[PENDING_FILL_GATE]`.
- PushOrderFilled send result visibility added if API supports bool/status, or explicit `[PENDING_FILL_SEND] SendJSON status unsupported` limitation logged if not.
- No DB, gateway schema, journal SQL, or backend behavior touched.
</success_criteria>

<output>
After completion, create `D:/Aureus/.planning/quick/260513-ccy-th-c-hi-n-theo-advisory-plan-260513-9x3-/260513-ccy-SUMMARY.md`
</output>
