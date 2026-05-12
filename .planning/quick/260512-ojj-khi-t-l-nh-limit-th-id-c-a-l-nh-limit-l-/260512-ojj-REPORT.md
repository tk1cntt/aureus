# Report 260512-ojj: Cơ chế map limit pending order id sang position ticket

## Tóm tắt

Code hiện tại đã có cơ chế map lệnh limit từ `pending_order_id` sang `ticket` thật sau khi lệnh khớp.

Luồng chính:

- Khi đặt limit thành công, journal vẫn giữ `status = TRIGGERED`, `ticket = NULL`, và lưu MT5 pending order id vào `pending_order_id`.
- Khi MT5 báo pending order đã khớp qua `DEAL_ENTRY_IN`, provider gửi event `ORDER_FILLED` có đủ `pending_order_id`, `position_ticket`, `deal_ticket`.
- Trader nhận `ORDER_FILLED`, normalize `position_ticket` thành `ticket` và `position_id`, rồi update journal thành `EXECUTED`.
- `deal_ticket` được lưu vào `entry_deal_ticket` để audit deal mở vị thế.

Kết luận ngắn: cơ chế mapping đã có. Nếu DB vẫn không update, cần kiểm tra event thực tế có đủ `trace_id` hoặc fallback key hợp lệ, có `position_ticket`, `open_price`, `time`, và provider có phát `ORDER_FILLED` hay không.

## Chứng cứ từ code

### 1. Pending order placed lưu `pending_order_id`

File: `services/aureus-trader/journal.py`

Hàm: `TradeJournalManager.on_order_pending_placed`

Bằng chứng:

- Lấy `pending_order_id = event.get("pending_order_id") or event.get("order")`.
- Bắt buộc có `trace_id` hoặc `cmd_id`.
- Bắt buộc có `pending_order_id`.
- Update `aureus_trade_journal` khi `status = 'TRIGGERED'`.
- Set các field: `pending_order_id`, `cmd_id`, `mt5_comment`, `entry_price`, `sl_initial`, `tp_initial`.
- Điều kiện match: `trace_id = $7` hoặc khi thiếu trace_id thì `cmd_id = $2`.

Ý nghĩa: lúc limit mới được đặt, DB chưa có position ticket thật. DB chỉ lưu id pending order ở `pending_order_id`; `ticket` vẫn chưa set.

### 2. MT5 provider phát `ORDER_FILLED` khi pending order khớp

File: `mql5/AureusProvider_v2.mq5`

Hàm: `PushOrderFilled`

Bằng chứng event JSON:

- `type`: `ORDER_FILLED`
- `deal_ticket`: deal mở vị thế
- `position_ticket`: ticket position thật sau khớp
- `pending_order_id`: ticket của pending order ban đầu
- `direction`, `volume`, `open_price`, `sl`, `tp`, `magic`, `strategy_name`, `trace_id`, `comment`, `time`, `t`

Hàm `OnTradeTransaction` phát hiện pending fill bằng:

- `DEAL_ENTRY_IN`
- lấy `orderTicket = trans.order`
- kiểm tra `HistoryOrderGetInteger(orderTicket, ORDER_TYPE)` thuộc các loại pending: `BUY_LIMIT`, `SELL_LIMIT`, `BUY_STOP`, `SELL_STOP`, `BUY_STOP_LIMIT`, `SELL_STOP_LIMIT`
- lấy `ticket = trans.position`
- gọi `PushOrderFilled(symbol, deal, ticket, orderTicket, ...)`

Ý nghĩa: MT5 chính là nơi biết pending order id và position ticket mới. Event `ORDER_FILLED` là cầu nối giữa 2 id này.

### 3. Dispatcher đưa `ORDER_FILLED` vào journal

File: `services/aureus-trader/dispatcher.py`

Hàm: `MT5Dispatcher.event_listener`

Bằng chứng:

- Khi event type là `ORDER_FILLED`, nếu có journal thì normalize `time` bằng `_normalize_mt5_unix_time`.
- Sau đó chạy `asyncio.create_task(self.journal.on_order_filled(event))`.
- Task journal không block event resolution.

Hàm dispatch order cũng xử lý final success:

- Nếu final type thuộc `ORDER_OPENED`, `ORDER_PENDING_PLACED`, `ORDER_FILLED`, state thành `FINAL_SUCCESS`.
- Với `ORDER_PENDING_PLACED`: gọi `journal.on_order_pending_placed(final)`.
- Với `ORDER_FILLED`: gọi `journal.on_order_filled(final)`.
- Với market/open bình thường: gọi `journal.on_order_opened(final)`.

Ý nghĩa: `ORDER_FILLED` có 2 đường vào journal: response trực tiếp của order dispatch và realtime Redis event listener.

### 4. Journal normalize `position_ticket` thành `ticket` và `position_id`

File: `services/aureus-trader/journal.py`

Hàm: `TradeJournalManager.on_order_filled`

Bằng chứng:

- Nếu event chưa có `ticket` nhưng có `position_ticket`, set `event["ticket"] = event.get("position_ticket")`.
- Nếu event chưa có `position_id` nhưng có `position_ticket`, set `event["position_id"] = event.get("position_ticket")`.
- Sau đó gọi `return await self.on_order_opened(event)`.

Ý nghĩa: journal coi `ORDER_FILLED` như một `ORDER_OPENED` sau khi đã đổi `position_ticket` thành `ticket` thật.

### 5. `on_order_opened` update journal thành EXECUTED

File: `services/aureus-trader/journal.py`

Hàm: `TradeJournalManager.on_order_opened`

Bằng chứng update:

- `status = 'EXECUTED'`
- `ticket = $1`
- `entry_price = $2`
- `entry_time = $3`
- `position_id = $4`
- `lot_size = $5`
- `sl_initial = $6`
- `tp_initial = $7`
- `pending_order_id = COALESCE($9, pending_order_id)`
- `entry_deal_ticket = COALESCE($10, entry_deal_ticket)`
- `cmd_id = COALESCE($11, cmd_id)`
- `mt5_comment = COALESCE($12, mt5_comment)`

Điều kiện match row:

- Chỉ update row `status = 'TRIGGERED'`.
- Code hiện tại bắt buộc event có `trace_id` trước khi chạy SQL update.
- SQL có điều kiện `pending_order_id`/`cmd_id`, nhưng các nhánh này không giúp được khi `trace_id` bị thiếu vì `on_order_opened` return `False` sớm.
- Vì vậy cơ chế thực tế hiện nay: `trace_id` là key bắt buộc; `pending_order_id`/`cmd_id` chỉ là điều kiện phụ trong SQL khi event vẫn có `trace_id`.

Ý nghĩa: mapping chính nằm ở update này. `position_ticket` trở thành `ticket` và `position_id` mới. `pending_order_id` được lưu để audit/nối logic, nhưng chưa phải fallback độc lập nếu `ORDER_FILLED` thiếu `trace_id`.

## Lifecycle hiện tại

1. Strategy match tạo journal row ban đầu.
   - Event: `STRATEGY_MATCH`.
   - Hàm: `journal.py::on_strategy_match`.
   - DB: tạo row trong `aureus_trade_journal` với `status = TRIGGERED`.

2. Limit order được MT5 accept.
   - Event: `ORDER_PENDING_PLACED`.
   - Hàm nhận: `dispatcher.py` gọi `journal.py::on_order_pending_placed`.
   - DB: set `pending_order_id`, `cmd_id`, `mt5_comment`, giá limit/SL/TP nếu có.
   - DB vẫn giữ `ticket = NULL`, `status = TRIGGERED`.

3. Limit order khớp thành position.
   - Nguồn: `mql5/AureusProvider_v2.mq5::OnTradeTransaction`.
   - Điều kiện: deal `DEAL_ENTRY_IN` và history order type là pending.
   - Provider lấy:
     - pending id từ `trans.order`
     - position id từ `trans.position`
     - deal id từ `trans.deal`

4. Provider gửi event fill.
   - Hàm: `AureusProvider_v2.mq5::PushOrderFilled`.
   - Event: `ORDER_FILLED`.
   - Payload chính: `pending_order_id`, `position_ticket`, `deal_ticket`, `trace_id`, `open_price`, `time`.

5. Trader dispatcher nhận event.
   - Hàm: `dispatcher.py::event_listener`.
   - Gọi async: `journal.on_order_filled(event)`.

6. Journal normalize ticket.
   - Hàm: `journal.py::on_order_filled`.
   - `position_ticket` → `ticket`.
   - `position_ticket` → `position_id`.

7. Journal update DB.
   - Hàm: `journal.py::on_order_opened`.
   - Bắt buộc có `trace_id`; nếu thiếu thì return `False` trước SQL update.
   - SQL update row `TRIGGERED` theo `trace_id`, kèm điều kiện phụ `pending_order_id`/`cmd_id` nếu có.
   - Set `status = EXECUTED`, `ticket = position_ticket`, `position_id = position_ticket`, `entry_deal_ticket = deal_ticket`.

## Bảng mapping field

| Field | Nguồn | Lưu/đổi sang | Ý nghĩa |
|---|---|---|---|
| `pending_order_id` | MT5 pending order ticket, `trans.order` | `aureus_trade_journal.pending_order_id` | Id của lệnh chờ ban đầu |
| `position_ticket` | MT5 position ticket, `trans.position` | `ticket`, `position_id` qua `on_order_filled` | Ticket thật sau khi pending khớp |
| `deal_ticket` | MT5 deal ticket, `trans.deal` | `entry_deal_ticket` | Audit link tới deal mở vị thế |
| `ticket` | Normalized từ `position_ticket` | `aureus_trade_journal.ticket` | Ticket chính để close/update về sau |
| `position_id` | Normalized từ `position_ticket` | `aureus_trade_journal.position_id` | Id position trong journal |
| `cmd_id` | Command/order dispatch | `aureus_trade_journal.cmd_id` | Fallback match khi thiếu `trace_id` |
| `trace_id` | Strategy/journal trace | Điều kiện update chính | Key tốt nhất để nối lifecycle |
| `entry_deal_ticket` | Từ `deal_ticket` | `aureus_trade_journal.entry_deal_ticket` | Bằng chứng deal đã mở position |

