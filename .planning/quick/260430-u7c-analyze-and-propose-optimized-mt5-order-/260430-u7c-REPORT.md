# Báo cáo quick 260430-u7c: Đề xuất tối ưu kiến trúc dispatch order MT5

## 1. Executive summary

Kiến trúc hiện tại của `aureus-trader -> aureus-gateway -> MT5 provider` tương đối đơn giản và có nhiều phần đúng cần giữ: command có `cmd_id` idempotent, payload gửi sang MT5 đã được allowlist, Redis channel tách command/event, provider có ACK/NACK/result, và MT5 đang có lớp chặn duplicate theo `symbol + magic + direction`.

Vấn đề chính không nằm ở `build_order_command()`. Vấn đề nằm ở tầng dispatch: một instance `OrderDispatcher` đang dùng global FIFO queue và `dispatch_loop()` chờ trọn `dispatch_order()` của một order, bao gồm ACK wait, result wait, retry/backoff, rồi mới lấy order kế tiếp. Vì vậy một order bị timeout có thể tạo head-of-line blocking và làm các order độc lập phía sau chậm tới khoảng 30s hoặc hơn.

Mục tiêu hợp lý không phải là biến MT5 thành hệ thống khớp lệnh song song thật sự. MT5 terminal/EA vẫn chạy handler tuần tự và broker side effect vẫn phải cẩn thận. Mục tiêu nên là: handoff command từ trader sang gateway/MT5 trong 1-2s cho các lane độc lập, sau đó xử lý ACK/result bất đồng bộ, có bounded concurrency, có khóa an toàn theo `symbol + magic + direction`, và có reconcile khi timeout mơ hồ.

Khuyến nghị chính (recommended option): triển khai scheduler theo lane `symbol + magic + direction`, mỗi lane chỉ có một command active, nhưng nhiều lane độc lập được in-flight đồng thời trong một giới hạn bounded. Kết hợp dần với state machine cho ACK/result để dispatch queue không bị giữ bởi `result_timeout`.

## 2. Luồng hiện tại và latency budget

Pipeline hiện tại:

```text
STRATEGY_MATCH
 -> services/aureus-trader/main.py run_trader()
 -> build_order_command()
 -> dispatcher.enqueue_order() / Redis list
 -> dispatch_loop() / lpop
 -> dispatch_order() / Redis COMMANDS_CHANNEL
 -> services/aureus-gateway/main.py run_command_subscriber()
 -> TCP writer.write + writer.drain
 -> MT5 OnTimer()
 -> ProcessIncomingCommands()
 -> ExecuteOpenOrder()
 -> ACK/NACK
 -> ORDER_OPENED / ORDER_PENDING_PLACED / ORDER_FILLED / ORDER_FAILED
```

### 2.1 Evidence ở trader

Trong `services/aureus-trader/main.py`, `run_trader()` start hai task độc lập: `dispatcher.dispatch_loop()` tại `main.py:77` và `dispatcher.event_listener()` tại `main.py:81`. Phần nhận signal filter `STRATEGY_MATCH`, validate, build command, gắn `strategy_event`, check idempotency, rồi enqueue tại `main.py:91-120`.

`services/aureus-trader/order_builder.py:40-91` chỉ build dict `OPEN_ORDER`: `cmd_id`, `symbol`, `direction`, `order_type`, `volume`, `price`, `sl`, `tp`, `magic`, `comment`, optional `trace_id`, `tp_rr_ratio`, `size_mode`, `risk_amount`. Không có publish sang MT5 trong hàm này.

`OrderDispatcher.enqueue_order()` ở `services/aureus-trader/dispatcher.py:65-79` chỉ `llen` để check queue size rồi `rpush(ORDER_QUEUE_KEY, json.dumps(order_cmd))`. Đây là enqueue nội bộ, chưa sang MT5.

Điểm blocking chính nằm ở `services/aureus-trader/dispatcher.py:81-99`: `dispatch_loop()` lấy `raw = await self.redis.lpop(ORDER_QUEUE_KEY)`, nếu rỗng thì `await asyncio.sleep(0.5)`, nếu có order thì `await self.dispatch_order(order)`. Dòng `await self.dispatch_order(order)` khiến một dispatcher instance xử lý outbound tuần tự.

