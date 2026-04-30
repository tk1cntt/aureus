# Báo cáo quick 260430-tqm: Luồng dispatch order sau build_order_command và enqueue_order

## Kết luận ngắn

1. Sau `build_order_command(event)` và `dispatcher.enqueue_order(order_cmd)`, order **chưa đi thẳng sang MT5**. Python trader chỉ tạo command `OPEN_ORDER`, gắn thêm `strategy_event`, check idempotency rồi push JSON vào Redis list `ORDER_QUEUE_KEY` bằng `rpush`. Sau đó `OrderDispatcher.dispatch_loop()` mới `lpop` từng item, gọi `dispatch_order()`, publish payload tối giản lên Redis `COMMANDS_CHANNEL`; gateway/bridge chuyển command đó qua socket tới MT5 provider, nơi `ProcessIncomingCommands()` nhận raw JSON và gọi `ExecuteOpenOrder()`.

2. Nhiều order đến cùng lúc có thể được nhận/enqueue liên tiếp, nhưng trong **một instance `OrderDispatcher` hiện tại**, outbound dispatch từ queue sang MT5 là **tuần tự**: `dispatch_loop()` lấy một order bằng `lpop` rồi `await self.dispatch_order(order)` đến khi order đó ACK/NACK/result/timeout/retry xong mới lấy order tiếp theo.

3. Nếu một order bị retry/timeout/error, order khác **có thể bị kẹt phía sau trong Redis queue** cho tới khi `dispatch_order()` của order hiện tại return. `event_listener()` vẫn là task riêng nên vẫn có thể nhận ACK/result cho order đang pending, nhưng nó không làm `dispatch_loop()` xử lý order tiếp theo song song.

4. Rủi ro chính là head-of-line blocking: một order gặp ACK timeout, result timeout, hoặc retry/backoff sẽ giữ loop tuần tự và làm tăng latency cho toàn bộ queue phía sau. Rủi ro này đã liên quan trực tiếp tới incident trước `260424-sbg` về ACK timeout/result timeout/NACK duplicate.

## 1. Luồng order sau build_order_command + enqueue_order

### 1.1 Strategy event vào trader

Trong `services/aureus-trader/main.py`, `run_trader()` khởi tạo Redis, `IdempotencyChecker`, `OrderDispatcher`, rồi start hai task độc lập:

- `dispatch_task = asyncio.create_task(dispatcher.dispatch_loop())` tại `main.py:77`.
- `event_task = asyncio.create_task(dispatcher.event_listener())` tại `main.py:81`.

Sau đó trader subscribe các kênh signal theo symbol (`main.py:85-88`) và loop qua Redis pub/sub (`main.py:91-93`). Chỉ event có `type == "STRATEGY_MATCH"` mới được xử lý tiếp (`main.py:99-101`). Event được validate bằng `validate_strategy_match(event)` (`main.py:103-107`).

### 1.2 build_order_command chỉ build command intent

`build_order_command(match_event)` nằm ở `services/aureus-trader/order_builder.py:40-91`. Hàm này:

- Lấy `data = match_event["data"]` tại `order_builder.py:46`.
- Tạo `cmd_id = generate_cmd_id(match_event)` tại `order_builder.py:47`.
- Map direction, SL, TP từ field canonical/fallback (`order_builder.py:49-52`).
- Tạo dict `command` với `type="OPEN_ORDER"`, `symbol`, `cmd_id`, `direction`, `order_type`, `volume`, `price`, `sl`, `tp`, `magic`, `comment` tại `order_builder.py:58-70`.
- Optional forward `trace_id` nếu có tại `order_builder.py:72-75`.
- Optional forward `tp_rr_ratio`, `size_mode`, `risk_amount` tại `order_builder.py:76-89`.

Điểm quan trọng: `build_order_command()` chỉ tạo Python dict. Không có Redis publish, không có socket, không có MT5 call trong hàm này.

### 1.3 main.py gắn strategy_event, check idempotency, rồi enqueue

Sau khi build command, `main.py` gắn original event vào command để giữ context nội bộ Python:

