# Quick Task 260424-a6a Summary

## Objective
Fix lỗi `trace_id = None` trong nhánh `ORDER_OPENED` khi `trace_id` chỉ được sinh/chuẩn hóa trong `await self.journal.on_strategy_match(strategy_payload)`.

## What changed

### `services/aureus-trader/dispatcher.py`
- Trong nhánh `final.type == "ORDER_OPENED"`:
  - Đổi `trace_id = order.get("trace_id", "")` thành `trace_id = order.get("trace_id")`.
  - Sau `await self.journal.on_strategy_match(strategy_payload)`, nếu `trace_id` ban đầu rỗng thì đọc lại từ `strategy_payload.get("trace_id")`.
  - Gán `final["trace_id"]` bằng trace đã resolve trước `on_order_opened`.

### `services/aureus-trader/tests/test_dispatcher.py`
- Thêm `TraceResolvingJournal` để mô phỏng trace_id được tạo trong `on_strategy_match`.
- Thêm test `test_dispatch_order_resolves_trace_id_after_strategy_match`:
  - `strategy_event.trace_id=None`, `order.trace_id=None`.
  - Xác nhận sau dispatch, cả `strategy_events[0]["trace_id"]` và `opened_events[0]["trace_id"]` đều là trace đã generate.

## Verification
- `pytest services/aureus-trader/tests/test_dispatcher.py -k "trace_id and strategy_match" -x` ✅
- `pytest services/aureus-trader/tests/test_dispatcher.py -x` ✅ (19 passed)

## Commit
- Code commit: `b17ad08` (`fix(trader): resolve late trace_id after strategy_match`)

## Notes
- Impact analysis đã chạy cho `dispatch_order` trước khi sửa (risk CRITICAL, scope đã được giới hạn đúng file mục tiêu).
- CLI hiện tại không có command `gitnexus detect_changes`; scope được kiểm soát bằng `git status` + `git diff` trước commit.