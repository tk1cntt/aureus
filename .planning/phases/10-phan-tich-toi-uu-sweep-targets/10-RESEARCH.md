# Phase 10: Phân tích và Tối ưu sweep_targets trong structure.py - Tiền trạm Kỹ thuật (Research)

## 1. Mục tiêu (Objective)
Cung cấp cái nhìn chuyên sâu về Kỹ thuật thi công cho Pha 10, tập trung vào việc dịch chuyển hệ thống `OrderBlock` từ theo dõi `Mitigation` nhị phân (boolean) sang hệ Máy trạng thái đa lớp (State Machine).

## 2. Kiến trúc Hiện tại vs Đề Xuất
### Hiện tại (As-Is):
- `structure.py` chưởng quản toàn bộ từ lúc sinh OB đến lúc check `is_mitigated`.
- Tồn tại vòng lặp Check Mitigation O(N^2) nặng nề đối với OB lịch sử.
- Target được lấy bằng cách Hardcode cắt ngọn 10 nodes `existing_targets[-10:]` cực nhiễu.
- `sweep.py` hoàn toàn lệ thuộc mảng Target sinh ra tử Structure.

### Đề xuất (To-Be - Solid Decoupling):
- **Structure (Bê tông)**: Chỉ chịu trách nhiệm đúc khuôn Pivot và sinh OB với cờ lót ổ: `state: 'PENDING'`, `break_counter: 0`.
- **Sweep (Trạm kiểm lâm)**: Lặp qua array `state_obj.obs`. Cập nhật trạng thái từng cây nến với 4 States: `PENDING`, `TOUCHED`, `SWEPT` (Kích hoạt Signal STOP_HUNT), `BROKEN_PENDING` (Chờ 2 nến xác nhận), `DEAD`.
- **Garbage Collection (GC)**: Sweep tự lọc mảng OB, xén bỏ OB `DEAD`.

## 3. Thuật toán Trọng tâm (Algorithms)

### A. Distance-based Truncation (Chống RAM Leak)
Thay vì chém 10 OB cũ nhất, ta lấy `10 OB gần Giá nhất`:
```python
# Sắp xếp các PENDING/TOUCHED OB dựa theo khoảng cách tuyệt đối tới giá nến hiện hành (candle['c'])
bull_obs.sort(key=lambda x: abs(x['top'] - float(candle['c'])))
# Chỉ giữ lại 10 OB gần nhất mỗi bên
active_obs = bull_obs[:10] + bear_obs[:10]
```

### B. List Comprehension Memory Lock (An toàn Vòng lặp)
Khi cập nhật `state_obj.obs` trong `sweep.py`:
```python
state_obj.obs = [ob for ob in state_obj.obs if ob.get('status', 'PENDING') != 'DEAD']
```

### C. Cơ chế Đếm Nến (Candle Counter) M1
Mỗi Tick, khi check OB đang ở `BROKEN_PENDING`:
```python
if close_is_outside_and_wick_is_outside:
    ob['break_counter'] += 1
    if ob['break_counter'] >= 2:
        ob['status'] = 'DEAD'
elif wick_touches_ob:
    ob['break_counter'] = 0
    ob['status'] = 'SWEPT' # Trap
```

## 4. Tương thích Event Redis
Bắn trạng thái OB ra ngoài thông qua `transient_signals`:
```python
state_obj.transient_signals["ob_state"] = state_obj.obs
request_ai_update("OB_STATE_CHANGE")
```

## 5. Validation Architecture (Nyquist Framework)
Để Pass qua vòng Test, ta cần tạo Mock Tests:
- Gỉa lập 1 nến chọc thủng thân qua OB -> Kiểm tra xem status có đổi thành `BROKEN_PENDING` không.
- Giả lập 2 nến ngay sau đó tách rời hoàn toàn OB -> Kiểm tra counter có `==2` và nhảy thành `DEAD` không.
- Giả lập mảng 50 OB -> Chạy hàm GC của `sweep.py` xem list có giữ đúng 10 OB gần C-Price nhất không.

## RESEARCH COMPLETE
