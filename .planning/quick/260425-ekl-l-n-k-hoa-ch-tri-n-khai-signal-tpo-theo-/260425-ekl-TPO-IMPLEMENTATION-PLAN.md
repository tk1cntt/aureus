# Kế hoạch triển khai future Signal TPO

## Nguyên tắc phạm vi

Tài liệu này là kế hoạch cho future implementation. Quick task `260425-ekl` không implement runtime code, không sửa tests, migrations, config hoặc database.

## Mục tiêu kiến trúc

Triển khai theo pipeline:

```text
TPOSignal indicator → TPO feature/context layer → setup rule engine → strategy signal → backtest/calibration → production
```

Nguyên tắc quan trọng: giữ `TPOSignal` là indicator gốc, không nhồi logic vào lệnh vào class này.

## Output contract mục tiêu

Signal cuối nên chuẩn hóa theo dạng:

```python
{
    "tag": "tpo_strategy",
    "t": ts,
    "side": "long" | "short" | "flat",
    "setup": "va_rejection" | "va_breakout_acceptance" | "trend_pullback" | None,
    "confidence": 0.0,
    "entry_type": "market" | "limit" | "stop" | None,
    "entry_price": None,
    "stop_loss": None,
    "take_profit": [],
    "context": {
        "d1_bias": "bullish" | "bearish" | "neutral",
        "h1_shape": "D" | "B" | "p" | "b" | None,
        "m30_shape": "D" | "B" | "p" | "b" | None,
        "price_location_h1": "above_vah" | "inside_va" | "below_val" | "near_poc",
        "poc_shift_h1": "up" | "down" | "flat" | "unknown"
    },
    "reasons": []
}
```

## Slice 1 — Mở rộng TPO state/context

### Mục tiêu

Tạo lớp feature layer để diễn giải output hiện tại của `TPOSignal` thành ngôn ngữ trạng thái rõ nghĩa.

### File dự kiến sẽ sửa/tạo trong future implementation

- Tạo mới: `services/aureus-signal/engine/signals/tpo_context.py`
- Có thể sửa: `services/aureus-signal/engine/signals/tpo.py` để thêm metadata tối thiểu nếu cần.
- Tạo/sửa test: `services/aureus-signal/tests/test_tpo_context.py`

### Thành phần chính

- `TPOContextBuilder`
- Context fields dự kiến:
  - `price_location_d1/h1/m30`
  - `distance_to_poc_*_ticks`
  - `distance_to_vah_*_ticks`
  - `distance_to_val_*_ticks`
  - `va_width_*`
  - `poc_shift_*`
  - `va_width_change_*`
  - `shape_transition_*`
  - `is_accepting_above_*_vah`
  - `is_rejecting_below_*_val`

### Test dự kiến trước khi implement

- RED test cho price location:
  - close > VAH → `above_vah`
  - close < VAL → `below_val`
  - close gần POC → `near_poc`
- RED test cho `va_width = VAH - VAL`.
- RED test cho history-based `poc_shift`:
  - POC tăng → `up`
  - POC giảm → `down`
  - POC đổi nhỏ trong tolerance → `flat`
- RED test cho output không crash khi block D1/H1/M30 là `None`.

### Output contract của slice

```python
{
    "timeframes": {
        "D1": {...},
        "H1": {...},
        "M30": {...}
    },
    "bias": {
        "d1": "bullish" | "bearish" | "neutral"
    }
}
```

### Tiêu chí không overfit

- Không dùng shape làm điều kiện quyết định duy nhất.
- Price relation và history phải độc lập với shape score.
- Threshold `near_poc` phải dựa trên tick size/ATR hoặc config được backtest sau, không hardcode tùy tiện.

## Slice 2 — History store cho TPO

### Mục tiêu

Lưu history tối thiểu để đo shift/transition, phục vụ detector.

### File dự kiến sẽ sửa/tạo trong future implementation

- Có thể sửa: `services/aureus-signal/engine/signals/tpo.py`
- Có thể tạo: `services/aureus-signal/engine/signals/tpo_history.py`
- Test: `services/aureus-signal/tests/test_tpo_history.py`

### History shape đề xuất

```python
state_obj.tpo_history = {
    "D1": [],
    "H1": [],
    "M30": []
}
```

Mỗi item lưu:

```python
{
    "t": ts,
    "POC": poc,
    "VAH": vah,
    "VAL": val,
    "shape": shape,
    "shape_confidence_pct": confidence,
    "va_width": vah - val
}
```

### Test dự kiến trước khi implement

- History append đúng khi có block mới.
- Không append duplicate cùng timestamp/timeframe.
- Giới hạn length để tránh memory growth.
- POC/VA shift tính đúng từ 2 snapshot gần nhất.

### Tiêu chí không overfit

- History chỉ lưu facts từ indicator, không lưu kết luận trade.
- Detector/scorer mới diễn giải history.

## Slice 3 — 3 detector đầu tiên

### Mục tiêu

Bắt đầu với 3 setup ít overfit và bám sát `tpo_indi.txt`:

1. `VARejectionDetector`
2. `VABreakoutAcceptanceDetector`
3. `TrendPullbackDetector`

### File dự kiến sẽ sửa/tạo trong future implementation

- Tạo mới: `services/aureus-signal/engine/signals/tpo_detectors.py`
- Test: `services/aureus-signal/tests/test_tpo_detectors.py`

### 3.1. `VARejectionDetector`

Long condition v1:

- previous close < H1/M30 `VAL`
- current close reclaimed above `VAL`
- current close vẫn dưới hoặc gần `POC`
- D1 không bearish mạnh
- shape chỉ là feature phụ, ưu tiên `D` hoặc `B` nhưng không bắt buộc tuyệt đối

Short condition đối xứng quanh `VAH`.

Output detector:

```python
{
    "setup": "va_rejection",
    "side": "long" | "short",
    "valid": True,
    "score": 0.0,
    "entry_zone": [low, high],
    "invalidation": price,
    "reasons": []
}
```

### 3.2. `VABreakoutAcceptanceDetector`

Long condition v1:

- close hiện tại > `VAH`
- 1-2 nến sau không đóng lại dưới `VAH`
- POC M30 hoặc H1 không giảm
- shape M30/H1 hỗ trợ continuation nhưng không là điều kiện duy nhất

Short condition đối xứng dưới `VAL`.

### 3.3. `TrendPullbackDetector`

Long condition v1:

- giá trên D1 POC hoặc D1 bias bullish/neutral-up
- pullback về H1 POC/VAL
- M30 có tín hiệu reclaim hoặc rejection nhỏ

Short condition đối xứng.

### Test dự kiến trước khi implement

- Mỗi detector có case long valid, short valid, invalid.
- Detector không phát signal khi thiếu context bắt buộc.
- Conflict obvious không tạo valid signal.
- Reasons phải giải thích đủ các điều kiện chính.

### Tiêu chí không overfit

- Detector chỉ phát setup candidate, không quyết định trade cuối.
- Không tune threshold bằng một mẫu duy nhất.
- Shape confidence là điểm cộng/trừ, không phải gate tuyệt đối.

## Slice 4 — `TPOStrategySignal` scorer

### Mục tiêu

Tổng hợp detector output, chấm điểm, xử lý conflict, sinh final `long/short/flat`.

### File dự kiến sẽ sửa/tạo trong future implementation

- Tạo mới: `services/aureus-signal/engine/signals/tpo_strategy.py`
- Có thể cập nhật registry signal nếu project có cơ chế đăng ký signal.
- Test: `services/aureus-signal/tests/test_tpo_strategy_signal.py`

### Scoring gợi ý

- D1 context cùng chiều: +15 đến +20.
- H1 price relation rõ ràng: +15 đến +25.
- M30 trigger/reclaim: +20 đến +30.
- POC shift cùng chiều: +10 đến +15.
- Shape hỗ trợ: +5 đến +10.
- Conflict timeframe: trừ điểm hoặc flat.

Mapping v1:

- `score >= 70`: signal mạnh.
- `50 <= score < 70`: signal medium, có thể log/backtest, chưa production.
- `< 50`: `flat`.

### Test dự kiến trước khi implement

- Nhiều detector cùng chiều → chọn setup score cao nhất hoặc merge reasons.
- Detector long và short cùng valid → `flat` hoặc conflict theo rule rõ ràng.
- Score dưới threshold → `flat`.
- Output contract luôn đủ keys.

### Tiêu chí không overfit

- Threshold phải được xác nhận bằng backtest/calibration trước production.
- Không tối ưu riêng cho một symbol/timeframe.
- Log reasons để audit quyết định scorer.

## Slice 5 — Replay/backtest/calibration

### Mục tiêu

Xác minh setup có edge trước khi production.

### File dự kiến sẽ sửa/tạo trong future implementation

- Có thể tạo: `services/aureus-signal/tests/test_tpo_strategy_backtest_fixture.py`
- Có thể tạo script nội bộ: `scripts/replay_tpo_strategy.py` hoặc đặt theo convention hiện có.
- Có thể bổ sung docs/report sau backtest trong `.planning/quick/` hoặc phase tương ứng.

### Backtest cần đo

- Số setup theo loại.
- Winrate.
- Average R.
- Expectancy.
- MFE/MAE.
- Distribution theo regime:
  - trend day
  - range day
  - high volatility
  - low volatility
- Sensitivity theo confidence threshold.

### Test/verification dự kiến

- Replay không làm thay đổi runtime state ngoài output log/report.
- Kết quả deterministic với cùng input data.
- Có fixture nhỏ để verify detector/scorer theo sequence nến.

### Tiêu chí không overfit

- Split train/validation theo thời gian.
- Không tune threshold trên cùng đoạn dùng để report kết quả.
- Report riêng theo symbol/timeframe/regime.

## Slice 6 — Production readiness

### Mục tiêu

Chỉ đưa vào production sau khi backtest đạt tiêu chí tối thiểu và output signal ổn định.

### Việc cần kiểm tra

- Signal không spam khi market đi ngang không rõ edge.
- Có `reasons` đủ để debug Telegram/log.
- Có kill switch/config threshold nếu hệ thống signal hiện tại hỗ trợ.
- Không thay đổi schema database nếu chưa có plan riêng.
- Nếu có persistence mới liên quan database, phải có e2e test với database theo `CLAUDE.md`.

## Thứ tự implement đề xuất

1. `TPOContextBuilder`
2. TPO history store
3. `VARejectionDetector`
4. `VABreakoutAcceptanceDetector`
5. `TrendPullbackDetector`
6. `TPOStrategySignal`
7. Backtest harness/calibration
8. Production integration sau khi có report kết quả

## Definition of Done cho future implementation

- Unit tests pass cho context/history/detectors/scorer.
- Backtest report có số liệu theo setup và regime.
- Output signal có contract ổn định.
- Không dùng shape như trigger đơn độc.
- Không deploy production nếu chưa có calibration threshold.
