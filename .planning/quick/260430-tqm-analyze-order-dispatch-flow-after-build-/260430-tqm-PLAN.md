---
phase: quick-260430-tqm-analyze-order-dispatch-flow-after-build
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - .planning/quick/260430-tqm-analyze-order-dispatch-flow-after-build-/260430-tqm-REPORT.md
autonomous: true
requirements:
  - QUICK-260430-TQM
must_haves:
  truths:
    - "Report trả lời rõ sau build_order_command + dispatcher.enqueue_order thì order đi qua Redis queue, dispatcher, Redis commands channel, MT5 provider, ACK/NACK/result event như thế nào."
    - "Report kết luận có bằng chứng về xử lý nhiều order đồng thời: enqueue có thể nhận nhiều event, nhưng dispatch_loop hiện lpop và await dispatch_order từng order nên dispatch outbound là tuần tự trong một dispatcher instance."
    - "Report kết luận có bằng chứng về blocking risk: một order đang chờ ACK/result/retry/backoff trong dispatch_order sẽ giữ dispatch_loop và làm các order phía sau trong queue phải chờ, dù event_listener vẫn chạy độc lập để nhận event."
    - "Report liệt kê rủi ro và next steps thực tế, không đề xuất implementation quá phạm vi."
  artifacts:
    - path: ".planning/quick/260430-tqm-analyze-order-dispatch-flow-after-build-/260430-tqm-REPORT.md"
      provides: "Báo cáo phân tích luồng dispatch order sang MT5, concurrency, retry/timeout blocking risk"
      min_lines: 80
  key_links:
    - from: "services/aureus-trader/main.py"
      to: "services/aureus-trader/order_builder.py"
      via: "run_trader gọi build_order_command(event) trước enqueue"
      pattern: "build_order_command\(event\)"
    - from: "services/aureus-trader/main.py"
      to: "services/aureus-trader/dispatcher.py"
      via: "run_trader gọi dispatcher.enqueue_order(order_cmd)"
      pattern: "dispatcher\.enqueue_order\(order_cmd\)"
    - from: "services/aureus-trader/dispatcher.py"
      to: "mql5/AureusProvider_v2.mq5"
      via: "dispatch_order publish OPEN_ORDER payload lên COMMANDS_CHANNEL; provider ExecuteOpenOrder đọc command, SendACK/SendNACK/PushOrderOpened/PushOrderFailed"
      pattern: "redis\.publish\(COMMANDS_CHANNEL"
---

<objective>
Tạo báo cáo phân tích, bằng tiếng Việt, về luồng order sau `build_order_command` và `dispatcher.enqueue_order` tới MT5, tập trung vào concurrency, retry/timeout và nguy cơ blocking.

Purpose: Giúp user hiểu chính xác một hoặc nhiều order được đẩy sang MT5 theo cơ chế nào, order lỗi/retry/timeout có làm kẹt các order khác không, và nên ưu tiên hardening gì tiếp theo.
Output: `.planning/quick/260430-tqm-analyze-order-dispatch-flow-after-build-/260430-tqm-REPORT.md`
</objective>

<execution_context>
@D:/Aureus/.claude/get-shit-done/workflows/execute-plan.md
@D:/Aureus/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@D:/Aureus/CLAUDE.md
@D:/Aureus/.planning/STATE.md
@D:/Aureus/services/aureus-trader/main.py
@D:/Aureus/services/aureus-trader/order_builder.py
@D:/Aureus/services/aureus-trader/dispatcher.py
@D:/Aureus/mql5/AureusProvider_v2.mq5
@D:/Aureus/.planning/quick/260424-sbg-ph-n-ti-ch-nguy-n-nh-n-timeout-cu-a-lu-n/260424-sbg-REPORT.md
@D:/Aureus/.planning/quick/260429-897-ca-c-l-nh-limit-khi-va-o-l-nh-k-co-ticke/260429-897-REPORT.md

<interfaces>
Các điểm source đã xác định để executor trích dẫn line-level trong report:

