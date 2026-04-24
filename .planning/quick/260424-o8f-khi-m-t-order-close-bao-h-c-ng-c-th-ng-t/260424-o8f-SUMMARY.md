# Quick Task 260424-o8f Summary

## Objective
Fix bug Telegram ORDER_CLOSED hiển thị strategy sai do fallback từ event payload tạm thời (ví dụ `[sl 1.34877]`) khi thiếu journal context.

## Impact Analysis
Đã chạy bắt buộc trước sửa:
- `npx gitnexus impact --repo Aureus --direction upstream _format_close` → Risk **CRITICAL**
- `npx gitnexus impact --repo Aureus --direction upstream _resolve_journal_context` → Risk **CRITICAL**
- `npx gitnexus impact --repo Aureus --direction upstream _handle_order_closed` → Risk **CRITICAL**

Blast radius tập trung trong `order_reporter` run-flow, nên fix scope hẹp đúng điểm ORDER_CLOSED.

## Root Cause
Trong `order_reporter._format_close`, strategy lấy theo chain:
- `journal.strategy_name` → fallback `event.strategy_name` → fallback `event.strategy` → `N/A`

Khi journal lookup không resolve kịp/không có row, notifier vẫn gửi message và fallback sang `event.strategy`.
Một số payload close có `event.strategy` là chuỗi tạm (vd `[sl 1.34877]`), dẫn tới Telegram hiển thị sai strategy.

## Changes
### 1) `services/aureus-notifier/order_reporter.py`
- Cập nhật `_handle_order_closed`:
  - Nếu không resolve được journal context hoặc journal không có `strategy_name`, **skip gửi Telegram** cho event ORDER_CLOSED.
  - Ghi warning log rõ ràng: `Skip ORDER_CLOSED notification: unresolved strategy context trace_id=... ticket=...`

=> Ngăn hoàn toàn fallback sai semantic từ event payload.

### 2) `services/aureus-notifier/tests/test_order_reporter.py`
- Thêm regression tests:
  - `test_handle_order_closed_skips_when_strategy_unresolved`
  - `test_handle_order_closed_skips_when_journal_missing_strategy_name`

## Verification
- `pytest services/aureus-notifier/tests/test_order_reporter.py -x` ✅ (14 passed)
- Runtime log check:
  - `wsl -d Aureus -e bash -lc "docker logs --since 10m aureus-notifier-dev 2>&1"`
  - Kết quả: notifier vẫn gửi `Order close notification sent ...` bình thường cho các case resolve được context.

## Notes
- Đây là fix thiên về tính đúng đắn dữ liệu (correctness) cho thông điệp Telegram.
- Trade-off chủ động: với case thiếu context, ưu tiên **không gửi sai** hơn là gửi message fallback không đáng tin.
