# Phase 11: Daily Signal Recalculation (Garbage Collection) - Research

## Objective
Thiết kế cơ chế dọn RAM state an toàn theo chu kỳ ngày để tránh phình `obs` khi engine chạy dài hạn.

## Key Constraints
- Trigger đúng mốc **00:00 UTC** (tương đương 05:00 GMT+7).
- Không block luồng xử lý realtime chính.
- Không thêm DB persistence path cho Order Block trong phase này.
- Giữ tương thích dashboard hiện có.

## Technical Findings
- Điểm tích hợp phù hợp là vòng lặp runtime trong `live_engine.py`.
- Dùng background loop kiểm tra mỗi phút + guard `last_gc_date` để tránh trigger lặp trong cùng ngày.
- Reuse flow `recalculate_all_signals` để dựng lại state từ cửa sổ 1500 nến thay vì tự viết GC rời rạc.

## Selected Approach
1. Bổ sung async daily GC loop trong engine runtime.
2. Khi chạm điều kiện thời gian và chưa chạy trong ngày:
   - Ghi log trigger.
   - Gọi recalculate theo flow chuẩn.
   - Cập nhật marker ngày đã chạy.

## Research Outcome
Giải pháp daily recalc đáp ứng mục tiêu chống OOM với rủi ro thấp, ít thay đổi kiến trúc, và không làm vỡ contract downstream.