- `services/aureus-trader/main.py`: `run_trader()` khởi tạo `OrderDispatcher`, start `dispatch_loop()` và `event_listener()` bằng `asyncio.create_task`, subscribe strategy channels, validate `STRATEGY_MATCH`, gọi `build_order_command(event)`, gắn `strategy_event`, check idempotency, rồi `await dispatcher.enqueue_order(order_cmd)`.
- `services/aureus-trader/order_builder.py`: `build_order_command()` tạo OPEN_ORDER command với `cmd_id`, `symbol`, `direction`, `order_type`, `volume`, `price`, `sl`, `tp`, `magic`, `comment`, optional `trace_id`, `tp_rr_ratio`, `size_mode`, `risk_amount`.
- `services/aureus-trader/dispatcher.py`: `enqueue_order()` dùng Redis `llen` + `rpush`; `dispatch_loop()` dùng `lpop` rồi `await self.dispatch_order(order)`; `dispatch_order()` publish payload lên `COMMANDS_CHANNEL`, chờ ACK/NACK bằng `_wait_for_response`, sau ACK chờ result, retry/backoff theo config; `event_listener()` subscribe `EVENTS_CHANNEL` và resolve `_pending_responses[cmd_id]`; `_extract_mt5_execution_payload()` allow field `trace_id`.
- `mql5/AureusProvider_v2.mq5`: `ExecuteOpenOrder()` parse raw command, reject duplicate/invalid/active strategy order, `SendACK(cmdId)` và `RecordCmdId(cmdId)` trước `OrderCheck`/`OrderSend`; success market/pending gọi `PushOrderOpened`; failure gọi `PushOrderFailed`; `SendNACK` dùng cho duplicate/invalid/trade disabled/strategy exists.
- Previous quick report `260424-sbg-REPORT.md`: đã ghi nhận ACK timeout, result timeout, retry cùng `cmd_id`, `NACK:DUPLICATE` là non-retryable và khuyến nghị timeout/correlation logging.
- Previous quick report `260429-897-REPORT.md`: đã mô tả limit order lifecycle/pending vs position ticket và các điểm route event liên quan dispatcher/provider/journal.
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Trace luồng order và concurrency từ source</name>
  <files>D:/Aureus/services/aureus-trader/main.py, D:/Aureus/services/aureus-trader/order_builder.py, D:/Aureus/services/aureus-trader/dispatcher.py, D:/Aureus/mql5/AureusProvider_v2.mq5, D:/Aureus/.planning/quick/260424-sbg-ph-n-ti-ch-nguy-n-nh-n-timeout-cu-a-lu-n/260424-sbg-REPORT.md, D:/Aureus/.planning/quick/260429-897-ca-c-l-nh-limit-khi-va-o-l-nh-k-co-ticke/260429-897-REPORT.md</files>
  <action>Đọc lại các file context và ghi chú line-level evidence cho 4 câu hỏi của user. Không sửa production code. Không chạy DB. Cần chứng minh rõ: (1) `build_order_command` chỉ build command, `enqueue_order` chỉ push vào Redis list; (2) `dispatch_loop` xử lý queue theo `lpop` + `await dispatch_order`, nên trong một dispatcher instance outbound dispatch là tuần tự; (3) `event_listener` chạy task riêng nên vẫn nhận ACK/result trong lúc dispatch_order chờ, nhưng chính dispatch_loop bị giữ bởi ACK timeout/result timeout/retry/backoff của order hiện tại; (4) MT5 provider ACK trước OrderSend, result là `ORDER_OPENED`/`ORDER_FAILED` hoặc NACK; (5) dùng previous reports để nối bối cảnh ACK timeout/NACK DUPLICATE và lifecycle limit nếu có liên quan.</action>
  <verify>
    <automated>python - <<'PY'
from pathlib import Path
paths = [
    Path('D:/Aureus/services/aureus-trader/main.py'),
    Path('D:/Aureus/services/aureus-trader/order_builder.py'),
    Path('D:/Aureus/services/aureus-trader/dispatcher.py'),
    Path('D:/Aureus/mql5/AureusProvider_v2.mq5'),
    Path('D:/Aureus/.planning/quick/260424-sbg-ph-n-ti-ch-nguy-n-nh-n-timeout-cu-a-lu-n/260424-sbg-REPORT.md'),
    Path('D:/Aureus/.planning/quick/260429-897-ca-c-l-nh-limit-khi-va-o-l-nh-k-co-ticke/260429-897-REPORT.md'),
]
for p in paths:
    assert p.exists(), p
print('source evidence files exist')
PY</automated>
  </verify>
  <done>Executor có danh sách bằng chứng cụ thể theo file/function/line để viết report, không còn điểm suy đoán không được gắn với source.</done>
</task>

