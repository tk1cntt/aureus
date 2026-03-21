# Phase 07 Context: Signal Trend Optimization

## Vision & Scope
Mục tiêu của Phase này là nâng cấp hoàn toàn thuật toán nhận diện xu hướng (Trend Detection) cho Hệ thống Signal. Phương pháp tính toán độ dốc (slope) qua EMA 200 hiện tại đã bộc lộ rõ yếu điểm (độ trễ lớn, false-break nhiều do lagging). 

Phase 07 đưa ra giải pháp thay thế đột phá: **OB-Dominance Matrix (Ma trận đếm Order Block)**. Bằng việc phân tích cấu trúc Cung/Cầu vĩ mô trực tiếp trên nền giá M1 (Leading Indicator), kết hợp rào cản vĩ mô EMA 200, hệ thống triệt tiêu nhiễu loạn và đảm bảo an toàn Accuracy-First cao nhất. Giữ vững tính Low-Latency nhờ đóng băng scope tính toán duy nhất ở M1.

## Gray Areas Resolved

### 1. Quản lý trạng thái OB & Timeframe Scope
**Decision:** `M1-Strict Unmitigated OB Counter`.
- Hệ thống duy trì một bộ đếm chỉ gồm các OB (Order Block) M1 **chưa bị đâm thủng** (unmitigated). 
- Bất kỳ OB nào bị giá quét/xuyên qua lập tức bị pop/xóa khỏi queue hiện tại để phản ánh lực cản thực tế nhất.
- Bỏ qua toàn bộ việc tính toán nến M5/M15 để tránh làm "phình" engine và duy trì khả năng thi hành độ trễ cực thấp.

### 2. Định lượng cờ xu hướng (Core Thresholds)
**Decision:** `N=2, M>=2 Order Flow Contract`.
Thay thế các phép kiểm tra slope mông lung thành lưới điều kiện Toán học / Cấu trúc chặt chẽ:
- **Kịch bản Sideways:** Nếu số lượng unmitigated `Green OB >= 2` VÀ `Red OB >= 2` đang đan xen nhau -> Trả cờ `SIDEWAYS`.
- **Kịch bản Áp đảo (Strong Trend):** Độ chênh lệch lực lượng phải là `abs(Green OB - Red OB) >= 2`.

### 3. Kịch bản Phân kỳ (Chaos / Dữ liệu mâu thuẫn)
**Decision:** `Strict EMA Directional Filtering (Anti-FOMO)`.
Ngay cả khi OB M1 áp đảo tuyệt đối (M>=2), tín hiệu xu hướng chỉ được phất cờ (BULLISH/BEARISH) nếu ĐỒNG THUẬN với hệ số tín nhiệm là **EMA 200**. 
- Nếu Lực Mua áp đảo nhưng Giá vẫn kẹt dưới EMA 200 -> Xung đột logic. Hệ thống gán cờ `NEUTRAL` và kiên quyết đứng ngoài thị trường (Discipline over FOMO) để chống lừa đảo từ tin tức Bơm/Xả.

## Code Context
- **Affected Path:** `services/aureus-signal/engine/signals/trend.py`.
- **Related Hooks:** Cần thiết lập logic (hoặc tái sử dụng data struct từ module sweep/structure) để theo dõi và cập nhật trạng thái Unmitigated OB trực tiếp runtime cho Trend signal.
- Cấu trúc cờ đẩy ra cuối cùng: `htf_trend` (BULLISH, BEARISH, NEUTRAL). Có thể định nghĩa thêm `market_regime` (TREND, SIDEWAYS) tùy thuộc vào class logic hiện tại.

## Next Steps Required for Planning
- Cần chạy `/gsd-plan-phase 7` (hoặc Researcher) để điều tra xem module cấu trúc hiện tại (structure/sweep) đã expose mảng OB list ra cho `trend.py` dễ dàng consume chưa.
- Lập checklist các kịch bản Integration Test ứng với Ma trận (Bơm xả ngược EMA, Sideways đan xen) để verify trước khi build code.