- `order_cmd = build_order_command(event)` tại `main.py:110`.
- `order_cmd["strategy_event"] = event` tại `main.py:111`.

Sau đó idempotency check theo `cmd_id`:

- `is_new = await dedup.check_and_mark(order_cmd["cmd_id"])` tại `main.py:114`.
- Nếu duplicate thì skip tại `main.py:115-117`.

Nếu là order mới, trader gọi:

- `enqueued = await dispatcher.enqueue_order(order_cmd)` tại `main.py:120`.

### 1.4 enqueue_order chỉ push vào Redis list

`OrderDispatcher.enqueue_order()` nằm ở `services/aureus-trader/dispatcher.py:65-79`:

- Đọc queue size bằng `await self.redis.llen(ORDER_QUEUE_KEY)` tại `dispatcher.py:70`.
- Nếu vượt `max_queue_size`, reject tại `dispatcher.py:71-76`.
- Nếu còn chỗ, push JSON vào Redis list bằng `await self.redis.rpush(ORDER_QUEUE_KEY, json.dumps(order_cmd))` tại `dispatcher.py:78`.

Vì vậy `enqueue_order()` chưa publish sang MT5. Nó chỉ đưa order vào hàng đợi Redis list.

### 1.5 dispatch_loop lấy queue và gọi dispatch_order

`OrderDispatcher.dispatch_loop()` nằm ở `dispatcher.py:81-99`:

- Loop khi `_running` true (`dispatcher.py:86`).
- `raw = await self.redis.lpop(ORDER_QUEUE_KEY)` tại `dispatcher.py:87`.
- Nếu queue rỗng thì sleep 0.5s (`dispatcher.py:88-90`).
- Nếu có item, parse JSON (`dispatcher.py:93`) rồi `await self.dispatch_order(order)` tại `dispatcher.py:94`.

Điểm quyết định concurrency nằm ở dòng `await self.dispatch_order(order)`: loop chờ toàn bộ lifecycle dispatch của order hiện tại xong mới quay lại `lpop` order tiếp theo.

### 1.6 dispatch_order publish payload sang commands channel và chờ ACK/result

`OrderDispatcher.dispatch_order()` nằm ở `dispatcher.py:100-184`:

- Lấy `cmd_id = order["cmd_id"]` tại `dispatcher.py:106`.
- Tạo `mt5_order = self._extract_mt5_execution_payload(order)` tại `dispatcher.py:108`.
- Vòng retry `for attempt in range(max_retries + 1)` tại `dispatcher.py:110`.
- Publish payload lên Redis `COMMANDS_CHANNEL` bằng `await self.redis.publish(COMMANDS_CHANNEL, json.dumps(mt5_order))` tại `dispatcher.py:112`.
- Chờ ACK/NACK bằng `_wait_for_response(cmd_id, self.config.ack_timeout)` tại `dispatcher.py:117-120`.
- Nếu ACK, tiếp tục chờ final result bằng `_wait_for_response(cmd_id, self.config.result_timeout)` tại `dispatcher.py:146-150`.

Payload gửi sang MT5 được lọc bởi `_extract_mt5_execution_payload()` tại `dispatcher.py:301-324`. Allowed fields gồm `type`, `symbol`, `cmd_id`, `direction`, `order_type`, `volume`, `price`, `sl`, `tp`, `magic`, `comment`, `tp_rr_ratio`, `size_mode`, `risk_amount`, `trace_id` (`dispatcher.py:303-319`). `strategy_event` không được gửi sang MT5, chỉ phục vụ journal/correlation nội bộ sau result.

### 1.7 MT5 provider nhận command từ gateway/socket

Trong `mql5/AureusProvider_v2.mq5`, EA/provider không subscribe Redis trực tiếp. Nó nhận command qua socket gateway:

- `OnTimer()` gọi `ProcessIncomingCommands()` tại `AureusProvider_v2.mq5:2721-2724`.
- `ProcessIncomingCommands()` kiểm tra socket connected (`AureusProvider_v2.mq5:2522-2523`), đọc raw JSON bằng `g_socket.Receive()` tại `AureusProvider_v2.mq5:2525`.
- Nếu raw chứa `"OPEN_ORDER"`, gọi `ExecuteOpenOrder(raw)` tại `AureusProvider_v2.mq5:2533-2538`.

