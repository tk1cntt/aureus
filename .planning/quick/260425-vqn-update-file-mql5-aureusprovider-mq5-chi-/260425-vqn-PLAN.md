---
phase: quick-260425-vqn-update-file-mql5-aureusprovider-mq5-chi
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - mql5/AureusProvider.mq5
autonomous: true
requirements:
  - QUICK-260425-VQN
must_haves:
  truths:
    - "Gateway OPEN_ORDER cho symbol có trong InpSymbols tiếp tục được ACK và đi vào luồng OrderCheck/OrderSend hiện có."
    - "Gateway OPEN_ORDER cho symbol không có trong InpSymbols bị từ chối an toàn trước ACK/RecordCmdId/OrderCheck/OrderSend."
    - "Gateway CLOSE_ORDER cho symbol không có trong InpSymbols bị từ chối an toàn trước ACK/RecordCmdId/OrderSend."
    - "Log/NACK nêu rõ lý do reject để debug được symbol không được khai báo."
  artifacts:
    - path: "mql5/AureusProvider.mq5"
      provides: "InpSymbols allowlist gate cho order commands từ gateway"
      contains: "FindContextIndex(symbol)"
  key_links:
    - from: "ProcessIncomingCommands"
      to: "ExecuteOpenOrder"
      via: "OPEN_ORDER dispatch giữ nguyên, allowlist nằm trong executor trước ACK"
      pattern: "ExecuteOpenOrder\\(raw\\)"
    - from: "ExecuteOpenOrder"
      to: "InpSymbols/g_contexts"
      via: "FindContextIndex(symbol) reject trước SendACK/RecordCmdId"
      pattern: "FindContextIndex\\(symbol\\)"
    - from: "ExecuteCloseOrder"
      to: "InpSymbols/g_contexts"
      via: "FindContextIndex(symbol) reject trước SendACK/RecordCmdId"
      pattern: "FindContextIndex\\(symbol\\)"
---

<objective>
Cập nhật `mql5/AureusProvider.mq5` để provider chỉ nhận và xử lý order commands từ gateway khi `symbol` nằm trong danh sách `InpSymbols`.

Purpose: Chặn lệnh gateway gửi nhầm/sai symbol trước khi MT5 ACK và trước khi gọi `OrderCheck`/`OrderSend`, giảm rủi ro provider mở/đóng lệnh ngoài danh sách symbol được cấu hình.
Output: Một thay đổi surgical trong `mql5/AureusProvider.mq5` với allowlist gate, logging/reason rõ ràng, và kiểm chứng bằng diff/direct review vì không yêu cầu database E2E.
</objective>

<execution_context>
@D:/Aureus/.claude/get-shit-done/workflows/execute-plan.md
@D:/Aureus/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@D:/Aureus/.planning/STATE.md
@D:/Aureus/CLAUDE.md
@D:/Aureus/RUN_SERVICES.md
@D:/Aureus/mql5/AureusProvider.mq5

<interfaces>
Các điểm hiện có trong `mql5/AureusProvider.mq5` cần giữ nguyên style và chỉnh tối thiểu:

```mql5
input string InpSymbols = "XAUUSD,BTCUSD,ETHUSD,USTEC,USDJPY,EURUSD,GBPUSD,AUDUSD";
SymbolContext g_contexts[];
int g_symbolCount;

int FindContextIndex(string symbol)
{
   for(int i = 0; i < g_symbolCount; i++)
   {
      if(g_contexts[i].symbol == symbol)
         return i;
   }
   return -1;
}

void SendNACK(string cmdId, string reason);
void SendACK(string cmdId);
void RecordCmdId(string cmdId);
void ExecuteOpenOrder(const string &raw);
void ExecuteCloseOrder(const string &raw);
void ProcessIncomingCommands();
```

