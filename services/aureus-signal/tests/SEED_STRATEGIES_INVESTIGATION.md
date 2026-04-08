# Báo Cáo Điều Tra: 2 Sequences Không Được Kích Hoạt

## Tóm Tắt

**Vấn đề**: 2 trong 6 seed strategies không được kích hoạt trong thực tế.

**Kết luận**: Vấn đề **KHÔNG PHẢI** do logic trong `seed_strategies.py` hay sequence evaluation. 
Tất cả 6 strategies đều có thể trigger thành công trong unit tests.

**Nguyên nhân gốc rễ**: Có 2 khả năng:

### 1. Path gọi strategy evaluation SAI

Có 2 paths để evaluate strategies:

#### Path A: `evaluate()` - Direct Call
- **KHÔNG** kiểm tra context filters
- Chỉ kiểm tra sequence match + score threshold
- Được dùng trong một số places
- **Vẫn trigger được** dù context sai

#### Path B: `on_bar_close()` - Full Pipeline (Được khuyến nghị)
- **CÓ** kiểm tra context filters
- Kiểm tra sequence match + score threshold
- Kiểm tra timing (chỉ trigger đúng candle)
- Trả về `reason_code` chi tiết
- **ĐÚNG** phải được dùng trong production

**Nếu hệ thống đang gọi `evaluate()` thay vì `on_bar_close()`**, strategies sẽ trigger mà bỏ qua context filters.

### 2. Signals Không Được Tạo Ra

Các strategies cần các events sau:
- `choch_up` / `choch_down` (từ structure.py)
- `sweep_bull` / `sweep_bear` (từ sweep.py)

Nếu signal detectors không chạy đúng hoặc không ghi vào `log_signal_normalize`, 
strategies sẽ không có events để match.

## Kết Quả Tests

### Test 1: All Strategies Activation (Normalized Format)
```
✅ TREND_CONT_BULL (score=4.0, threshold=0)
✅ TREND_CONT_BEAR (score=4.0, threshold=0)
✅ ORDER_FLOW_BULL (score=8.5, threshold=6.0)
✅ ORDER_FLOW_BEAR (score=8.5, threshold=6.0)
✅ SESSION_SWEEP_BULL (score=7.0, threshold=6.0)
✅ SESSION_SWEEP_BEAR (score=7.0, threshold=6.0)
```
**Kết quả**: 6/6 trigger thành công

### Test 2: All Strategies Activation (Raw Event Format)
```
✅ TREND_CONT_BULL (score=4.0, threshold=0)
✅ TREND_CONT_BEAR (score=4.0, threshold=0)
✅ ORDER_FLOW_BULL (score=8.5, threshold=6.0)
✅ ORDER_FLOW_BEAR (score=8.5, threshold=6.0)
✅ SESSION_SWEEP_BULL (score=7.0, threshold=6.0)
✅ SESSION_SWEEP_BEAR (score=7.0, threshold=6.0)
```
**Kết quả**: 6/6 trigger thành công với raw format `{"tag": "choch", "value": "choch_up"}`

### Test 3: Context Filters
- Seed strategies **KHÔNG có** context filters → Đúng thiết kế
- Nếu có context filters, `evaluate()` vẫn trigger (BUG!)
- `on_bar_close()` đúng là không trigger khi context fails

### Test 4: Event Normalization
- Raw format `{"tag": "choch", "value": "choch_up"}` → normalized thành `choch_up` ✅
- Normalization hoạt động đúng trong `_evaluate_sequence()` dòng 198

## Files Đã Tạo

1. `test_seed_strategies_activation.py` - Tests activation của tất cả strategies
2. `test_seed_strategies_context_filters.py` - Tests context filters và event formats

## Khuyến Nghị

### 1. Kiểm Tra Production Code
Xem nơi nào đang gọi strategy evaluation:

```python
# SAI - Bỏ qua context filters
intent = strategy.evaluate(df, signals, state)

# ĐÚNG - Đầy đủ checks
result = strategy.on_bar_close({
    "df": df,
    "state": state,
    "backfill_status": "READY"
})
```

### 2. Thêm Logging
Thêm logging để theo dõi:
- Strategy nào được evaluate
- Events nào có trong `log_signal_normalize`
- Context nào đang được dùng (trend, session, EMA)
- Reason code khi không trigger

### 3. Debug Production
Kiểm tra logs thực tế:
```python
# Trong on_bar_close, log:
logger.debug(
    f"strategy={self.name} "
    f"context_passed={ctx['passed']} "
    f"failed_filters={ctx['failed_filters']} "
    f"score={core['score']} "
    f"matched_steps={core['matched_steps']} "
    f"reason_code={reason_code}"
)
```

### 4. Kiểm Tra Signal Generation
Xác minh rằng structure.py và sweep.py đang chạy:
- Structure detector có detect được choch_up/choch_down không?
- Sweep detector có detect được sweep_bull/sweep_bear không?
- Events có được ghi vào `log_signal_normalize` không?

## Chi Tiết Kỹ Thuật

### Event Normalization Logic
File: `engine/strategies/template.py` dòng 196-199

```python
if ev_val and isinstance(ev_val, str) and ev_tag in ["choch", "sweep", "ob", "fvg", "bos"]:
    ev_tag = ev_val
```

Điều này cho phép:
- `{"tag": "choch", "value": "choch_up"}` → match với strategy cần `choch_up`
- `{"tag": "sweep", "value": "sweep_bull"}` → match với strategy cần `sweep_bull`

### Seed Strategies Config
File: `engine/strategies/seed_strategies.py`

Tất cả 6 strategies đều có:
- `context_filters: []` (rỗng - không có filters)
- Sequence đơn giản (1-2 steps)
- Score thresholds thấp (0-6.0)

### Trigger Conditions

| Strategy | Events Cần Thiết | Min Score | Thực Tế Trigger? |
|----------|-----------------|-----------|------------------|
| TREND_CONT_BULL | choch_up | 0 | ✅ (score=4.0) |
| TREND_CONT_BEAR | choch_down | 0 | ✅ (score=4.0) |
| ORDER_FLOW_BULL | choch_up + sweep_bull | 6.0 | ✅ (score=8.5) |
| ORDER_FLOW_BEAR | choch_down + sweep_bear | 6.0 | ✅ (score=8.5) |
| SESSION_SWEEP_BULL | sweep_bull | 6.0 | ✅ (score=7.0) |
| SESSION_SWEEP_BEAR | sweep_bear | 6.0 | ✅ (score=7.0) |

## Kết Luận

**Tất cả 6 seed strategies đều hoạt động đúng trong unit tests.**

Nếu 2 strategies không trigger trong production, nguyên nhân có thể là:
1. Signal detectors không tạo ra events (structure.py hoặc sweep.py)
2. Events không được ghi vào `log_signal_normalize` đúng format
3. Code đang gọi sai path (`evaluate()` thay vì `on_bar_close()`)
4. Có context filters được thêm vào sau khi seed (khác với config gốc)

Cần kiểm tra logs production để xác định chính xác strategies nào không trigger và lý do.