Như vậy đường đi thực tế là:

`STRATEGY_MATCH pub/sub -> run_trader -> build_order_command -> enqueue_order/rpush Redis list -> dispatch_loop/lpop -> dispatch_order/publish COMMANDS_CHANNEL -> gateway/socket -> MT5 ProcessIncomingCommands -> ExecuteOpenOrder`.

### 1.8 ExecuteOpenOrder ACK/NACK/result

`ExecuteOpenOrder()` bắt đầu tại `AureusProvider_v2.mq5:1837` và parse các field command tại `AureusProvider_v2.mq5:1840-1854`.

Các reject sớm dùng NACK:

- Missing required fields: `SendNACK(..., "INVALID_COMMAND")` tại `AureusProvider_v2.mq5:1862-1867`.
- Duplicate `cmd_id`: `SendNACK(cmdId, "DUPLICATE")` tại `AureusProvider_v2.mq5:1869-1874`.
- Duplicate active strategy order theo symbol/magic/side: `SendNACK(cmdId, "STRATEGY_ORDER_EXISTS")` tại `AureusProvider_v2.mq5:1884-1904` và `1907-1935`.
- AutoTrading disabled: `SendNACK(cmdId, "TRADE_DISABLED")` tại `AureusProvider_v2.mq5:1938-1943`.

Nếu command được accept, provider gửi ACK trước khi build/send trade request:

- `SendACK(cmdId)` tại `AureusProvider_v2.mq5:1946-1947`.
- `RecordCmdId(cmdId)` tại `AureusProvider_v2.mq5:1947-1948`.

Sau đó provider build `MqlTradeRequest`, `OrderCheck`, `OrderSend`. Nếu fail thì `PushOrderFailed(...)`:

- `OrderCheck` fail: `PushOrderFailed(...)` tại `AureusProvider_v2.mq5:2113-2120`.
- `OrderSend` fail: `PushOrderFailed(...)` tại `AureusProvider_v2.mq5:2123-2130`.
- Retcode không DONE: `PushOrderFailed(...)` tại `AureusProvider_v2.mq5:2288-2295`.

Nếu success thì provider push terminal event:

- Market success gọi `PushOrderOpened(...)` tại `AureusProvider_v2.mq5:2225-2231`, `2257-2263`, hoặc `2267-2273` tùy path finalize/modify.
- Non-market success gọi `PushOrderOpened(...)` tại `AureusProvider_v2.mq5:2277-2285`.

`SendACK()` tạo JSON `{"type":"ACK","cmd_id":...}` và gửi qua socket tại `AureusProvider_v2.mq5:850-858`. `PushOrderOpened()` tạo `ORDER_OPENED` event tại `AureusProvider_v2.mq5:972-984`. `PushOrderFailed()` tạo `ORDER_FAILED` event tại `AureusProvider_v2.mq5:990-1000`.

## 2. Nhiều order đến cùng lúc: tuần tự hay concurrent?

### 2.1 Enqueue có thể nhận nhiều event liên tiếp

`run_trader()` xử lý Redis pub/sub event trong `async for message in pubsub.listen()` (`main.py:91-93`). Mỗi `STRATEGY_MATCH` hợp lệ được build và enqueue bằng `await dispatcher.enqueue_order(order_cmd)` (`main.py:109-120`). Vì `enqueue_order()` chỉ `llen` rồi `rpush`, nhiều order có thể được đẩy vào Redis list nhanh, theo thứ tự arrival tại trader.

### 2.2 Dispatch outbound trong một dispatcher instance là tuần tự

Bằng chứng chính nằm ở `dispatcher.py:86-94`:

```text
while self._running:
    raw = await self.redis.lpop(ORDER_QUEUE_KEY)
    ...
    order = json.loads(raw)
    await self.dispatch_order(order)
```

Vì `await self.dispatch_order(order)` nằm trực tiếp trong loop và không dùng `asyncio.create_task()` cho từng order, một instance dispatcher chỉ xử lý một order outbound tại một thời điểm.