<task type="auto">
  <name>Task 2: Viết report trả lời 4 câu hỏi của user</name>
  <files>D:/Aureus/.planning/quick/260430-tqm-analyze-order-dispatch-flow-after-build-/260430-tqm-REPORT.md</files>
  <action>Tạo report tiếng Việt tại đúng path. Cấu trúc bắt buộc: `## Kết luận ngắn`, `## 1. Luồng order sau build_order_command + enqueue_order`, `## 2. Nhiều order đến cùng lúc: tuần tự hay concurrent?`, `## 3. Một order lỗi/retry/timeout có block order khác không?`, `## 4. Rủi ro`, `## 5. Recommended next steps`, `## Evidence`. Kết luận phải nêu rõ: trong một `OrderDispatcher` hiện tại, nhiều order được enqueue nhanh nhưng dispatch từ Redis queue sang MT5 là tuần tự vì `dispatch_loop` await toàn bộ `dispatch_order`; một order timeout/retry có thể block các order phía sau trong queue cho tới khi nó return, với thời gian xấu nhất xấp xỉ ACK timeout/retry/backoff hoặc result timeout; event listener không bị block hoàn toàn vì là task riêng. Cần cite file/function/line-level evidence từ source và dẫn chiếu previous quick reports liên quan. Không thêm code implementation, không sửa ROADMAP/STATE, không commit.</action>
  <verify>
    <automated>python - <<'PY'
from pathlib import Path
p = Path('D:/Aureus/.planning/quick/260430-tqm-analyze-order-dispatch-flow-after-build-/260430-tqm-REPORT.md')
assert p.exists(), 'report missing'
text = p.read_text(encoding='utf-8')
required = [
    '## Kết luận ngắn',
    '## 1. Luồng order sau build_order_command + enqueue_order',
    '## 2. Nhiều order đến cùng lúc: tuần tự hay concurrent?',
    '## 3. Một order lỗi/retry/timeout có block order khác không?',
    '## 4. Rủi ro',
    '## 5. Recommended next steps',
    '## Evidence',
    'build_order_command',
    'enqueue_order',
    'dispatch_loop',
    'dispatch_order',
    'event_listener',
    'ExecuteOpenOrder',
    'SendACK',
    'PushOrderOpened',
    '260424-sbg',
]
missing = [s for s in required if s not in text]
assert not missing, missing
assert len(text.splitlines()) >= 80, 'report too short for evidence-backed analysis'
print('report structure ok')
PY</automated>
  </verify>
  <done>Report trả lời đầy đủ 4 câu hỏi, có bằng chứng concrete, có rủi ro và next steps, không thay đổi production/database.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Redis strategy pub/sub -> aureus-trader | STRATEGY_MATCH event từ Redis được validate/build thành order command. |
| aureus-trader -> Redis command channel -> MT5 provider | OPEN_ORDER payload vượt ranh giới Python service sang MT5 EA/provider. |
| MT5 provider -> Redis/event bridge -> aureus-trader | ACK/NACK/ORDER_OPENED/ORDER_FAILED event quay lại để resolve pending future. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-260430-tqm-01 | D | `OrderDispatcher.dispatch_loop` | mitigate | Report phải đánh giá DoS/queue blocking do một order chờ timeout/retry giữ dispatch loop tuần tự. |
| T-260430-tqm-02 | R | `cmd_id` correlation | mitigate | Report phải nêu nhu cầu correlation logging/metrics theo `cmd_id` cho publish, ACK/NACK, result, retry. |
| T-260430-tqm-03 | T | Redis command/event payload | accept | Task chỉ phân tích, không sửa auth/transport; ghi nhận đây là trust boundary nếu cần hardening sau. |
</threat_model>

<verification>
Chạy automated verify trong từng task. Sau khi report tạo xong, đọc report một lần để đảm bảo trả lời trực tiếp 4 câu hỏi, không chỉ mô tả chung chung.
</verification>

<success_criteria>
- File `D:/Aureus/.planning/quick/260430-tqm-analyze-order-dispatch-flow-after-build-/260430-tqm-REPORT.md` tồn tại.
- Report bằng tiếng Việt.
- Report kết luận rõ sequential vs concurrent và blocking risk.
- Report có bằng chứng file/function/line-level nơi khả thi.
- Không sửa production code, không sửa database, không commit.
</success_criteria>

<output>
Sau completion, không cần tạo SUMMARY trừ khi executor workflow yêu cầu. Artifact chính là `D:/Aureus/.planning/quick/260430-tqm-analyze-order-dispatch-flow-after-build-/260430-tqm-REPORT.md`.
</output>
