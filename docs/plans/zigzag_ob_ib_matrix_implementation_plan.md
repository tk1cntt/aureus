# Kế hoạch triển khai: Ma trận quyết định ZigZag OB->IB (Additive Only)

Kế hoạch này mã hóa các kết quả từ phiên Brainstorming vào file `zigzag_pro2.py`.

## User Review Required

> [!IMPORTANT]
> **Nguyên tắc cốt lõi**: Mọi thay đổi sẽ được thực hiện dưới dạng **thêm mới** (chèn logic tiền xử lý hoặc hàm hỗ trợ). Các khối mã MQL5 gốc sẽ được giữ nguyên hoặc chỉ được gọi sau khi logic OB đã được xử lý xong.

## Proposed Changes

### [Component] zigzag_pro2.py

Triển khai một State Machine nhỏ để quản lý trạng thái chờ đợi khi có nến Outside Bar.

#### [MODIFY] [zigzag_pro2.py](file:///d:/Aureus/services/aureus-signal/engine/common/zigzag_pro2.py)

1.  **Thêm các biến trạng thái vào `__init__`**:
    - `self.ob_waiting`: `bool` (Mặc định False).
    - `self.ob_high`, `self.ob_low`, `self.ob_index`, `self.ob_count`: Để theo dõi nến OB hiện tại.
    - `self.last_pivot_state`: Lưu Peak/Trough gần nhất tại `let` để tra cứu Ma trận.

2.  **Triển khai logic tiền xử lý**:
    - Chèn vào đầu vòng lặp xử lý nến.
    - Áp dụng các quy tắc từ Ma trận:
        - Xử lý Breakout Up/Down.
        - Xử lý trạng thái Pending cho Inside Bar.
        - Thực hiện "Quy tắc Thoát" sau 5 nến với biên độ < 50% OB.

3.  **Hạnh động cụ thể**:
    - Nếu là case `TROUGH -> OB -> Phá Low`: Cập nhật `self.up[ob_idx] = ob_high` (PEAK) VÀ `self.dn[breakout_idx] = new_low` (TROUGH).

## Verification Plan

### Automated Tests
- Chạy lại bộ unit test hiện có để đảm bảo không có regression.
- Viết test case mới mô phỏng kịch bản OB -> 5 IB -> Auto Wave.

### Manual Verification
- Kiểm tra visual trên MT5 để xác nhận các râu nến OB dài đã được bắt đúng điểm xoay.
