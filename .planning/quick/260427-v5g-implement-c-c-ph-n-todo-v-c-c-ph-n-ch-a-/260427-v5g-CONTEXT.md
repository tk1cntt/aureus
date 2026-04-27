# Quick Task 260427-v5g: Implement các phần TODO và các phần chưa hoàn thiện ở services\aureus-signal\engine\orders.py - Context

**Gathered:** 2026-04-27
**Status:** Ready for planning

<domain>
## Task Boundary

Implement các phần TODO và các phần chưa hoàn thiện ở `services\aureus-signal\engine\orders.py`.

</domain>

<decisions>
## Implementation Decisions

### Scope TODO
- Implement toàn bộ TODO/chưa hoàn thiện trong `orders.py`, chỉ sửa file khác khi bắt buộc để test hoặc tương thích.

### Order behavior
- Nếu có lỗi broker/order lifecycle: log warning và reject order.
- Không retry order submission vì order chỉ có ý nghĩa tức thì; retry làm mất tính đúng thời điểm vào lệnh.

### DB/E2E test
- Nếu thay đổi chạm tới database hoặc luồng tạo/sửa data, phải chạy DB E2E để xác nhận chỉnh sửa và tạo data thành công.

### Claude's Discretion
- Giữ thay đổi tối thiểu, theo pattern hiện có, không mở rộng scope ngoài nhu cầu của `orders.py`.

</decisions>

<specifics>
## Specific Ideas

No specific implementation references beyond the selected behavior constraints above.

</specifics>

<canonical_refs>
## Canonical References

No external specs — requirements fully captured in decisions above.

</canonical_refs>
