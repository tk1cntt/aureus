# Phase 9: Signal Structure & Traceability v1.1 (CONTEXT)

## 1. Phương Châm Tối Cao (User Directive)

`structure.py` được xác nhận là một tệp logic cực kỳ phức tạp, có tính dây chuyền cao và mong manh ("sửa lần nào lỗi lần đó").
Vì vậy, định hướng tối thượng của Phase 9 là: **KHÔNG CHẠM VÀO THUẬT TOÁN LÕI.** 
Bất cứ sự thay đổi nào đối với Loop `_process_choch`, `_process_ob`, hay `_verify_mitigations` đều bị cấm ngặt trừ khi chứng minh được bằng toán học và Snapshot test. Mọi nỗ lực tối ưu Performance (O(N) thay vì O(N*M)) phải dẹp sang một bên để nhường chỗ cho **Sự ổn định tuyệt đối (100% Output Parity)**.

## 2. Tiêu chí Tối ưu hóa an toàn (Non-Destructive)

Cách duy nhất để thực thi Phase 9 mà không làm hỏng Logic là **"Read-Only Injection"** (Bọc Traceability ở chế độ chỉ đọc):
1. **Traceability v1.1 Wrapper**: Thay vì sửa code sâu bên trong, chúng ta chỉ gài một đoạn code ở **cuối hàm `calculate`** để đọc các giá trị `state_obj.obs`, `points`, v.v... rồi dịch nó sang định dạng payload `transient_signals['ob_state']` và `choch_state`. Việc này đảm bảo Data Pipeline của Signal Factory nhận đủ v1.1 payload mà Signal Core không bị di dịch 1 bit nào.
2. **Loại bỏ Code Rác (Dead Code)**: Chỉ xóa những lệnh rác như `print()`, `logger.debug` thừa thãi (nếu an toàn). Bỏ qua ý định xóa các OB đã Mitigated vì nó có thể phá vỡ Logic đếm OB đang chạy ngầm của hệ thống.

## 3. Chiến lược Kiểm Thử: Golden Master (Snapshot Testing)

Trước khi viết thêm bất kỳ dòng Traceability nào vào file, chúng ta KHỞI TẠO Tấm khiên bảo vệ mang tên **Golden Master Test**:
- Inject một tập nến mẫu vào bản gốc của `structure.py`.
- Khóa (Dump) toàn bộ state Output ra file JSON.
- Sau khi gắn màng bọc Traceability, chạy lại tập nến đó và Assert Hash hoặc Dump Text 100% phải trùng khớp bit-for-bit với bản gốc. Nếu sai 1 dấu phẩy hoặc lệch thuộc tính, lập tức Revert.

## 4. Bàn Giao (Deliverables)

- Giữ nguyên toàn vẹn cấu trúc file `structure.py` hiện hành.
- Bổ sung Output Map cho `transient_signals['ob_state']` và `transient_signals['choch_state']` để Signal Factory không báo MISSING.
- Sinh Test Suites: Unit test chuyên bảo vệ Snapshot (Golden Master). Tích hợp test Runtime. Đảm bảo Coverage > 80% chỉ bằng cách quét, không refactor.