Điều này khác với `event_listener()`: listener được start bằng task riêng ở `main.py:81`, nên nó có thể chạy đồng thời để nhận ACK/NACK/result. Nhưng concurrency đó là concurrency cho event resolution, không phải concurrency cho gửi nhiều order sang MT5.

### 2.3 Không thấy worker pool hoặc per-symbol queue trong dispatcher hiện tại

Trong `OrderDispatcher`, không có worker pool, semaphore, per-symbol queue, hoặc `create_task(self.dispatch_order(...))`. Queue key là global `ORDER_QUEUE_KEY`; `dispatch_loop()` dùng một `lpop` và một `await dispatch_order` tuần tự. Do đó kết luận đúng trong phạm vi source hiện tại là:

- Concurrent ở tầng nhận signal/enqueue: có thể có nhiều event được queue.
- Sequential ở tầng outbound dispatch trong một dispatcher instance: gửi/chờ từng order một.
- Nếu chạy nhiều instance `aureus-trader` cùng dùng chung Redis list thì có thể có concurrency giữa instance, nhưng source/plan hiện tại không chứng minh deployment đang chạy nhiều dispatcher. Báo cáo này kết luận theo một instance đang thấy trong `run_trader()`.

## 3. Một order lỗi/retry/timeout có block order khác không?

### 3.1 Có, block ở dispatch_loop queue phía sau

Vì `dispatch_loop()` await toàn bộ `dispatch_order()`, bất cứ delay nào trong `dispatch_order()` đều giữ loop không quay lại `lpop` order tiếp theo.

Các delay/blocking path trong `dispatch_order()`:

1. Chờ ACK/NACK: `_wait_for_response(cmd_id, self.config.ack_timeout)` tại `dispatcher.py:117-120`.
2. ACK timeout: nếu timeout, log warning rồi nếu còn retry thì `await asyncio.sleep(2**attempt)` tại `dispatcher.py:122-129`.
3. Retryable NACK: `await asyncio.sleep(2**attempt)` tại `dispatcher.py:134-141`.
4. Sau ACK, chờ result: `_wait_for_response(cmd_id, self.config.result_timeout)` tại `dispatcher.py:146-150`.
5. Result timeout: gọi `_handle_max_retries(order)` rồi return tại `dispatcher.py:152-155`.
6. Retryable final result: `await asyncio.sleep(2**attempt)` tại `dispatcher.py:171-177`.

Trong các khoảng chờ này, `dispatch_loop()` chưa xử lý order tiếp theo. Vì vậy một order bị ACK timeout/retry/backoff/result timeout là head-of-line blocker cho các order đứng sau trong Redis list.

### 3.2 event_listener không bị block hoàn toàn

`event_listener()` được start riêng tại `main.py:81` và subscribe `EVENTS_CHANNEL` trong `dispatcher.py:186-190`. Nó lắng nghe pub/sub message (`dispatcher.py:193`) và nếu event có `cmd_id` khớp pending future thì pop future và `future.set_result(event)` tại `dispatcher.py:220-224`.

Vì listener là task riêng, trong lúc `dispatch_order()` đang chờ `_wait_for_response()`, listener vẫn có thể nhận ACK/NACK/ORDER_OPENED/ORDER_FAILED và resolve future. Đây là lý do ACK/result có thể unblock order hiện tại.

Nhưng listener chỉ resolve future cho order đang pending; nó không tự lấy order kế tiếp từ Redis list. Lệnh kế tiếp vẫn phải chờ `dispatch_loop()` quay lại sau khi `dispatch_order()` của order hiện tại return.

### 3.3 Thời gian kẹt xấu nhất theo config hiện tại

`260424-sbg-REPORT.md` ghi nhận default config liên quan:

- `ack_timeout=5.0`.
- `result_timeout=30.0`.
- `max_retries=3`.

