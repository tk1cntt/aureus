# Phase 44.4 — Structure Processor Optimization Requirements

## Mục tiêu
Tối ưu `StructureSignal` để giảm latency/candle nhưng **không thay đổi logic trading hiện tại** (strict parity).

## Bước 1: Liệt kê và Phân rã (Neutral Listing)

### Phương án A — Data-access optimization (Pandas iloc/iterrows -> NumPy array access)
- Giữ nguyên thuật toán, điều kiện breakout/mitigation/OB.
- Thay cách đọc dữ liệu từ DataFrame row-by-row sang mảng (`to_numpy()`).
- Duy trì output schema hiện tại.

### Phương án B — Incremental processing theo candle mới (delta scan)
- Lưu state nội bộ để chỉ xử lý phần dữ liệu mới thay vì quét full window mỗi lần.
- Có cơ chế invalidation/fallback full scan khi gặp out-of-order/reset.
- Cần bổ sung metadata state cho structure.

### Phương án C — Vector hóa/Batch predicate mạnh hơn
- Dùng mask/index tìm breakout/mitigation theo vectorized operations.
- Giảm vòng lặp Python, tăng xử lý theo block.
- Cần cẩn trọng vì logic event-driven nhiều điều kiện tuần tự.

### Phương án D — Shadow execution + parity verifier (dual-path)
- Chạy đồng thời old path + new path trong giai đoạn chuyển đổi.
- So sánh output runtime (tag/timestamp/OB fields/mitigation flags).
- Có cờ bật/tắt mode: `off|shadow|on`.

### Phương án E — Rewrite bằng extension (Numba/Cython/Rust)
- Chuyển phần hot-path sang runtime native/JIT.
- Yêu cầu build/deploy khác và tăng độ phức tạp vận hành.
- Cần contract test chặt để bảo toàn logic.

---

## Bước 2: Phân tích theo Tiêu chí (Attribute Mapping)

### Tiêu chí X: Hiệu năng / tốc độ thực thi
- Mạnh nhất: **E (extension native/JIT)**
- Kế tiếp: **C (vector hóa mạnh)**
- An toàn + cải thiện vừa phải: **A (array access)**
- Cải thiện lớn theo workload streaming: **B (incremental)**

### Tiêu chí Y: Khả năng bảo trì / ổn định / dễ rollback
- Mạnh nhất: **A + D**
- Kế tiếp: **B + D**
- Yếu hơn về maintainability: **C** (logic khó đọc hơn), **E** (toolchain phức tạp)

### Trade-off cụ thể
- Chọn **A thay vì B**:
  - Mất lợi thế giảm độ phức tạp theo thời gian thực (B giảm số scan lớn hơn khi workload tăng).
  - Được lợi: rủi ro thấp hơn, rollback dễ hơn, ít thay đổi state machine.

- Chọn **B thay vì A**:
  - Được lợi: tiềm năng giảm latency mạnh hơn trong live stream.
  - Mất: tăng rủi ro sai lệch state ở edge-case (out-of-order/reset/recovery).

- Chọn **C thay vì A**:
  - Được lợi: nhanh hơn trong một số phần scan.
  - Mất: readability và khả năng chứng minh parity tuần tự theo event giảm.

- Chọn **E thay vì A/B/C**:
  - Được lợi: performance trần cao nhất.
  - Mất: chi phí build/deploy, debug khó, thời gian đưa vào production dài hơn.

---

## Bước 3: Đề xuất dựa trên Context (Contextual Recommendation)

### Context cụ thể
1. Hệ thống live trading hiện tại yêu cầu **độ ổn định cao**, không được sai logic hiện có.
2. `structure_processor` là signal quan trọng, tác động downstream CHOCH/OB/sweep.
3. Đang có pipeline profiling theo candle và test suite Phase 44 (44.0→44.3) sẵn.
4. Nhu cầu chính: giảm latency nhưng ưu tiên **correctness > speed**.