Hiện tại `ExecuteOpenOrder` đã có check `FindContextIndex(symbol) < 0` trả `UNKNOWN_SYMBOL` trước ACK. Cần rà soát và làm rõ behavior này theo yêu cầu, đồng thời bổ sung cùng allowlist gate cho `ExecuteCloseOrder` vì hiện tại close order chưa kiểm tra symbol thuộc `InpSymbols` trước ACK/OrderSend.
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Rà soát impact và xác định symbol allowlist edit points</name>
  <files>mql5/AureusProvider.mq5</files>
  <action>Trước khi sửa bất kỳ function nào, tuân thủ CLAUDE.md: chạy GitNexus impact-analysis cho các symbol dự kiến chỉnh, tối thiểu `ExecuteOpenOrder` và `ExecuteCloseOrder`; nếu cần chỉnh helper thì chạy thêm cho helper đó. Nếu GitNexus không index được MQL5 symbols hoặc trả không tìm thấy symbol, ghi rõ trong summary là "MQL5 symbols not indexed" và thay bằng direct code review trên file/diff. Báo blast radius: direct callers, affected processes nếu có, risk level. Không refactor luồng order, không đổi schema JSON, không đổi InpSymbols parsing.</action>
  <verify>
    <automated>npx gitnexus impact ExecuteOpenOrder --direction upstream || true</automated>
    <automated>npx gitnexus impact ExecuteCloseOrder --direction upstream || true</automated>
  </verify>
  <done>Impact hoặc lý do không index được MQL5 đã được ghi trong summary; edit points chỉ giới hạn trong order allowlist validation của `mql5/AureusProvider.mq5`.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Enforce InpSymbols allowlist trước khi xử lý OPEN_ORDER/CLOSE_ORDER</name>
  <files>mql5/AureusProvider.mq5</files>
  <behavior>
    - OPEN_ORDER với `symbol` thuộc `InpSymbols`: đi qua behavior hiện có, ACK sau validation và tiếp tục `OrderCheck`/`OrderSend`.
    - OPEN_ORDER với `symbol` không thuộc `InpSymbols`: gửi NACK reason rõ ràng như `SYMBOL_NOT_ALLOWED` hoặc giữ `UNKNOWN_SYMBOL` nếu muốn ít đổi downstream hơn; không gọi `SendACK`, không `RecordCmdId`, không `OrderCheck`, không `OrderSend`.
    - CLOSE_ORDER với `symbol` không thuộc `InpSymbols`: gửi NACK reason rõ ràng trước `TerminalInfoInteger`, `SendACK`, `RecordCmdId`, `PositionSelectByTicket`, và `OrderSend`.
    - Reject path có `PrintFormat` debug/log reason chứa `cmd_id` và `symbol` để tra log được nguyên nhân.
  </behavior>
  <action>Sửa tối thiểu `mql5/AureusProvider.mq5`. Dùng `FindContextIndex(symbol) < 0` làm source of truth cho `InpSymbols` allowlist vì `g_contexts` được parse từ `InpSymbols` trong `OnInit`. Giữ check required fields trước allowlist để tránh symbol rỗng bị log sai. Với `ExecuteOpenOrder`, nếu đã có `UNKNOWN_SYMBOL` gate thì chỉ bổ sung logging/reason nếu cần, không di chuyển ACK xuống sai vị trí. Với `ExecuteCloseOrder`, thêm allowlist gate ngay sau duplicate check hoặc trước trade allowed check, nhưng bắt buộc trước `SendACK(cmdId)` và `RecordCmdId(cmdId)`. Không thêm database test vì task không liên quan database. Không xử lý request market-data/backfill ngoài scope; yêu cầu chỉ là order từ gateway.</action>
  <verify>
    <automated>git diff -- mql5/AureusProvider.mq5</automated>
    <automated>git diff -- mql5/AureusProvider.mq5 | grep -E "FindContextIndex\(symbol\)|SYMBOL_NOT_ALLOWED|UNKNOWN_SYMBOL|SendNACK"</automated>
    <automated>git diff -- mql5/AureusProvider.mq5 | grep -E "ExecuteCloseOrder|SendACK\(cmdId\)|RecordCmdId\(cmdId\)"</automated>
  </verify>
  <done>`ExecuteCloseOrder` và `ExecuteOpenOrder` đều reject symbol ngoài `InpSymbols` trước ACK/record/order execution; reject reason/log đọc được; allowed symbols không bị đổi luồng xử lý hiện có.</done>