Với ACK timeout liên tiếp, mỗi attempt chờ ACK timeout rồi backoff. Source `dispatcher.py:110-129` dùng `range(max_retries + 1)`, tức nếu `max_retries=3` sẽ có 4 publish attempts. Backoff được sleep khi `attempt < max_retries`: `2**0 + 2**1 + 2**2 = 1 + 2 + 4 = 7s`. Tổng worst-case ACK-missing gần đúng: `4 * ack_timeout + 7s = 4*5 + 7 = 27s` trước `_handle_max_retries()`.

Với ACK thành công nhưng không có result, order giữ loop khoảng `ack latency + result_timeout`, tức mặc định khoảng 30s sau ACK trước khi return (`dispatcher.py:146-155`).

Với retryable NACK hoặc retryable `ORDER_FAILED`, mỗi retry cũng sleep backoff (`dispatcher.py:134-141`, `171-177`). Nếu các attempt lặp lại, queue phía sau bị delay theo tổng thời gian chờ ACK/result + backoff của order đầu hàng.

### 3.4 Previous incident 260424-sbg là bằng chứng thực tế

`260424-sbg-REPORT.md` mô tả timeline có hai order được queued gần như cùng lúc:

- `ord-8d74d544f5b2` queued lúc `13:20:01,636`.
- `ord-c52e9b1f48eb` queued lúc `13:20:01,638`.
- Order A result timeout lúc `13:20:30,842`.
- Order B sau đó mới ghi nhận ACK timeout attempt 1 lúc `13:20:35,851`, attempt 2 lúc `13:20:41,861`, attempt 3 lúc `13:20:47,845`, rồi `NACK:DUPLICATE` lúc `13:20:51,903`.

Timeline này phù hợp với cơ chế sequential dispatch: order B đã queue sau A nhưng outbound processing của B bị delay cho tới khi A result timeout/return. Báo cáo `260424-sbg` cũng kết luận sự cố là timeout/event delivery mismatch và khuyến nghị correlation log theo `cmd_id`.

## 4. Rủi ro

### 4.1 Head-of-line blocking / queue latency amplification

Một order gặp ACK timeout hoặc result timeout có thể giữ `dispatch_loop()` hàng chục giây. Nếu cùng lúc có nhiều order tốt phía sau, chúng vẫn chờ trong Redis list dù MT5 có thể sẵn sàng xử lý. Đây là rủi ro DoS nội bộ ở boundary `aureus-trader -> Redis command channel -> MT5 provider`.

### 4.2 Retry cùng cmd_id có thể tạo NACK DUPLICATE sau ACK bị lost

`260424-sbg-REPORT.md` đã ghi nhận pattern: ACK bị lost/đến trễ, trader retry cùng `cmd_id`, provider đã `RecordCmdId(cmdId)` sau ACK nên lần sau trả `NACK:DUPLICATE`. Source hiện tại cũng thể hiện provider `SendACK(cmdId)` rồi `RecordCmdId(cmdId)` tại `AureusProvider_v2.mq5:1946-1948`, và duplicate path `SendNACK(cmdId, "DUPLICATE")` tại `AureusProvider_v2.mq5:1869-1874`.

Rủi ro là business log có thể nhìn như order reject duplicate, trong khi bản chất là ACK/result delivery/correlation issue.

### 4.3 Result timeout sau ACK gây mơ hồ trạng thái thực thi

Provider ACK trước `OrderCheck`/`OrderSend` (`AureusProvider_v2.mq5:1946-1948`). Nếu trader nhận ACK nhưng không nhận `ORDER_OPENED`/`ORDER_FAILED` trong `result_timeout`, dispatcher gọi `_handle_max_retries()` và publish `ORDER_REJECTED` nội bộ (`dispatcher.py:152-155`, `365-386`). Tuy nhiên phía MT5 có thể đã xử lý hoặc event bị rơi/chậm. Đây là trạng thái ambiguous: trader nghĩ max retries/timeout, MT5 có thể đã có side effect.

### 4.4 Silent return khi symbol không nằm trong InpSymbols

Trong `ExecuteOpenOrder()`, nếu `FindContextIndex(symbol) < 0`, code hiện tại return mà không gửi NACK vì `SendNACK` bị comment (`AureusProvider_v2.mq5:1876-1882`). Với order như vậy, trader sẽ chờ ACK tới timeout, retry, và block queue phía sau theo cơ chế trên. Đây là một risk cụ thể làm tăng head-of-line blocking.

