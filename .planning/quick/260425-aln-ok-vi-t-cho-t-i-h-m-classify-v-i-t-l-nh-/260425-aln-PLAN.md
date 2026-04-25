# Quick Task 260425-aln Plan

## Objective
Viết hàm classify TPO shape cho 4 dạng `D/B/p/b` kèm tỷ lệ (%) và update hiển thị trong SIGNAL ALERT Telegram.

## Scope
1. Cập nhật `services/aureus-signal/engine/signals/tpo.py`
   - Bổ sung classify shape + confidence + score distribution.
   - Giữ tương thích payload cũ (`POC/VAH/VAL`) và mở rộng thêm trường shape.
2. Cập nhật `services/aureus-notifier/formatters.py`
   - Render shape + confidence trong phần TPO của Indicator Snapshot.
3. Cập nhật tests liên quan
   - `services/aureus-signal/tests/test_tpo_signal.py`
   - `services/aureus-notifier/tests/test_formatters.py`

## Verification
- `pytest services/aureus-signal/tests/test_tpo_signal.py services/aureus-notifier/tests/test_formatters.py services/aureus-signal/tests/test_indicator_snapshot.py -q`
- Xác nhận message SIGNAL ALERT có chuỗi `Shape:<D|B|p|b> (<xx.x>%)` khi payload có dữ liệu classify.

## Notes
- Đã chạy GitNexus impact trước khi sửa cho các symbol chính:
  - `build_indicator_snapshot_for_telegram` (CRITICAL)
  - `_format_indicator_section` (LOW)
  - `_build_profile` (LOW)
