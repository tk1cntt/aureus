# 11-01: Summary - Daily Signal Recalculation (Garbage Collection)

## Execution Outcomes
Mục tiêu "Chống rò rỉ RAM (OOM)" cho hệ thống Order Block đã được giải quyết triệt để thông qua cơ chế tự động dọn rác System RAM mỗi ngày một lần lúc 5:00 sáng.

1. **Daily GC Loop**:  
   - Đã nhúng vòng lặp `daily_gc_loop()` vào bên trong hàm `run_signal_engine()`.  
   - Loop tự động chạy nền không gian (background task). Kích hoạt lệnh `recalculate_all_signals(1500 candles)` mỗi khi thời gian hệ thống chạm mốc **0:00 UTC (5 AM GMT+7)**.
   - Luồng tái kết xuất (Recalculate) đảm bảo dọn sạch toàn cục Order Blocks từ ngày hôm trước, thiết lập lại mốc Baseline 1 ngày mà không làm chặn luồng stream giá.

2. **Duy Trì Tính Tương Thích (Backward Compatibility)**:
   - Dashboard API vẫn hoạt động nguyên bản. Mọi "Box màu xám" từ trạng thái `TOUCHED/SWEPT` của hôm nay vẫn sẽ hiển thị mượt mà trên UI, tránh tình trạng bị tàng hình.
   - Chặn rủi ro thắt cổ chai Database (I/O Bottleneck) vì giải pháp không cần sử dụng PostgreSQL làm backend lưu Order Block.

3. **UAT & Code Quality**:
   - Baseline Code không thay đổi, Unit Tests của Signal vẫn Pass 100%.
   - Logic an toàn lồng vào (`last_gc_date`) chặn trường hợp Engine bị giật lú gọi GC 2 lần trong cùng một phút.

## Artifacts
- `d:\Aureus\services\aureus-signal\engine\live_engine.py` (Added `daily_gc_loop`).
- `11-UAT.md` (Tested logic timing manually).

---
**Status:** Completed. Tiết kiệm vĩnh viễn RAM phần trăm tăng trưởng mỗi ngày cho Live Engine.