### 4.5 MT5 provider xử lý command trong OnTimer đơn luồng

Provider gọi `ProcessIncomingCommands()` trong `OnTimer()` (`AureusProvider_v2.mq5:2721-2724`). Trong MQL5 EA, event handler chạy tuần tự trong EA thread. `ExecuteOpenOrder()` thực hiện parse, validate, `OrderCheck`, `OrderSend`, optional modify/final event trong cùng call. Vì vậy phía MT5 provider cũng không thể coi là worker pool concurrent.

### 4.6 Limit order lifecycle vẫn có semantic caveat

`260429-897-REPORT.md` chỉ ra với limit/pending order, provider từng dùng `ORDER_OPENED` cho pending accepted, trong khi position ticket thật chỉ có khi pending fill sau này. Source hiện tại ở `AureusProvider_v2.mq5:2277-2285` vẫn có non-market success path gọi `PushOrderOpened(...)` với `result.order`. Điều này không trực tiếp thay đổi câu trả lời về queue blocking, nhưng làm result semantics phức tạp hơn: dispatcher chỉ thấy final event theo `cmd_id`, còn lifecycle position thật có thể chưa hoàn tất.

## 5. Recommended next steps

### 5.1 Ngắn hạn: tăng observability theo cmd_id

Ưu tiên thêm correlation logging/metrics theo `cmd_id` cho các mốc:

- Trader enqueue: `cmd_id`, queue size, symbol, direction.
- Dispatcher publish: `cmd_id`, attempt, timestamp, payload type.
- ACK/NACK received: `cmd_id`, latency từ publish, reason.
- Result received: `cmd_id`, latency từ ACK, result type/ticket/retcode.
- Timeout/retry/backoff: `cmd_id`, attempt, elapsed, queue age.
- Provider receive/ACK/NACK/OrderCheck/OrderSend/PushOrderOpened/PushOrderFailed: cùng `cmd_id`.

Đây là mitigation trực tiếp cho threat `T-260430-tqm-02` trong plan: correlation logging/metrics theo `cmd_id`.

### 5.2 Ngắn hạn: xử lý silent no-response path

Path symbol không thuộc `InpSymbols` đang return không NACK (`AureusProvider_v2.mq5:1876-1882`). Nên cân nhắc biến nó thành NACK rõ ràng, ví dụ `SYMBOL_NOT_ALLOWED`, để trader không chờ ACK timeout và không block queue vô ích. Đây là hardening nhỏ nhưng cần implement/test riêng, không nằm trong report-only task này.

### 5.3 Ngắn hạn: phân loại timeout outcome rõ hơn

Khi result timeout sau ACK, không nên coi đơn giản như business reject. Nên phân biệt:

- `ACK_TIMEOUT_NO_PROVIDER_RESPONSE`.
- `RESULT_TIMEOUT_AFTER_ACK`.
- `NACK_DUPLICATE_AFTER_ACK_TIMEOUT`.
- `MT5_REJECT_NON_RETRYABLE`.

Điều này giúp vận hành biết order có thể đã có side effect ở MT5 hay chưa.

### 5.4 Trung hạn: tránh head-of-line blocking

Có vài hướng, cần design riêng trước khi implement:

1. Worker pool dispatcher với giới hạn concurrency nhỏ, ví dụ 2-4 order in-flight, nhưng phải đảm bảo MT5/provider/gateway chịu được và idempotency/correlation đúng.
2. Per-symbol hoặc per-strategy queue để một symbol/strategy lỗi không block toàn hệ thống.
3. Tách publish/ACK wait/result wait thành state machine: dispatch loop chỉ publish và register pending, còn result được xử lý async. Cách này giảm blocking nhưng thay đổi kiến trúc nhiều hơn.
4. Giữ sequential dispatch nhưng thêm queue age/timeout circuit breaker để detect và cảnh báo khi order đầu hàng giữ queue quá lâu.