Trong `dispatch_order()` tại `dispatcher.py:100-184`, order được publish lên `COMMANDS_CHANNEL` rồi chờ ACK/NACK bằng `_wait_for_response(cmd_id, self.config.ack_timeout)` tại `dispatcher.py:117-120`. Nếu ACK, tiếp tục chờ final bằng `_wait_for_response(cmd_id, self.config.result_timeout)` tại `dispatcher.py:146-150`. Retry/backoff dùng `await asyncio.sleep(2**attempt)` tại `dispatcher.py:127-129`, `dispatcher.py:134-141`, và `dispatcher.py:171-177`.

Default config ở `services/aureus-trader/config.py:17-20` là `ack_timeout=5.0`, `result_timeout=30.0`, `max_retries=3`.

### 2.2 Evidence ở gateway

`services/aureus-gateway/main.py:462-520` có `run_command_subscriber()` subscribe Redis channel `aureus:mt5:commands`. Khi có command theo symbol, gateway lấy `active_connections[symbol]`, gọi `writer.write(payload.encode('utf-8'))`, rồi `await writer.drain()` tại `main.py:503-510`.

`writer.drain()` là điểm latency hợp lệ: nếu socket buffer/backpressure hoặc EA connection chậm, coroutine sẽ chờ. Gateway hiện forward theo từng writer trong set active connections của symbol. Nó không phải nguyên nhân 30s chính theo code hiện tại, nhưng là hop cần đo latency vì nằm trên đường handoff sang MT5.

### 2.3 Evidence ở MT5 provider

`mql5/AureusProvider_v2.mq5:2721-2724` cho thấy `OnTimer()` gọi `ProcessIncomingCommands()`. Trong `ProcessIncomingCommands()` tại `AureusProvider_v2.mq5:2520-2538`, EA check socket, `g_socket.Receive()`, detect `"OPEN_ORDER"`, rồi gọi `ExecuteOpenOrder(raw)`.

`ExecuteOpenOrder()` tại `AureusProvider_v2.mq5:1838-2304` parse `cmd_id`, `symbol`, `direction`, `order_type`, volume, price, SL/TP, magic, comment, risk fields và `trace_id` tại `1840-1854`.

Provider gửi NACK sớm cho invalid command và duplicate cmd_id tại `1863-1875`, duplicate active strategy position/order cùng `symbol + magic + direction` tại `1885-1936`, và trade disabled tại `1939-1944`. Nếu accept, provider gửi `SendACK(cmdId)` rồi `RecordCmdId(cmdId)` tại `1946-1948`, trước `OrderCheck`/`OrderSend`.

Result được push bằng `PushOrderFailed()` khi `OrderCheck`/`OrderSend`/retcode fail tại `2113-2130` và `2288-2295`; hoặc `PushOrderOpened()` khi success tại `2225-2273` và `2277-2285`. `SendACK()` format JSON tại `850-858`, `SendNACK()` tại `865-873`, `PushOrderOpened()` tại `973-984`, `PushOrderFailed()` tại `991-1000`.

Một điểm rủi ro cụ thể: nếu `FindContextIndex(symbol) < 0`, code ở `AureusProvider_v2.mq5:1877-1882` đang return im lặng vì `SendNACK(cmdId, "SYMBOL_NOT_ALLOWED")` bị comment. Path này làm trader chờ ACK timeout thay vì reject nhanh.

## 3. Vì sao latency hiện tại có thể tới khoảng 30s

Có bốn nguồn latency/blocking chính:

1. Empty queue polling: `dispatch_loop()` sleep tối đa 0.5s khi queue rỗng (`dispatcher.py:88-90`). Đây là nhỏ, nhưng vẫn là baseline jitter trước khi order được lpop.

2. Global sequential wait: `dispatch_loop()` `await self.dispatch_order(order)` (`dispatcher.py:93-94`). Đây là nguyên nhân head-of-line blocking: order sau không được publish cho tới khi order trước hoàn tất ACK/result/retry/timeout.

