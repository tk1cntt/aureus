# Phase 11 Context: Daily Signal Recalculation (Garbage Collection)

## Chuyển Hướng Kiến Trúc (Architectural Pivot)
Ban đầu hệ thống dự tính xử lý OOM cho Order Block bằng Database Persistence và Redis Stream Sync. Tuy nhiên, sau khi thảo luận (GSD Discuss), phương án đó quá rườm rà (Over-engineering), tiềm ẩn nguy cơ Botleneck DB khi có nhiều lượng truy cập từ Dashboard.

**Giải pháp Chốt Hạ (Từ Sếp): Hệ thống tự động dọn rác (Daily Reset) bằng hàm `recalculate_all_signals` vào thời điểm nến đóng/mở cửa ngày.**

---

## Các Quyết Định Kiến Trúc (Architectural Decisions)

### 1. Cơ chế Hoạt động (05:00 AM GMT+7)
- **Vấn đề đã giải quyết:** File RAM State (`state.obs`) sẽ phình to ra vô hạn nếu Engine chạy liên tục vài tuần, làm chậm tốc độ quét và gây sập RAM (Out of Memory).
- **Quyết định:** Viết một tiến trình (Cron Job / Background Task / Timer) kích hoạt tự động vào đúng **5 giờ sáng giờ Việt Nam (GMT+7)**, tức là **0 giờ khuya UTC** hàng ngày.
- **Hành động:** 
  - Clear sạch RAM State trên Redis của toàn bộ các Symbol.
  - Gọi lại hàm `recalculate_all_signals`.
  - Luồng tái khởi động vốn đã được thiết kế đọc 1500 nến M1 (tương đương hơn 24 tiếng giao dịch) để vẽ lại State mới nhất. Những OB nảy mầm từ trước đó 2 ngày sẽ vĩnh viễn bị xóa vứt, giữ cho RAM luôn cực xanh.

### 2. Sự Nguyên Vẹn của UI Dashboard (100% Backward Compatibility)
- **Vấn đề đã giải quyết:** Dashboard hiện đang Query 50 lệnh. Nếu Live Engine tự cắt 10 lệnh, UI của Dashboard sẽ mất dữ liệu hiển thị (ví dụ mất cục OB màu xám của những vùng giá đã bị đâm thủng do biến `DEAD` hoặc `mitigated`).
- **Quyết định:** Gỡ bỏ HOÀN TOÀN toàn bộ cơ chế Garbage Collection cắt lặp `[:10]` và lọc `DEAD` độc lập rườm rà ở bên trong file `sweep.py`. Tại 1 thời điểm `T`, có bao nhiêu OB sống/chết/nửa sống thì đều xuất ra bấy nhiêu OB. Chấp nhận cho mảng `obs` phình to tự nhiên tối đa trong 24 giờ.
- **Kết quả:** Code của hàm `signals` siêu mượt, UI ở Frontend nhận được trọn bộ dữ liệu lịch sử cực nét 50 OB không hề sứt mẻ trong suốt phiên giao dịch, và RAM Bot thì nhẹ tựa lông hồng.

### 3. Hiệu năng Hệ Thống (Zero DB I/O Dành Riêng OB)
- **Quyết định:** Order Block chỉ tồn tại duy nhất trên Môi trường Cache/RAM (Redis/Engine). Tuyệt đối không có lệnh INSERT / UPDATE rời rạc nào bắn vào PostgreSQL. 
- **Lợi ích:** Botleneck DB biến mất 100%. Backend API Dashboard Fetch từ Redis 1 Triệu Request một giây cũng không bao giờ làm ngỏm System. 

---

## Chuẩn Bị Thực Thi (Prepare for Execution)
- Xóa bỏ Code cũ ở `sweep.py` (Đã Dọn).
- Viết tính năng Cron Timer 5h Sáng tại `live_engine.py` (hoặc module tương tự) thay thế cho Phase 11 cũ.
