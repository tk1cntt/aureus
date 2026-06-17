# Quick Task Summary: StructureSignalM5 Implementation

**Status**: Complete
**Date**: 2026-06-17
**Task ID**: 260617-qv8

## Mô tả
Triển khai StructureSignalM5 để phát hiện CHoCH/BOS/Order Blocks trên timeframe M5, sử dụng phương án resample M1→M5 on-the-fly.

## Những gì đã hoàn thành

### Task 1: Extract shared logic ✓
- **File**: `engine/signals/structure_common.py` (mới)
- Tạo module chứa các helper functions dùng chung cho M1 và M5:
  - `detect_breakout()`: Phát hiện breakout candle
  - `find_opposing_extreme()`: Tìm opposing extreme (HH/LL)
  - `find_ob_zone()`: Tìm Order Block zone
  - `verify_mitigation()`: Kiểm tra OB mitigation
- Tất cả functions nhận numpy arrays, trả về primitives

### Task 2: Refactor structure.py ✓
- **File**: `engine/signals/structure.py` (sửa)
- Refactor `_process_choch_numpy()` dùng `detect_breakout()` và `find_opposing_extreme()`
- Refactor `_process_ob_numpy()` dùng `find_ob_zone()`
- Refactor `_verify_mitigations_numpy()` dùng `verify_mitigation()`
- Giữ nguyên `_calculate_old_path` (pandas path) không thay đổi

### Task 3: Implement StructureSignalM5 ✓
- **File**: `engine/signals/structure_m5.py` (mới)
- Class `StructureSignalM5` kế thừa `BaseSignal`
- Features:
  - Resample M1→M5 bằng `resample_to_tf(df, 'M5')`
  - Exclude forming candle: `ht_df.iloc[:-1]`
  - Private ZigZag instance: `self._zz_m5` (không dùng chung với M1)
  - Private swing_points: `self._swing_points_m5` (không lưu vào state_obj)
  - Private OBs: `self._obs_m5`
  - Emit tags: `choch_m5_up`, `choch_m5_down`, `bos_m5_up`, `bos_m5_down`
  - Store OB state: `transient_signals['ob_state_m5']`
- TODO: ZigZag params (ext_period=5, min_amplitude=100) cần tune cho M5

### Task 4: Register signal ✓
- **File**: `engine/signal_factory.py` (sửa)
- Import `StructureSignalM5`
- Register trong signal_set ngay sau `structure_processor`, trước `sweep_processor`
- Signal sẽ chạy tự động khi signal engine khởi động

## Verification
- ✅ `structure_common.py` imports thành công
- ✅ `structure_m5.py` imports thành công
- ✅ `structure.py` không có lỗi cú pháp sau refactor
- ✅ `signal_factory.py` không có lỗi cú pháp sau update

## Technical Decisions

### Tại sao dùng private state thay vì lưu vào state_obj?
1. **Tránh side effects**: M5 signals không ảnh hưởng M1 signals
2. **State isolation**: Mỗi timeframe có state riêng biệt
3. **Easier debugging**: Có thể track M5 state riêng
4. **No persistence overhead**: Không cần lưu M5 state vào DB

### Tại sao resample on-the-fly thay vì persistent M5 window?
1. **Đơn giản hơn**: Không cần quản lý 2 windows
2. **Tiết kiệm memory**: Chỉ tạo M5 data khi cần
3. **Consistency**: Luôn sync với M1 data
4. **Pattern đã có**: CISDMultiTFSignal dùng cùng approach

### Tại sao dùng shared helpers?
1. **DRY**: Logic CHoCH/BOS/OB giống nhau giữa M1 và M5
2. **Maintainability**: Sửa 1 chỗ, cả 2 dùng
3. **Testability**: Có thể test helpers độc lập
4. **Performance**: Numpy operations tối ưu

## Next Steps
1. **Tune ZigZag params**: Chạy production, monitor M5 CHoCH/BOS frequency
2. **Add unit tests**: Test structure_common helpers với edge cases
3. **Monitor performance**: Check CPU usage khi resample M1→M5
4. **Consider M15/H1**: Nếu M5 hoạt động tốt, mở rộng cho M15, H1

## Files Changed
- `services/aureus-signal/engine/signals/structure_common.py` (new)
- `services/aureus-signal/engine/signals/structure_m5.py` (new)
- `services/aureus-signal/engine/signals/structure.py` (modified)
- `services/aureus-signal/engine/signal_factory.py` (modified)