3. Result timeout sau ACK: nếu ACK đã về nhưng final result không về, `dispatch_order()` chờ `result_timeout=30.0` theo config (`dispatcher.py:146-155`, `config.py:18-20`). Trong 30s này order khác vẫn nằm trong Redis list.

4. ACK timeout + retry/backoff: nếu ACK không về, mỗi attempt chờ `ack_timeout=5s`; với `max_retries=3`, vòng `range(max_retries + 1)` có 4 lần publish/chờ ACK, cộng backoff 1+2+4=7s. Tổng xấu nhất khoảng `4*5 + 7 = 27s` trước khi max retries. Đây gần bằng 30s ngay cả chưa tính gateway/MT5 jitter.

Các điểm bổ sung làm tình hình xấu hơn:

- Gateway `writer.drain()` có thể chờ nếu TCP writer bị backpressure.
- MT5 provider xử lý command trong `OnTimer()`/EA event loop, không phải worker pool song song.
- Silent no-NACK path khi symbol không thuộc `InpSymbols` khiến trader timeout vô ích.
- Sau ACK, trạng thái timeout là mơ hồ: provider có thể đã side-effect order nhưng event result bị rơi/chậm.

Bằng chứng runtime từ report trước `260424-sbg`: hai order queued gần như cùng lúc ở `13:20:01.636` và `13:20:01.638`; order A result timeout ở `13:20:30.842`; order B mới bắt đầu ACK timeout attempt sau đó ở `13:20:35.851`, rồi retry và nhận `NACK:DUPLICATE` ở `13:20:51.903`. Timeline này khớp với global sequential dispatch.

## 4. Phần cần giữ vs phần đang over-complicated/rủi ro

### 4.1 Phần cần giữ

- Deterministic `cmd_id` và idempotency: `generate_cmd_id()` tạo key ổn định từ strategy/symbol/time/direction; Redis dedup ở trader và provider dedup bằng `RecordCmdId()` giúp tránh double side effect.
- Payload allowlist: `_extract_mt5_execution_payload()` tại `dispatcher.py:301-324` chỉ gửi field cần thiết sang MT5, không gửi `strategy_event` nặng.
- Redis `COMMANDS_CHANNEL` và `EVENTS_CHANNEL`: tách command/event rõ ràng, dễ quan sát.
- ACK/NACK/result semantics: ACK nghĩa là provider accept command, final result mới nói side effect order.
- Provider-side duplicate lock: `ExecuteOpenOrder()` chặn active position/order cùng `symbol + magic + direction`; đây là safety constraint quan trọng cho entry/DCA.
- Journal correlation bằng `trace_id`, `cmd_id`, `strategy_event` nội bộ Python: cần giữ để lifecycle persistence không mất ngữ cảnh.

### 4.2 Phần over-complicated hoặc rủi ro

- Global FIFO queue chờ final result trước khi gửi order tiếp theo. Đây là thiết kế đơn giản nhưng gây blocking quá rộng.
- Retry/backoff nằm trong cùng `dispatch_order()` mà `dispatch_loop()` đang await, làm retry của một order block order khác.
- `RESULT_TIMEOUT` bị xử lý gần như rejection/max retries, trong khi sau ACK thì timeout là ambiguous, có thể đã có side effect ở MT5.
- `NACK:DUPLICATE` sau ACK lost dễ bị hiểu là business reject, trong khi nó có thể là duplicate recovery signal.
- Một global queue cho mọi symbol khiến lỗi của `XAUUSD` có thể delay `BTCUSD`, `ETHUSD`, hoặc symbol khác không liên quan.
- Nếu provider vẫn dùng `ORDER_OPENED` cho pending accepted ở một số path, semantics limit/pending bị mơ hồ; dispatcher hiện đã nhận `ORDER_PENDING_PLACED`/`ORDER_FILLED`, nhưng provider path cần đồng bộ trong task riêng.
- Silent return khi symbol không thuộc `InpSymbols` tạo no-response path không cần thiết.

## 5. Option kiến trúc để đạt 1-2s send-to-MT5 và tránh block order khác

### Option A: Minimal hardening, vẫn sequential

