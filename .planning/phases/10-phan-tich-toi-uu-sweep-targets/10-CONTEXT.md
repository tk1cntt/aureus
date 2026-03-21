# Context: Phase 10 - Phân tích và tối ưu sweep_targets trong structure.py

## 1. Yêu cầu & Bối cảnh (Background)
Khởi động đợt Discuss để phân tích lại toàn bộ lỗ hổng của logic sinh `sweep_targets` hiện tại trong MQL5.

## 2. Quyết định của Visionary (Decisions Captured)
- **Về CHOCH Origin làm Target**: Sếp đánh giá việc lấy cái chốt CHOCH Origin làm Target quét thanh khoản là thiếu cơ sở tín hiệu. Nó thiếu rất nhiều điều kiện xác nhận đảo chiều.
-> **Quyết định**: Xoá bỏ hoàn toàn `CHOCH_ORIGIN` khỏi logic sinh `sweep_targets`.

- **Về Vòng Đời OrderBlock (OB Lifecycle)**: Sếp chỉ ra rằng một OB khi bị giá chạm đến sẽ có 4 kịch bản trọn đời:
  1. **Touched & Reversed**: Chỉ chạm/táp nhẹ vào zone rồi đảo chiều đi đúng cấu trúc (Kiểm định thành công - Mitigation).
  2. **Swept & Reversed**: Giá đâm xuyên thủng dải OB (quét Stoploss / Liquidity Hunt) nhưng nến đóng cửa lập tức rút chân ngược trở lại và đảo chiều.
  3. **Broken (Phá vỡ giả/Trap)**: Giá đâm xuyên hoàn toàn (Close qua OB) nhưng chỉ bằng 1 nến. Nếu nến ngay sau quay lại áp đảo (Engulfing) thì tính là Trap/Fakeout chứ chưa bị phá hẳn.
  4. **Confirmed Broken & Gone**: Giá đâm xuyên tuột luốt. **ĐIỀU KIỆN TIÊN QUYẾT**: Phải chờ **2 NẾN TIẾP THEO** xác nhận vẫn đóng cửa phía ngoài OB VÀ râu nến (Wick) tuyệt đối KHÔNG chạm ngược lại vùng OB. Khi thỏa mãn nến thứ 2 này, OB mới chính thức bị vô hiệu hóa (Dead) hoặc bị vượt qua.

## 4. Đặc tả Kiến trúc Trạng Thái (State Machine Requirements)
- Xóa bỏ biến `is_mitigated=True/False` yếu ớt hiện tại.
- Xây dựng Counter đếm số nến kề từ khi xảy ra vụ đâm thủng (Breakout Candle) để tính toán State.
  - Nếu `Tick_N` đâm thủng, thì `Tick_N+1` và `Tick_N+2` phải hoàn toàn đóng ngoài và không dính râu.
  - Cần cơ chế Memory ghi nhớ những OB đang ở trạng thái Cấn Cáo (Pending Confirmation).

## 3. Các Gray Areas Đang Thảo Luận
- Cần mô hình hóa (State Machine) 4 trạng thái này vào Object của từng OB để `structure.py` và các module ngoài có căn cứ giao dịch thay vì chỉ gán cờ `is_mitigated=True/False` cực kì chung chung như cũ.
- Thiết kế Data Tracking: Dùng Candle Close vs Candle Wick để nhận diện khác biệt giữa Swept (chỉ xỏ kim) và Broken (thủng body).
## 5. Cấu Trúc Phân Bổ (Architecture Decoupling - Thay đổi cực lớn)
**A. `structure.py` (Nhà máy Bê tông - Chỉ đúc Khuôn)**
- **Xóa bỏ hoàn toàn**: Hàm `_verify_mitigations` cũ kỹ sẽ bị xóa sổ hoàn toàn khỏi file này. `calculate()` của Structure sẽ nhẹ gánh tối đa.
- **Chức năng duy nhất**: Đọc cấu trúc $\implies$ Nhận diện Pivot/CHOCH $\implies$ Sinh ra 1 OrderBlock sơ sinh (`state="PENDING"`, `break_counter=0`) và ném vào Array `state_obj.obs`. Chấm hết. 
- Không tự phân tích râu/thân nến nữa để giữ CPU cost thấp nhất cho hàm Sinh Cấu trúc.

**B. `sweep.py` (Trạm Kiểm Lâm - Cập nhật Tracking & Signal)**
- Vì đúng bản chất lý thuyết, Sweep là hành vi nến chọc thủng/xỏ kim qua Liquidity Zone. Việc quản lý 4 State của OrderBlock nằm trọn vẹn trong chuyên môn của Signal này.
- Đầu hàm `calculate()` của Sweep, ta sẽ chạy `_update_ob_states(candle)` duyệt qua list `state_obj.obs`.
- Dựa vào giá Close/Wick hiện tại, Sweep sẽ trực tiếp cập nhật trạng thái của OB (`TOUCHED`, `SWEPT`, `BROKEN_PENDING`, `DEAD`).
- Nếu nó vấp phải State `SWEPT`, nó kích hoạt ngay lệnh tạo Signal báo Stop Hunt về Factory.
- Cuối cùng, Tự tay `sweep.py` làm nhiệm vụ dọn rác (Garbage Collector): Đá văng các OB `DEAD` ra khỏi bộ nhớ bằng array filtering.

## 6. Xử lý Rủi Ro (Risk Mitigations từ Party Mode)
1. **Giải pháp chống tràn Memory (TTL / Garbage Collection)**: 
   - Không đếm theo thời gian mà giữ lại theo **Khoảng Cách (Distance)**.
   - Khi mảng quá lớn, tự động sắp xếp và **giữ lại đúng 10 OB gần với giá hiện tại nhất**. Tương tự cho mỗi bên Bull/Bear. OB càng gần giá thì rủi ro bị chạm càng lớn, càng đáng lưu trữ.
   - Mỗi khi trạng thái OB thay đổi, hệ thống sẽ đẩy Event vào Redis để update danh sách OB chuẩn và lưu vào DB.
2. **Đồng bộ Đếm Nến M1**:
   - Hiện tại hệ thống đang thiết kế chuẩn trên Timeframe M1. 
   - Giải pháp 2 nến xác nhận (`break_counter == 2`) sẽ được chốt cứng tính bằng nến M1. Đảm bảo triệt tiêu độ trễ/xung đột khung giờ.
3. **Kỹ thuật Code an toàn (Safe Iteration)**:
   - Dọn rác **bắt buộc dùng List Comprehension**: `state_obj.obs = [ob for ob in state_obj.obs if ob.get('status', 'PENDING') != 'DEAD']`. 
   - Yêu cầu này phải được ghi chú cực kỳ nắn nót vào bản chất **10-01-PLAN.md** sắp tới để lúc thi công không bị lỗi Python `IndexError` do xóa Element trong lúc đang Loop.