Vì đây là thay đổi concurrency/architecture, không nên sửa vội trong quick report. Cần task riêng có test mô phỏng ACK timeout/result timeout/nhiều order.

### 5.5 Trung hạn: reconcile trạng thái MT5 khi timeout

Với result timeout sau ACK, nên có cơ chế query/reconcile theo `cmd_id`, `magic`, `symbol`, `comment/trace_id` hoặc pending order id để xác nhận MT5 đã mở/đặt/thất bại. Nếu không, timeout có thể tạo trạng thái journal/trader sai so với terminal.

### 5.6 Liên quan limit lifecycle

Dựa trên `260429-897`, nếu tiếp tục dùng limit/pending order, nên tách event `ORDER_PENDING_PLACED` và `ORDER_FILLED`/position opened rõ ràng, tránh dùng `ORDER_OPENED` cho pending accepted. Dispatcher hiện đã accept `ORDER_PENDING_PLACED`/`ORDER_FILLED` trong success types tại `dispatcher.py:157-168`, nhưng provider path cần được kiểm tra theo source hiện hành và test riêng.

## Evidence

| Chủ đề | File/function/line | Bằng chứng |
|---|---|---|
| Trader start dispatcher loop | `services/aureus-trader/main.py:74-82` | Khởi tạo `OrderDispatcher`, start `dispatch_loop()` và `event_listener()` bằng `asyncio.create_task`. |
| Strategy event processing | `services/aureus-trader/main.py:91-120` | Subscribe pub/sub, filter `STRATEGY_MATCH`, validate, `build_order_command(event)`, gắn `strategy_event`, idempotency, `dispatcher.enqueue_order(order_cmd)`. |
| Command builder | `services/aureus-trader/order_builder.py:40-91` | Build dict `OPEN_ORDER` với `cmd_id`, symbol, direction, order_type, volume, price, SL/TP, magic, comment, optional trace/risk fields. |
| Enqueue chỉ Redis list | `services/aureus-trader/dispatcher.py:65-79` | `llen` check max queue, `rpush(ORDER_QUEUE_KEY, json.dumps(order_cmd))`. |
| Dispatch sequential | `services/aureus-trader/dispatcher.py:81-99` | `lpop` rồi `await self.dispatch_order(order)` trong cùng loop. |
| Publish to MT5 command channel | `services/aureus-trader/dispatcher.py:100-120` | `_extract_mt5_execution_payload`, `redis.publish(COMMANDS_CHANNEL, ...)`, chờ ACK/NACK. |
| Wait result after ACK | `services/aureus-trader/dispatcher.py:146-181` | Sau ACK chờ final result, xử lý success, retryable final, rejection. |
| Pending future resolution | `services/aureus-trader/dispatcher.py:186-224` | `event_listener()` subscribe `EVENTS_CHANNEL`, match `cmd_id`, `future.set_result(event)`. |
| Timeout cleanup | `services/aureus-trader/dispatcher.py:326-338` | `_wait_for_response()` tạo future, `asyncio.wait_for`, timeout thì pop pending và return None. |
| Payload allowlist | `services/aureus-trader/dispatcher.py:301-324` | Chỉ gửi fields cần thiết sang MT5, có `trace_id`, không gửi `strategy_event`. |
| Provider receive command | `mql5/AureusProvider_v2.mq5:2520-2538` | `ProcessIncomingCommands()` đọc `g_socket.Receive()`, detect `OPEN_ORDER`, gọi `ExecuteOpenOrder(raw)`. |
| Provider timer | `mql5/AureusProvider_v2.mq5:2721-2724` | `OnTimer()` gọi `ProcessIncomingCommands()`. |
| Provider parse command | `mql5/AureusProvider_v2.mq5:1837-1854` | `ExecuteOpenOrder()` parse `cmd_id`, `symbol`, `direction`, `order_type`, `volume`, `price`, SL/TP, magic, comment, trace_id. |
| Provider NACK invalid/duplicate | `mql5/AureusProvider_v2.mq5:1862-1874` | Missing fields -> `INVALID_COMMAND`, duplicate -> `DUPLICATE`. |
| Provider duplicate strategy NACK | `mql5/AureusProvider_v2.mq5:1884-1935` | Existing position/order same symbol/magic/side -> `STRATEGY_ORDER_EXISTS`. |
| Provider ACK before OrderSend | `mql5/AureusProvider_v2.mq5:1946-1948` | `SendACK(cmdId)` và `RecordCmdId(cmdId)` trước build/check/send request. |
| Provider result failed | `mql5/AureusProvider_v2.mq5:2113-2130`, `2288-2295` | `OrderCheck`/`OrderSend`/retcode fail -> `PushOrderFailed`. |
| Provider result opened | `mql5/AureusProvider_v2.mq5:2225-2273`, `2277-2285` | Success paths -> `PushOrderOpened`. |
| ACK JSON | `mql5/AureusProvider_v2.mq5:850-858` | `SendACK()` sends `{"type":"ACK","cmd_id":...}`. |
| NACK JSON | `mql5/AureusProvider_v2.mq5:864-872` | `SendNACK()` sends `{"type":"NACK","cmd_id":...,"reason":...}`. |
| ORDER_OPENED JSON | `mql5/AureusProvider_v2.mq5:972-984` | `PushOrderOpened()` sends `ORDER_OPENED` with cmd_id/ticket/symbol/direction/order_type. |
| ORDER_FAILED JSON | `mql5/AureusProvider_v2.mq5:990-1000` | `PushOrderFailed()` sends `ORDER_FAILED` with reason/retcode/entry/ask/bid. |
| Previous ACK/result timeout | `.planning/quick/260424-sbg.../260424-sbg-REPORT.md:16-24` | Ghi nhận ACK timeout, result timeout, retry cùng `cmd_id`, `NACK:DUPLICATE` non-retryable. |
| Previous sequential symptom | `.planning/quick/260424-sbg.../260424-sbg-REPORT.md:41-55` | Hai order queued cùng lúc, order sau bắt đầu timeout sau khi order trước result timeout. |
| Limit lifecycle caveat | `.planning/quick/260429-897.../260429-897-REPORT.md:59-75` | Limit/pending accepted không đồng nghĩa position opened; `ORDER_OPENED` cho pending có semantic rủi ro. |