Nội dung:
- Bật NACK rõ cho `SYMBOL_NOT_ALLOWED` thay vì return im lặng.
- Thêm metrics enqueue age, publish-to-ACK, ACK-to-result, gateway write latency.
- Phân loại timeout rõ hơn: `ACK_TIMEOUT_NO_PROVIDER_RESPONSE`, `RESULT_TIMEOUT_AFTER_ACK`, `ACK_LOST_DUPLICATE_RECOVERY`.
- Giữ `dispatch_loop()` sequential như hiện tại.

Ưu điểm:
- Ít thay đổi nhất, rủi ro triển khai thấp.
- Giải quyết path timeout vô ích do no-NACK.
- Tăng khả năng debug nhanh theo `cmd_id`.

Nhược điểm:
- Không giải quyết bản chất head-of-line blocking.
- Một order result timeout vẫn block order sau khoảng 30s.
- Không đạt mục tiêu non-blocking cho các order độc lập.

Test cần có:
- Symbol không nằm trong `InpSymbols` phải nhận NACK nhanh.
- Metrics có đủ các mốc enqueue/publish/gateway/ACK/result.

Kết luận: cần làm Phase 1, nhưng không đủ làm kiến trúc cuối.

### Option B: Bounded in-flight worker pool / semaphore

Nội dung:
- `dispatch_loop()` lấy nhiều order và `create_task(dispatch_order)` nhưng qua semaphore giới hạn, ví dụ 2-4 in-flight.
- Mỗi order tự chờ ACK/result, order khác vẫn có thể publish.
- Giữ event listener match `cmd_id` vào pending future.

Ưu điểm:
- Giảm head-of-line blocking rõ rệt.
- Dễ triển khai hơn full state machine.
- Có thể đạt 1-2s handoff cho order phía sau nếu gateway/MT5 không nghẽn.

Nhược điểm/rủi ro:
- Nếu chỉ dùng worker pool global, có thể gửi nhiều order cùng `symbol + magic + direction` trước khi provider lock phản hồi, tăng NACK hoặc race semantic.
- MT5 EA vẫn không xử lý song song thật; concurrency quá cao chỉ dồn áp lực vào gateway/provider/broker.
- Cần quản lý pending futures và cancellation sạch.

Test cần có:
- ACK timeout của order A không ngăn order B publish trong 1-2s.
- Concurrency cap hoạt động, không tạo unbounded tasks.
- Duplicate/cùng lane không in-flight đồng thời.

Kết luận: tốt hơn hiện tại nhưng phải kết hợp lane lock; nếu không sẽ thiếu an toàn trading.

### Option C: Per-symbol hoặc per `symbol + magic + direction` lanes

Nội dung:
- Mỗi order được gán lane key: `symbol + magic + direction`.
- Mỗi lane chỉ có một active command; nhiều lane độc lập có thể chạy concurrently trong global bounded in-flight limit.
- Lanes có queue riêng hoặc scheduler chọn order ready từ global queue rồi dispatch nếu lane đang free.

Ưu điểm:
- Giảm head-of-line blocking giữa các symbol/strategy/direction độc lập.
- Phù hợp với safety lock hiện có trong provider: duplicate strategy order cũng theo `symbol + magic + direction`.
- Không biến MT5 thành fully parallel; chỉ tăng handoff cho lane độc lập.
- Dễ kiểm soát DCA/entry: cùng lane không bị gửi chồng.

Nhược điểm/rủi ro:
- Cần thiết kế scheduler để không starvation lane nào.
- Cần lưu trạng thái lane khi timeout ambiguous; không được release lane quá sớm nếu có thể đã side-effect.
- Cần reconcile để unlock lane an toàn sau `RESULT_TIMEOUT_AFTER_ACK`.

Test cần có:
- Lane A timeout ACK/result, lane B khác symbol/magic/direction vẫn publish trong 1-2s.
- Hai order cùng lane không publish đồng thời.
- `NACK:STRATEGY_ORDER_EXISTS`/duplicate release lane đúng.
- `RESULT_TIMEOUT_AFTER_ACK` không bị coi là business reject và không mở flood retry cùng lane.

Kết luận: đây là option cân bằng nhất cho hệ thống trading hiện tại.

