# Quick Task 260425-bnh Plan

## Objective
Phân tích thuật toán TPO trong `services/aureus-signal/engine/signals/tpo.py`: khi có candle mới đang tính tiếp hay tính lại từ đầu, đánh giá kiến trúc theo quy trình 4 bước và đề xuất tối ưu.

## Scope
1. Đọc code TPO và luồng candle runtime liên quan.
2. Viết tài liệu phân tích neutral listing → attribute mapping → contextual recommendation → adversarial mode.
3. Cập nhật STATE.md và commit artifacts.

## Files
- `services/aureus-signal/engine/signals/tpo.py`
- `services/aureus-signal/engine/live_engine.py`
- `services/aureus-signal/engine/signal_factory.py`
- `.planning/quick/260425-bnh-ph-n-t-ch-nh-gi-thu-t-to-n-t-nh-to-n-tpo/260425-bnh-SUMMARY.md`

## Verification
- Tài liệu phải trả lời rõ: candle mới hiện tại tính tiếp hay tính lại từ đầu.
- Tài liệu phải có đủ 4 bước theo yêu cầu.
- Tài liệu phải đưa ra lựa chọn tối ưu và các fail scenarios.