## Trả lời trực tiếp 4 câu hỏi

1. **Sau `build_order_command` và `dispatcher.enqueue_order`, order đi sang MT5 như thế nào?**  
   `build_order_command` tạo dict `OPEN_ORDER`; `enqueue_order` push dict đó vào Redis list; `dispatch_loop` `lpop`; `dispatch_order` publish payload lên Redis `COMMANDS_CHANNEL`; gateway/socket đưa raw JSON tới MT5 provider; `ProcessIncomingCommands` nhận và gọi `ExecuteOpenOrder`; provider gửi ACK/NACK rồi `ORDER_OPENED`/`ORDER_FAILED` result.

2. **Nhiều order cùng lúc xử lý tuần tự hay concurrent?**  
   Enqueue có thể nhận nhiều order liên tiếp, nhưng outbound dispatch trong một `OrderDispatcher` là tuần tự vì `dispatch_loop` dùng `lpop` rồi `await dispatch_order(order)` cho từng order. `event_listener` concurrent nhưng chỉ để nhận/resolve ACK/result.

3. **Nếu một order retry/timeout/error thì order khác có bị kẹt không?**  
   Có, order phía sau trong Redis queue bị kẹt ở dispatch layer cho tới khi order hiện tại return khỏi `dispatch_order`. ACK/result listener vẫn chạy, nhưng không lấy order kế tiếp thay dispatch loop.

4. **Rủi ro và next steps?**  
   Rủi ro chính: head-of-line blocking, ambiguous state sau ACK/result timeout, NACK duplicate do retry cùng `cmd_id`, silent no-response path khi symbol không allowed, và lifecycle semantic phức tạp với limit order. Next steps: bổ sung correlation log/metrics theo `cmd_id`, NACK rõ các reject path, phân loại timeout outcome, cân nhắc worker pool/per-symbol queue/state-machine dispatch sau khi có test concurrency, và reconcile MT5 state khi result timeout.