### Option D: State-machine dispatcher

Nội dung:
- Tách handoff khỏi final wait: dispatch loop publish/register pending state nhanh rồi tiếp tục xử lý order/lane khác.
- Event listener chuyển state: `PUBLISHED -> ACKED/NACKED -> FINAL_SUCCESS/FINAL_FAILED/TIMEOUT_AMBIGUOUS`.
- Journal/result handling chạy async theo state transitions.

Ưu điểm:
- Kiến trúc sạch nhất về mặt messaging.
- Loại bỏ việc queue loop chờ `result_timeout`.
- Dễ gắn metrics, retry policy, reconcile, và persistence state.

Nhược điểm/rủi ro:
- Scope lớn hơn; phải thay đổi nhiều test và semantics.
- Nếu không có persistence/reconcile tốt, restart giữa chừng có thể mất pending state.
- Cần định nghĩa rõ timeout, duplicate recovery, result late arrival.

Test cần có:
- Late result sau timeout vẫn được match và reconcile đúng.
- Restart/recovery hoặc ít nhất Redis state TTL cho pending command.
- ACK lost rồi duplicate NACK được classify `ACK_LOST_DUPLICATE_RECOVERY`.

Kết luận: là hướng kiến trúc dài hạn tốt, nhưng nên triển khai sau khi có lane scheduler/observability.

### Option E: One process per order

Đây là ý tưởng người dùng nêu: mỗi order chạy một process riêng để order này timeout không block order khác.

Lợi ích:
- Fault isolation ở Python process tốt hơn: một process bị treo/crash ít ảnh hưởng process khác.
- Không bị blocking do `await dispatch_order()` trong cùng loop nếu mỗi process tự xử lý order của nó.
- Có thể đơn giản về tư duy ban đầu: mỗi order là một worker độc lập.

Rủi ro:
- Process explosion nếu nhiều signal đến cùng lúc; startup overhead của OS process thường lớn hơn nhiều so với `asyncio.Task`.
- Nhiều process cùng consume Redis/gửi command dễ tạo race, duplicate, khó cap concurrency.
- Correlation `_pending_responses` nằm trong process riêng; event pub/sub ACK/result phải route đúng process, hoặc mọi process đều nghe event rồi filter, gây lãng phí và khó debug.
- Idempotency/reconcile phức tạp hơn vì state phân tán theo process.
- Observability khó hơn: log/metrics theo `cmd_id` rải ở nhiều process ngắn hạn.
- MT5 terminal/EA/account vẫn là boundary tuần tự/sensitive; nhiều process Python không làm broker side effect song song an toàn hơn.
- Khó enforce `symbol + magic + direction` lock tập trung nếu không có distributed lock chuẩn.

Khuyến nghị: không dùng one OS process per order làm kiến trúc chính. Nếu cần isolation, dùng bounded worker tasks/lanes trong một service trước; chỉ cân nhắc process pool cố định hoặc service instances cố định sau khi có đo đạc chứng minh Python event loop là bottleneck. Hiện bottleneck chính là queue design và ACK/result semantics, không phải thiếu OS process.

## 6. Khuyến nghị kiến trúc tốt nhất

Khuyến nghị: `per-symbol + magic + direction lane scheduler` kết hợp bounded in-flight async state machine theo từng bước.

Tên ngắn: bounded lane dispatcher.

Cách hoạt động đề xuất:

1. Order vào queue vẫn giữ `cmd_id` deterministic và Redis dedup.
2. Dispatcher xác định lane key từ `symbol`, `magic`, `direction`.
3. Nếu lane đang free và global in-flight chưa vượt cap, publish command sang `COMMANDS_CHANNEL`, register pending state, mark lane active.
4. Dispatch loop không chờ final result 30s trước khi xét lane khác; nó tiếp tục handoff order ở lane độc lập.
5. ACK/NACK/result event chuyển state và release lane theo rule an toàn.
6. Với `RESULT_TIMEOUT_AFTER_ACK`, không release/đánh reject mù ngay; chuyển trạng thái ambiguous và chạy reconcile MT5.

Vì sao option này có thể đạt 1-2s send-to-MT5:

- Order ở lane B không phải chờ lane A hết `result_timeout=30s`.
- Dispatch loop chỉ cần publish/register pending nhanh, thường trong mili-giây đến dưới 1-2s nếu Redis/gateway/socket khỏe.
- Global bounded cap bảo vệ gateway/MT5 khỏi flood.
- Per-lane single active command bảo vệ cùng strategy/symbol/direction khỏi gửi chồng.

## 7. Safety constraints bắt buộc

1. Lane/lock identity phải là `symbol + magic + direction`, không chỉ symbol. Lý do: cùng symbol có thể có nhiều magic/strategy; BUY và SELL có thể được quản lý riêng theo các task gần đây của `AureusProvider_v2`.

2. Idempotency phải giữ nhiều lớp:
   - deterministic `cmd_id` từ event;
   - Redis dedup ở trader;
   - provider dedup `IsDuplicateCmd`/`RecordCmdId`;
   - retry cùng `cmd_id`, không generate cmd mới cho cùng intent;
   - duplicate sau ACK lost phải classify recovery, không coi đơn giản là reject.

3. ACK/result semantics phải rõ:
   - ACK chỉ nghĩa là provider accepted command sau validate/dedup, chưa đảm bảo broker side effect.
   - Final result mới xác nhận `ORDER_OPENED`, `ORDER_PENDING_PLACED`, `ORDER_FILLED`, hoặc `ORDER_FAILED`.
   - `RESULT_TIMEOUT_AFTER_ACK` là ambiguous; không được publish business rejection đơn giản nếu chưa reconcile.

4. Không unbounded concurrency:
   - Có global max in-flight.
   - Mỗi lane chỉ một active command.
   - Có timeout/circuit breaker nhưng không retry vô hạn.

5. Reconcile khi timeout mơ hồ:
   - Query MT5 positions/orders/history bằng `cmd_id`, `trace_id`, `symbol`, `magic`, `direction`, comment nếu có.
   - Với pending order, cần tìm pending order id và later fill event.
   - Late result sau timeout vẫn phải được accept và cập nhật state nếu match `cmd_id`.

6. Provider duplicate strategy lock phải giữ:
   - Không cho nhiều active order cùng `symbol + magic + direction` nếu business rule vẫn là một entry/DCA lane.
   - `InpSymbols` validation phải reject rõ bằng NACK, không silent return.

7. Observability là safety requirement:
   - Log/metrics theo `cmd_id` ở enqueue, dequeue, publish, gateway write, provider receive, ACK, NACK, result, timeout, retry, reconcile.

## 8. Phased implementation steps

### Phase 1: Observability và explicit no-response fixes

- Bổ sung NACK rõ cho symbol không thuộc `InpSymbols`, ví dụ `SYMBOL_NOT_ALLOWED`.
- Thêm metrics/log:
  - enqueue timestamp và queue age;
  - publish timestamp;
  - publish-to-ACK latency;
  - ACK-to-result latency;
  - gateway `writer.drain` latency;
  - provider receive-to-ACK và ACK-to-result nếu có thể;
  - timeout class theo `cmd_id`.
- Phân loại lỗi:
  - `ACK_TIMEOUT_NO_PROVIDER_RESPONSE`;
  - `RESULT_TIMEOUT_AFTER_ACK`;
  - `ACK_LOST_DUPLICATE_RECOVERY`;
  - `MT5_REJECT_NON_RETRYABLE`.

Mục tiêu: biết chính xác bottleneck trước khi đổi concurrency sâu.

### Phase 2: Lane scheduler với bounded concurrent in-flight tasks

- Implement lane key `symbol + magic + direction`.
- Cho phép nhiều lane khác nhau in-flight đồng thời, nhưng cap global, ví dụ 2-4 trước khi đo đạc.
- Không cho hai command cùng lane publish đồng thời.
- Test mô phỏng: lane A ACK timeout/result timeout, lane B vẫn publish trong 1-2s.
- Test cùng lane: order B cùng `symbol + magic + direction` phải chờ lane A resolve/reconcile.

Mục tiêu: loại bỏ head-of-line blocking giữa các lane độc lập.

### Phase 3: Result state machine và reconcile

