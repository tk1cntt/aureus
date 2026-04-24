# Timeout Analysis Report — 260424-sbg

## Scope
Phân tích chuỗi log sau:

- `13:20:01,636` Order queued: `ord-8d74d544f5b2`
- `13:20:01,638` Order queued: `ord-c52e9b1f48eb`
- `13:20:30,842` Result timeout: `ord-8d74d544f5b2`
- `13:20:30,842` Max retries exceeded: `ord-8d74d544f5b2`
- `13:20:35,851` ACK timeout attempt 1: `ord-c52e9b1f48eb`
- `13:20:41,861` ACK timeout attempt 2: `ord-c52e9b1f48eb`
- `13:20:47,845` ACK timeout attempt 3: `ord-c52e9b1f48eb`
- `13:20:51,903` Order rejected: `ord-c52e9b1f48eb` (`NACK: DUPLICATE`)

## Evidence from code

### 1) Trader timeout/retry behavior
`services/aureus-trader/dispatcher.py`

- ACK timeout: `self.config.ack_timeout` (default 5s)
- Result timeout sau ACK: `self.config.result_timeout` (default 30s)
- Retry tối đa: `self.config.max_retries` (default 3)
- Khi ACK timeout: republish cùng `cmd_id`, backoff `2**attempt` giây
- `NACK:DUPLICATE` là **non-retryable** (`NON_RETRYABLE_NACK_REASONS`)

### 2) Default config
`services/aureus-trader/config.py`

- `ack_timeout=5.0`
- `result_timeout=30.0`
- `max_retries=3`

### 3) EA side dedup
`mql5/AureusProvider.mq5`

- Nếu `IsDuplicateCmd(cmdId)` true ⇒ `SendNACK(cmdId, "DUPLICATE")`
- ACK được gửi ngay sau validate + dedup pass (`SendACK(cmdId)`), trước khi `OrderSend`
- Sau ACK mới `RecordCmdId(cmdId)`

## Timeline reconstruction

### Order A — `ord-8d74d544f5b2`
1. 13:20:01.636: Trader enqueue order A.
2. Dispatcher gửi command, có khả năng đã nhận `ACK` (vì không thấy log ACK timeout cho A).
3. Dispatcher chờ result (`ORDER_OPENED/ORDER_FAILED`) trong 30s.
4. 13:20:30.842: Hết `result_timeout` ⇒ `Result timeout` + `Max retries exceeded` ngay.

**Kết luận A:** timeout nằm ở pha **post-ACK**, tức phía thực thi lệnh/đẩy event kết quả không về kịp hoặc không về đúng `cmd_id`.

### Order B — `ord-c52e9b1f48eb`
1. 13:20:01.638: Trader enqueue order B.
2. Không nhận được ACK trong 5s ⇒ timeout attempt 1, trader republish cùng `cmd_id`.
3. Tương tự attempt 2 và 3.
4. 13:20:51.903: Nhận `NACK:DUPLICATE`.

**Kết luận B:** lệnh đã từng được phía EA ghi nhận vào dedup history trước đó, nhưng ACK cho trader không tới đúng lúc/lost; các lần republish về sau bị NACK duplicate.

## Root cause analysis

## Primary root cause (high confidence)
**Mất đồng bộ event delivery giữa trader và EA cho cùng `cmd_id`, tạo ra hai kiểu timeout khác nhau:**

- Với order A: ACK có thể đã tới nhưng result không tới trong `result_timeout=30s`.
- Với order B: command được EA nhận/ghi dedup nhưng ACK không tới trader trong cửa sổ 5s, dẫn tới retry; cuối cùng chỉ nhận được NACK duplicate.

## Contributing factors
1. **`ack_timeout` ngắn (5s)** trong môi trường có jitter/độ trễ bridge/socket.
2. **Dedup ở EA là in-memory FIFO** (`RecordCmdId`), không đồng bộ trạng thái thực thi với trader future.
3. **Retry cùng `cmd_id`** là đúng về idempotency, nhưng khi ACK gốc bị trễ/lost thì pattern tự nhiên là `ACK timeout` → `NACK DUPLICATE`.
4. Không có correlation log đầy đủ hai đầu (trader + EA) theo cùng `cmd_id` để xác minh nhanh ACK/result bị mất ở hop nào.

## What this incident is NOT
- Không phải lỗi validation command thuần túy (`INVALID_COMMAND`), vì khi đó sẽ NACK sớm và nhất quán.
- Không phải duplicate do signal layer enqueue trùng trong cùng micro-second một cách rõ ràng; pattern log phù hợp hơn với retry path ở dispatcher.

## Confidence
- **High** cho kết luận về cơ chế timeout/retry/dedup (đọc thẳng từ code).
- **Medium** cho vị trí mất event chính xác (cần log runtime bridge/EA tại mốc 13:20 để chốt hop rơi gói).

## Actionable recommendations

### Immediate (no code / low risk)
1. Tăng tạm `ACK_TIMEOUT` từ `5s` lên `8-10s` để giảm false timeout.
2. Tăng `RESULT_TIMEOUT` từ `30s` lên `45-60s` với symbol dễ chậm (BTCUSD lúc thị trường bận).
3. Bật debug log correlation theo `cmd_id` ở cả trader và EA trong khung giờ sự cố.

### Short-term code improvements
1. **Phân tách ACK timeout vs duplicate-recovery:**
   - Nếu nhận `NACK:DUPLICATE` sau các ACK timeout, classify riêng là `ACK_LOST_DUPLICATE_RECOVERY` (không coi là reject business bình thường).
2. **Bổ sung metric:**
   - `ack_timeout_count`, `result_timeout_count`, `nack_duplicate_after_ack_timeout_count`.
3. **Enrich log:**
   - Log publish timestamp + retry attempt + elapsed time theo `cmd_id`.

### Medium-term hardening
1. Cân nhắc cơ chế ACK idempotent replay ở bridge (resend ACK khi nhận duplicate cmd_id gần thời điểm cũ).
2. Cân nhắc correlation store ngắn hạn (Redis) để giữ trạng thái `cmd_id -> ack_sent/result_sent` xuyên jitter.

## Verification checklist
1. Reproduce controlled test: chèn delay ACK hoặc delay ORDER_OPENED để xác nhận pattern tương tự.
2. Sau khi tăng timeout, theo dõi 24h:
   - Tỷ lệ `ACK timeout` giảm?
   - Tỷ lệ `NACK:DUPLICATE` sau ACK timeout giảm?
3. Kiểm tra event completeness theo cmd_id:
   - `publish OPEN_ORDER` -> `ACK/NACK` -> `ORDER_OPENED/ORDER_FAILED`.

## Final diagnosis summary
Sự cố là **timeout do mất/đến trễ event trong pipeline trader↔EA**, không phải một lỗi đơn lẻ ở retry logic. `NACK:DUPLICATE` ở lệnh thứ hai là hậu quả của retry sau ACK timeout khi EA đã ghi nhận cmd_id trước đó.
