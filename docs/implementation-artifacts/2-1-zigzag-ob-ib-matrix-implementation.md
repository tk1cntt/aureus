# Story 2.1: Triển khai Ma trận quyết định OB->IB cho ZigZag

Status: done

## Story

As a Boss (Trader),
I want ZigZag tự động xử lý nến Outside Bar và Inside Bar theo ma trận logic đã chốt,
so that các điểm xoay (Pivot) được xác nhận chính xác theo hướng phá vỡ và không bị bỏ lỡ các râu nến dài (wick).

## Acceptance Criteria

1. **Ưu tiên thay thế cực trị (Priority Replacement)**: Nếu trong khoảng `ext_period`, nến OB có High cao hơn Peak cũ hoặc Low thấp hơn Trough cũ, phải thực hiện cập nhật ngay.
2. **Trạng thái Chờ (Pending State)**: Khi xuất hiện OB, nếu nến tiếp theo là Inside Bar (IB), ZigZag phải tạm dừng vẽ (Pending). **Dùng cơ chế WIPE** xóa bỏ mọi pivot do code MT5 tự ý vẽ trong giai đoạn này.
3. **Ma trận quyết định (Post-process Override)**:
    - `PEAK -> OB -> Phá Low`: Xác nhận Đỉnh mới tại High OB và Đáy mới tại nến phá vỡ.
    - `TROUGH -> OB -> Phá High`: Xác nhận Đáy mới tại Low OB và Đỉnh mới tại nến phá vỡ.
    - Ma trận logic sẽ chạy **SAU** code MT5 để ghi đè hoặc điều chỉnh kết quả.
4. **Cơ chế Thoát mặc định (Default Exit)**: Nếu sau 5 nến IB mà biên độ dao động < 50% OB, thực hiện vẽ "Sóng kép" (Double Pivot) dựa trên trạng thái trước đó.
5. **Nguyên tắc Bảo tồn (Post-process Only)**: MT5 logic chạy nguyên bản, Matrix can thiệp ở cuối vòng lặp.

## Tasks / Subtasks

- [x] Task 1: Khởi tạo các biến trạng thái mới (AC: 2, 4)
  - Files
    - Modify: `services/aureus-signal/engine/common/zigzag_pro2.py`
  - [x] Step 1: Thêm `self.ob_waiting`, `self.ob_high`, `self.ob_low`, `self.ob_index`, `self.ob_count` vào `__init__`.
  - [x] Step 2: Thêm `self.last_piv_type` để theo dõi trạng thái Pivot gần nhất (Peak/Trough).

- [x] Task 2: Triển khai logic Tiền xử lý OB (Pre-processing) (AC: 1, 2, 3, 5)
  - Files
    - Modify: `services/aureus-signal/engine/common/zigzag_pro2.py`
  - [x] Step 1: Chèn khối logic kiểm tra nến hiện tại so với trạng thái `ob_waiting`.
  - [x] Step 2: Xử lý các điều kiện Breakout High/Low theo Ma trận.
  - [x] Step 3: Implement logic Double Pivot (Gán đồng thời cả `up` và `dn` buffer nếu cần).

- [x] Task 3: Triển khai Quy tắc Thoát 5 nến (AC: 4)
  - Files
    - Modify: `services/aureus-signal/engine/common/zigzag_pro2.py`
  - [x] Step 1: Tăng `ob_count` cho mỗi nến IB.
  - [x] Step 2: Kiểm tra biên độ dao động của 5 nến gần nhất so với OB Range.
  - [x] Step 3: Thực hiện vẽ cưỡng bức nếu thỏa mãn điều kiện.

- [x] Task 4: Kiểm định và Xác nhận (AC: Tất cả)
  - Files
    - Test: `services/aureus-signal/tests/test_zigzag_ob_logic.py`
  - [x] Step 1: Viết test case mô phỏng nến tin tức (OB cực to) và sideway.
  - [x] Step 2: Chạy bộ test để xác nhận logic "Double Pivot" hoạt động đúng.

## Dev Notes

- **Source components**: `ZigZagPro` class trong `zigzag_pro2.py`.
- **Constraint**: `self.ext_period` vẫn là tham số quan trọng cho logic thay thế cực trị.
- **Patterns**: Sử dụng `ExtremumType` enum để phân loại nến.

### References

- [Ma trận quyết định OB->IB](file:///d:/Aureus/docs/brainstorming/zigzag-ob-ib-matrix-2026-03-15.md)
- [Implementation Plan](file:///D:/Aureus/docs/plans/zigzag_ob_ib_matrix_implementation_plan.md)

## Dev Agent Record

### Agent Model Used

Antigravity (GPT-4o variant)

### File List
- `services/aureus-signal/engine/common/zigzag_pro2.py`