- Tách trạng thái command khỏi stack `dispatch_order()`.
- Event listener transition state và xử lý late events.
- `RESULT_TIMEOUT_AFTER_ACK` chuyển ambiguous, trigger reconcile thay vì reject ngay.
- `NACK:DUPLICATE` sau ACK timeout classify `ACK_LOST_DUPLICATE_RECOVERY`, sau đó reconcile theo `cmd_id`/`trace_id`/symbol/magic/direction.
- Journal update theo final/reconcile result, không ghi sai business rejection.

Mục tiêu: xử lý đúng side effect mơ hồ.

### Phase 4: Gateway/MT5 optimization nếu metrics chứng minh còn nghẽn

- Nếu `writer.drain()` chậm: cân nhắc queue writer riêng theo symbol/connection, timeout write, và metric backpressure.
- Nếu `OnTimer()` polling chậm: xem lại timer interval/socket receive loop của provider.
- Nếu provider result emit chậm: tối ưu code quanh `OrderCheck`/`OrderSend`/event push.
- Chỉ tối ưu sau khi Phase 1-3 cho thấy bottleneck còn ở gateway/MT5, không đoán trước.

## 9. Những việc không nên làm ngay

- Không spawn one OS process per order làm giải pháp chính; nói cách khác, không spawn process riêng cho từng order.
- Không bỏ idempotency/retry; chỉ phân loại retry/timeout đúng hơn.
- Không cho nhiều lệnh cùng `symbol + magic + direction` in-flight.
- Không coi MT5 là fully parallel chỉ vì Python dùng async/concurrent tasks.
- Không rút ngắn timeout một cách mù quáng để đạt chỉ số latency; timeout sau ACK cần reconcile, không phải reject nhanh.
- Không sửa source trong task report này; cần plan implementation riêng với test concurrency.

## 10. Evidence table

| Chủ đề | File/function/line | Bằng chứng |
|---|---|---|
| Trader start tasks | `services/aureus-trader/main.py:74-82` | Start `dispatch_loop()` và `event_listener()` bằng `asyncio.create_task`. |
| Strategy to enqueue | `services/aureus-trader/main.py:91-120` | Filter `STRATEGY_MATCH`, validate, `build_order_command`, dedup, `enqueue_order`. |
| Build command | `services/aureus-trader/order_builder.py:40-91` | Tạo `OPEN_ORDER` dict, không publish sang MT5. |
| Config timeouts | `services/aureus-trader/config.py:17-20` | `ack_timeout=5.0`, `result_timeout=30.0`, `max_retries=3`. |
| Enqueue Redis list | `services/aureus-trader/dispatcher.py:65-79` | `llen`, `rpush(ORDER_QUEUE_KEY, json.dumps(order_cmd))`. |
| Sequential dispatch | `services/aureus-trader/dispatcher.py:81-99` | `lpop` rồi `await self.dispatch_order(order)`. |
| ACK wait | `services/aureus-trader/dispatcher.py:117-120` | `_wait_for_response(cmd_id, ack_timeout)`. |
| Result wait | `services/aureus-trader/dispatcher.py:146-155` | Sau ACK chờ final bằng `result_timeout`. |
| Retry/backoff | `services/aureus-trader/dispatcher.py:127-129`, `134-141`, `171-177` | Sleep `2**attempt` trong cùng dispatch order. |
| Payload allowlist | `services/aureus-trader/dispatcher.py:301-324` | Chỉ gửi fields cần thiết sang MT5. |
| Event listener | `services/aureus-trader/dispatcher.py:186-224` | Subscribe event, match `cmd_id`, resolve future. |
| Gateway bridge | `services/aureus-gateway/main.py:462-520` | Subscribe `aureus:mt5:commands`, write TCP, `await writer.drain()`. |
| Provider receive | `mql5/AureusProvider_v2.mq5:2520-2538` | `g_socket.Receive()`, detect `OPEN_ORDER`, gọi `ExecuteOpenOrder`. |
| Provider OnTimer | `mql5/AureusProvider_v2.mq5:2721-2724` | `OnTimer()` gọi `ProcessIncomingCommands()`. |
| Provider parse | `mql5/AureusProvider_v2.mq5:1840-1854` | Parse `cmd_id`, symbol, direction, order_type, magic, trace_id. |
| Silent symbol path | `mql5/AureusProvider_v2.mq5:1877-1882` | `SYMBOL_NOT_ALLOWED` NACK đang bị comment, return im lặng. |
| Duplicate strategy lock | `mql5/AureusProvider_v2.mq5:1885-1936` | Chặn existing position/order cùng symbol/magic/side. |
| ACK before OrderSend | `mql5/AureusProvider_v2.mq5:1946-1948` | `SendACK` và `RecordCmdId` trước `OrderCheck`/`OrderSend`. |
| Result events | `mql5/AureusProvider_v2.mq5:2113-2130`, `2225-2285`, `2288-2295` | Push failed/opened theo outcome. |
| ACK JSON | `mql5/AureusProvider_v2.mq5:850-858` | `SendACK()` gửi JSON ACK. |
| NACK JSON | `mql5/AureusProvider_v2.mq5:865-873` | `SendNACK()` gửi JSON NACK. |
| Previous timeout incident | `.planning/quick/260424-sbg.../260424-sbg-REPORT.md:5-12` | Timeline 2 order queued cùng lúc, order sau bị delay và NACK duplicate. |
| Previous flow analysis | `.planning/quick/260430-tqm.../260430-tqm-REPORT.md:1-10` | Xác nhận outbound dispatch tuần tự và head-of-line blocking. |