## Điều kiện journal update đúng

Journal update đúng khi các điều kiện này cùng đúng:

- Row journal đang ở `status = TRIGGERED`.
- Event fill có `trace_id` khớp row journal. Đây là điều kiện bắt buộc trong code hiện tại.
- Event có `position_ticket` để normalize thành `ticket`.
- Event có `open_price` hoặc `price`, và giá này lớn hơn 0.
- Event có `time` hoặc `open_time` hợp lệ.
- Provider thực sự gửi `ORDER_FILLED` khi pending order khớp.
- Dispatcher chạy và gọi được `journal.on_order_filled`.
- `pending_order_id`/`cmd_id` có thể giúp SQL match chặt hơn, nhưng không thay thế được `trace_id` nếu event thiếu `trace_id`.

## Case có thể fail

1. Thiếu `trace_id` trong `ORDER_FILLED`.
   - `on_order_opened` return `False` ngay khi thiếu `trace_id`.
   - Fallback theo `pending_order_id` hoặc `cmd_id` trong SQL không chạy được trong case này.
   - Kết quả: journal không chuyển `EXECUTED` dù event có `pending_order_id`/`cmd_id`.

2. Event `ORDER_FILLED` thiếu `position_ticket`.
   - `on_order_filled` không thể set `ticket`.
   - `on_order_opened` sẽ báo missing ticket và return false.

3. Event thiếu `open_price` hoặc `price`.
   - `on_order_opened` reject nếu `entry_price is None` hoặc `entry_price <= 0`.

4. Event thiếu `time` hoặc `open_time`.
   - `on_order_opened` reject vì không cho fallback entry time.
   - Đây phù hợp rule hệ thống: entry time phải từ MT5.

5. Provider không phát `ORDER_FILLED`.
   - Không có event nối `pending_order_id` với `position_ticket`.
   - DB sẽ giữ row ở `TRIGGERED`, có `pending_order_id`, nhưng không có `ticket`.

6. Row journal không còn `TRIGGERED`.
   - Query update chỉ target `WHERE status = 'TRIGGERED'`.
   - Nếu row đã bị close/update sai trạng thái trước đó, fill event không update được.

7. Duplicate/realtime race.
   - Dispatcher có thể xử lý `ORDER_FILLED` từ final response hoặc event listener.
   - Query chỉ update row `TRIGGERED`, nên lần đầu chuyển `EXECUTED`; lần sau có thể không match nữa. Đây thường là idempotency chấp nhận được, nhưng log có thể báo update false ở event sau.

## DB E2E proof hiện có

File: `services/aureus-trader/scripts/verify_limit_order_lifecycle_db_e2e.py`

Script chứng minh lifecycle:

- Tạo `STRATEGY_MATCH`.
- Gọi `on_order_pending_placed` với `pending_order_id`.
- Assert journal `status = TRIGGERED`, `pending_order_id` đúng, `ticket is None`.
- Gọi `on_order_filled` với `pending_order_id`, `deal_ticket`, `position_ticket`, `open_price`, `time`.
- Assert journal `status = EXECUTED`.
- Assert `ticket == position_ticket`.
- Assert `position_id == position_ticket`.
- Assert `entry_deal_ticket == deal_ticket`.
- Sau đó gọi `on_order_closed` bằng `ticket = position_ticket` và assert close vẫn nối đúng row.

Command nếu DB sẵn:

```bash
python services/aureus-trader/scripts/verify_limit_order_lifecycle_db_e2e.py
```

## Verification đã chạy trong quick này

Command:

```bash
python -m pytest services/aureus-trader/tests/test_journal.py -k "pending or filled" -q
```

Kết quả:

```text
2 passed, 79 deselected in 0.17s
```

## Kết luận

Cơ chế hiện tại đã có mapping pending limit order id sang position ticket.

Mapping cụ thể:

- Pending placed: `pending_order_id` được lưu vào DB khi nhận `ORDER_PENDING_PLACED`.
- Pending filled: provider gửi `ORDER_FILLED` với `pending_order_id`, `position_ticket`, `deal_ticket`.
- Trader journal: `position_ticket` được map thành `ticket` và `position_id`.
- DB audit: `deal_ticket` được lưu thành `entry_deal_ticket`.
- Update row: code hiện tại bắt buộc `trace_id`; `pending_order_id`/`cmd_id` chưa fallback độc lập khi `trace_id` thiếu.

Không cần sửa code trong quick report-only này. Việc cần làm nếu đang thấy DB không update là verify event thực tế và DB E2E: event `ORDER_FILLED` có đủ `trace_id`, `pending_order_id`, `position_ticket`, `deal_ticket`, `open_price`, `time`, và key match journal hay không.