</task>

<task type="auto">
  <name>Task 3: Verify scope, syntax-oriented review, and change detection</name>
  <files>mql5/AureusProvider.mq5</files>
  <action>Kiểm tra diff thủ công để đảm bảo thay đổi chỉ chạm đúng allowlist gate và logging. Nếu môi trường có MetaEditor/MetaTrader compiler CLI thì compile `mql5/AureusProvider.mq5`; nếu không có compiler trong repo/CI, ghi rõ limitation trong summary và dùng direct code review: braces balance quanh `ExecuteOpenOrder`/`ExecuteCloseOrder`, reject nằm trước ACK, không thay đổi request building. Chạy GitNexus detect changes trước khi kết thúc/commit theo CLAUDE.md; nếu GitNexus báo MQL5 không indexed thì ghi rõ và đối chiếu bằng `git diff --stat` + direct diff. Nếu command verification lỗi do môi trường, tham khảo `D:/Aureus/RUN_SERVICES.md` trước khi kết luận.</action>
  <verify>
    <automated>git diff --check -- mql5/AureusProvider.mq5</automated>
    <automated>git diff --stat -- mql5/AureusProvider.mq5</automated>
    <automated>npx gitnexus detect-changes || true</automated>
  </verify>
  <done>Diff clean, scope chỉ là `mql5/AureusProvider.mq5`, GitNexus detect-changes hoặc fallback direct diff đã xác nhận affected scope đúng kỳ vọng; summary nêu rõ không chạy DB E2E vì không phải database feature.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| gateway → MT5 provider TCP command | Gateway command payload là input bên ngoài vào Expert Advisor; `symbol` không được tin cậy dù gateway là service nội bộ. |
| MT5 provider → broker trade engine | Sau ACK/order validation, provider có thể gọi `OrderCheck`/`OrderSend`; symbol sai ở đây có thể dẫn đến lệnh ngoài danh sách vận hành. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-260425-VQN-01 | Tampering | `ExecuteOpenOrder`/`ExecuteCloseOrder` symbol field | mitigate | Validate `symbol` via `FindContextIndex(symbol)` derived from `InpSymbols` before ACK/record/order execution. |
| T-260425-VQN-02 | Repudiation | rejected order command logging | mitigate | Emit NACK reason and debug/log line containing `cmd_id` + `symbol` for rejected out-of-allowlist orders. |
| T-260425-VQN-03 | Elevation of Privilege | gateway command attempts trade on unconfigured instrument | mitigate | Do not call `OrderCheck`/`OrderSend` for symbols absent from `InpSymbols`. |
</threat_model>

<verification>
- `git diff --check -- mql5/AureusProvider.mq5` passes.
- Direct diff shows allowlist check occurs before `SendACK(cmdId)` and `RecordCmdId(cmdId)` in both open/close order paths.
- GitNexus impact/detect requirements are executed or documented as unavailable for MQL5 indexing, with direct code review fallback.
- No database E2E required because no database code/schema/persistence path is modified.
</verification>

<success_criteria>
- Provider accepts/processes gateway order commands only for symbols declared in `InpSymbols`.
- Provider safely rejects/ignores all other order symbols with clear NACK/log reason.
- Existing allowed-symbol behavior remains unchanged.
- Only `mql5/AureusProvider.mq5` is modified.
</success_criteria>

<output>
After completion, create `D:/Aureus/.planning/quick/260425-vqn-update-file-mql5-aureusprovider-mq5-chi-/260425-vqn-SUMMARY.md`.
</output>
