# Phase 14: Sequence Engine Foundation - Context

**Gathered:** 2026-03-22
**Status:** Ready for planning

<domain>
## Phase Boundary

Xây dựng thuật toán State Machine O(1) đánh giá chuỗi tín hiệu (sequence config) cho `TemplateStrategy`, thay thế vòng lặp duyệt `signal_history` mô phỏng cũ. Đảm bảo hỗ trợ chính xác timeout (`max_wait`), tín hiệu hủy (`reset_signals`) và các bước không bắt buộc (`required: False`).

</domain>

<decisions>
## Implementation Decisions

### Engine Architecture & Pattern Matching
- **D-01 (Party Mode):** Áp dụng mô hình Máy trạng thái (State Machine $O(1)$) xử lý dứt điểm theo từng nến. Chỉ lưu lại vết (index, timestamp) thay vì duyệt mảng.
- **D-02 (Party Mode):** Xử lý tín hiệu `reset_signals` có độ ưu tiên cao nhất. Nếu tìm thấy tín hiệu hủy -> reset `current_step_index = 0` ngay lập tức, phủ nhận mọi kết quả `match` trong chính nến đó.

### State Persistence
- **D-03 (User - 1A):** Trạng thái của Sequence (`current_step_index`, mảng `matched_indexes`...) phải được ghi đè vào `state_obj.strategy_progress`. Việc này tận dụng cơ chế serialize có sẵn để snapshot lên Redis, giúp phục hồi đúng chuỗi lệnh dang dở khi restart bot.

### Timeout Logic (max_wait)
- **D-04 (User - 2B):** Đơn vị đo `max_wait` được tính bằng "số lượng cây nến trôi qua" (Candle index difference) tính từ nến khớp ở bước liền trước tới nến hiện tại.

### Optional Steps (required: False)
- **D-05 (User - 3A):** Hỗ trợ scan xuyên bước ("nhảy" bước). Ngay trong cùng một cây nến, nếu một bước không bắt buộc (optional) bị trượt, Engine tự động bỏ qua và đối chiếu liền bước tiếp theo ở ngay nến đó.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Implementation Targets
- `services/aureus-signal/engine/strategies/template.py` — File chứa thuật toán chuỗi sẽ được cải tạo toàn diện.
- `services/aureus-signal/engine/strategies/registry.py` — Rà soát luồng truyền gọi `evaluate_all`.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Cấu trúc thư viện Dictionary `state_obj.strategy_progress` đã có cơ chế tự động Snapshot.
</code_context>
