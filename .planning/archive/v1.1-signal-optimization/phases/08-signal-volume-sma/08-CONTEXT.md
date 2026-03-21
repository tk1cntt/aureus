# Phase 08: Signal Volume SMA Optimization Context

## 1. Vấn Đề Ghi Trạng Thái (State Mutation Hardcoding)
**Decision:** Áp dụng Dynamic Attribute (Option 1A) `setattr(state_obj, f"vol_sma_{self.period}", sma_val)`.
**Reason:** Giải pháp này giữ nguyên tính tương thích 100% khi Signal được gọi với mặc định `period=20` (vẫn sẽ sinh ra `state.vol_sma_20`), nhưng đồng thời mở khóa tính đa hình nếu tương lai hệ thống muốn tạo thêm tín hiệu `VolumeSMASignal(period=50)` mà không bị dẫm đạp biến.

## 2. Điểm Kích Hoạt Tín Hiệu (Event Trigger Threshold)
**Decision:** Thêm tham số `spike_threshold` (Configurable, mặc định = 1.0 HOẶC 1.5) vào lớp `VolumeSMASignal` (Option 2A lai 2B).
**Reason:** 
- State Update (ghi vào `state_obj`) luôn chạy mọi nến. Tại đây cấu trúc Judge cũ ko bị hỏng.
- Signal Emit (hành vi `return dict`) chỉ bắn ra Event Tag khi Thể tích nến Vượt Chuẩn (`current_vol > sma_val * spike_threshold`). 
- Default `threshold=1.0` sẽ đóng vai trò Volume Crossover qua đường SMA. Đề xuất này biến `volume_sma` thành một hệ thống cảnh báo (Signal) thay vì bộ máy xả rác Indicator vô nghĩa.

## 3. Khử Nhiễu Dữ Liệu (Missing Data / NaN Handling)
**Decision:** Zero Imputation `fillna(0)` (Option 3A).
**Reason:** Nếu tick data từ Gateway bị khuyết cột Volume (NaN), theo thực tế Trading nghĩa là nến đó không có thanh khoản (Volume = 0). Việc quy về `0` giữ nguyên vẹn mẫu số của SMA (vẫn chia đều cho 20 nến) giúp trung bình bị kéo xuống một cách phản ánh chính xác trạng thái thị trường cạn cung/cầu.

## Code Context & Guiderails
- **Target File:** `services/aureus-signal/engine/signals/volume_sma.py`
- Nắm giữ tuyệt đối public interface `calculate(self, df, state_obj)`.
- **Event Contract Payload:** Khi triggered phải tuân thủ nghiêm ngặt hình hài:
  `{"tag": f"vol_sma_{self.period}", "value": round(sma_val, 2), "current_vol": ...}`
- Cần tạo Test File `test_volume_sma_o1.py` cho logic threshold spike và Missing Data coverage.
- Cần tạo Integration Test Execution Node cho volume_sma.