### Đề xuất tối ưu
**Đề xuất chính: triển khai theo lộ trình A + D trước, sau đó mới cân nhắc B.**

#### Giai đoạn 1 (an toàn nhất): A + D
- Tối ưu truy cập dữ liệu nội bộ (`iloc/iterrows` -> arrays) nhưng không đổi điều kiện logic.
- Bật `shadow` parity verifier để so old/new runtime trong production.
- Chỉ chuyển `on` khi mismatch = 0 trong cửa sổ đủ lớn.

#### Giai đoạn 2 (nếu cần thêm performance): B + D
- Thêm incremental scan có fallback full scan cứng.
- Tiếp tục shadow verify cho tới khi ổn định.

**Lý do chọn:**
- Đáp ứng yêu cầu không sai logic.
- Có đường rollback rõ ràng.
- Dùng được hạ tầng test/profiling hiện có.
- Tối ưu theo bước nhỏ, giảm blast radius.

---

## Bước 4: Chế độ Phản biện Nghịch đảo (Adversarial Mode)

Giả sử đã chọn **A + D**.

### 3+ kịch bản có thể thất bại
1. **Sai khác do thứ tự/kiểu số khi chuyển sang arrays**
   - Ví dụ float precision/implicit cast làm khác điều kiện break ở ranh giới.
   - Hậu quả: CHOCH phát hiện sớm/muộn 1 candle.

2. **Parity checker không bao phủ đủ field**
   - Chỉ so tag/value mà bỏ qua metadata OB (`t_start`, `quality`, `break_counter`, `mitigated`).
   - Hậu quả: mismatch ngầm, ảnh hưởng downstream strategy.

3. **Shadow mode tạo overhead đáng kể**
   - Chạy dual-path trên giờ cao điểm làm tăng latency tổng.
   - Hậu quả: backpressure tại pipeline.

4. **Edge-case reset/recovery không đồng nhất**
   - Khi warmup/recalculate, state transient khác giữa old/new path.
   - Hậu quả: false mismatch hoặc tệ hơn là sai production nếu bật `on` quá sớm.

### Rủi ro kiến trúc thường bị bỏ qua
- Drift giữa logic core và logic parity comparator theo thời gian (comparator lỗi thời).
- Thiếu observability theo symbol/time-window khiến mismatch khó tái hiện.
- Không định nghĩa rõ “acceptance threshold” (bao nhiêu mismatch thì rollback).

### Suggest lựa chọn tốt nhất (sau phản biện)
**Vẫn giữ A + D là lựa chọn tốt nhất**, với điều kiện bắt buộc:
1. Comparator so sánh đầy đủ contract (tag, t, value, data fields quan trọng).
2. Có auto-fallback sang old path khi phát hiện mismatch.
3. Chỉ promote `on` sau khi pass:
   - Unit parity tests
   - Replay tests
   - Shadow runtime mismatch = 0 trong khoảng quan sát đã định.

---

## Yêu cầu thực thi & kiểm thử (làm chuẩn UAT)

### Functional parity
- [ ] Old path và optimized path cho kết quả identical trên bộ test chuẩn.
- [ ] Không thay đổi schema output của `structure_processor`.
- [ ] Không thay đổi side effects vào `state.transient_signals`, `state.obs`, `state.swing_points`.

### Runtime safety
- [ ] Có feature flag `AUREUS_STRUCTURE_OPT_MODE=off|shadow|on`.
- [ ] Shadow mode log mismatch có đủ context để debug (symbol, t, diff fields).
- [ ] Mismatch => auto fallback old path, không làm gián đoạn pipeline.

### Performance
- [ ] Giảm `structure_processor` avg_ms ít nhất 40% ở điều kiện tương đương.
- [ ] Không làm tăng `_total` latency do shadow mode khi ở `on`.

### Verification commands
- [ ] `pytest` phase suite (44.0→44.4) pass.
- [ ] Replay test so sánh old/new output pass.
- [ ] Production shadow window đạt tiêu chí mismatch = 0 trước khi bật `on`.