## 11. Trả lời trực tiếp 5 câu hỏi bắt buộc

1. Vì sao flow hiện tại có thể mất tới 30s và latency/blocking nằm ở đâu?  
   Vì `dispatch_loop()` chờ `dispatch_order()` hoàn tất. `dispatch_order()` chờ ACK tối đa 5s mỗi attempt, retry/backoff có thể khoảng 27s khi ACK mất liên tiếp; nếu ACK đã về nhưng result mất/chậm thì chờ `result_timeout=30s`. Trong thời gian đó order phía sau không được publish. Gateway `writer.drain()`, MT5 `OnTimer()`, và silent no-NACK symbol path là các điểm latency bổ sung.

2. Phần nào cần thiết vs over-complicated?  
   Cần giữ `cmd_id` idempotency, payload allowlist, Redis command/event channels, ACK/NACK/result semantics, provider duplicate lock theo symbol/magic/direction, và journal correlation. Rủi ro/over-complicated là global FIFO chờ final result, retry nằm trong loop tuần tự, timeout sau ACK bị coi như reject, duplicate sau ACK lost bị mơ hồ, một queue cho mọi symbol, và silent no-response path.

3. Option kiến trúc cụ thể để target 1-2s send-to-MT5 và tránh block order khác?  
   Option A minimal hardening; Option B bounded in-flight worker pool; Option C lane scheduler theo `symbol + magic + direction`; Option D state-machine dispatcher; Option E one process per order. Option C kết hợp dần Option D là khuyến nghị tốt nhất.

4. Đánh giá one process per order?  
   Có lợi về fault isolation và tránh blocking Python await trong cùng loop, nhưng không khuyến nghị làm kiến trúc chính vì process overhead, process explosion, khó correlation ACK/result, khó idempotency/reconcile, khó enforce lock, và MT5 vẫn không parallel thật. Nên dùng bounded async tasks/lanes thay vì one OS process per order.

5. Best option và lộ trình/safety constraints?  
   Best option là bounded lane dispatcher theo `symbol + magic + direction`, sau đó nâng lên state machine ACK/result và reconcile. Lộ trình: Phase 1 observability + explicit NACK; Phase 2 lane scheduler bounded in-flight; Phase 3 state machine + reconcile `RESULT_TIMEOUT_AFTER_ACK`/`ACK_LOST_DUPLICATE_RECOVERY`; Phase 4 tối ưu gateway/MT5 nếu metrics chứng minh cần. Safety constraints: lane lock, idempotency nhiều lớp, ACK/result semantics rõ, bounded concurrency, reconcile timeout mơ hồ, giữ provider duplicate lock và `InpSymbols` validation.
