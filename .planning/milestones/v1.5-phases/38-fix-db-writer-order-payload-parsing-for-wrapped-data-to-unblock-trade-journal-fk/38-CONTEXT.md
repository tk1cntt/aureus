# Phase 38: Fix DB writer order payload parsing for wrapped data to unblock trade journal FK - Context

**Gathered:** 2026-04-09T20:55:43+07:00
**Status:** Ready for planning
**Source:** User decisions + codebase verification

<domain>
## Phase Boundary

Phase 38 tập trung sửa `aureus-db-writer` để parse đúng order events dạng wrapped payload (`type` + `data`) từ Redis stream, đảm bảo ghi dữ liệu trade nhất quán và không chặn luồng liên kết journal/FK downstream.

Phạm vi gồm:
- Chuẩn hóa contract giữa producer và consumer cho order stream
- Xử lý strict validation với trường bắt buộc (đặc biệt timestamp)
- Chính sách ACK cho event invalid để tránh retry loop
- Không mở rộng sang capability mới ngoài fix parsing/contract

</domain>

<decisions>
## Implementation Decisions

### Contract đồng nhất producer-consumer
- **D-01:** Canonical input cho DB writer là payload wrapped từ stream: top-level có `type`, `data`; dữ liệu order nghiệp vụ nằm trong `data` (JSON object/string).
- **D-02:** DB writer phải normalize vào một model canonical nội bộ trước khi validate/insert/update, thay vì đọc field top-level rời rạc.
- **D-03:** Mục tiêu là đồng nhất dữ liệu giữa producer và consumer; không dựa vào suy đoán shape.

### Status semantics
- **D-04:** Không map `type -> status` trong phase này.
- **D-05:** `status` chỉ lấy từ dữ liệu order thực tế; nếu thiếu thì xử lý theo rule validation (không tạo status giả từ event type).

### Timestamp policy (strict)
- **D-06:** Timestamp nghiệp vụ là trường bắt buộc cho các event cần ghi DB.
- **D-07:** Không dùng fallback timestamp không phản ánh nghiệp vụ (ví dụ suy ra từ stream `msg_id`) để ghi record chính.
- **D-08:** Event thiếu timestamp hợp lệ được coi là invalid payload theo policy reject của phase.

### Invalid event handling
- **D-09:** Chọn policy ACK + skip cho event invalid/business-invalid, kèm logging reason rõ ràng để vận hành và forensic.
- **D-10:** Tránh retry vô hạn cho dữ liệu lỗi contract.

### Payload persistence
- **D-11:** Cột `payload` JSONB chỉ lưu canonical normalized payload (không lưu cả raw envelope trong DB chính).

### the agent's Discretion
- Cách tổ chức helper normalize/validate trong `DBWriter.process_batch()` hoặc utility nội bộ.
- Chuẩn log message/reason_code chi tiết cho từng nhánh invalid.
- Bổ sung test coverage cho wrapped payload, missing required fields, ACK behavior.

</decisions>

<canonical_refs>
## Canonical References

### Roadmap & phase scope
- `.planning/ROADMAP.md` — Định nghĩa Phase 38 và mục tiêu fix parsing để unblock trade journal FK.

### Producer contract (order stream emit)
- `services/aureus-signal/engine/orders.py` — Publish order events theo dạng `{"type": ..., "data": json.dumps(order)}` cho `ORDER_PENDING`/`ORDER_OPEN`/`ORDER_CLOSE`.
- `services/aureus-signal/engine/strategy_executor.py` — Emit `ORDER_REJECTED` theo cùng envelope pattern.

### Consumer implementation cần sửa
- `services/aureus-db-writer/main.py` — `process_batch()` nhánh `order_buffer` hiện parse thiên về top-level fields và cần chuẩn hóa theo wrapped payload contract.
- `services/aureus-db-writer/main.py` — `check_xpending()` và ACK flow liên quan order stream recovery.

### Downstream dependency context
- `.planning/phases/37-trade-execution-journal/37-CONTEXT.md` — Bối cảnh journal phụ thuộc dữ liệu trade nhất quán từ DB writer.

</canonical_refs>

<specifics>
## Specific Ideas

- User yêu cầu xử lý theo hướng contract-first: producer và consumer phải đồng nhất schema.
- User chốt không map `type -> status` khi chưa đánh giá đầy đủ ảnh hưởng truy vấn dữ liệu theo status.
- User yêu cầu timestamp là dữ liệu quan trọng, không chấp nhận fallback giá trị có thể sai ngữ nghĩa.

</specifics>

<deferred>
## Deferred Ideas

- Đánh giá chiến lược map `type -> status` có thể làm ở phase khác khi có impact analysis đầy đủ trên truy vấn/báo cáo hiện hữu.

</deferred>

---

*Phase: 38-fix-db-writer-order-payload-parsing-for-wrapped-data-to-unblock-trade-journal-fk*
