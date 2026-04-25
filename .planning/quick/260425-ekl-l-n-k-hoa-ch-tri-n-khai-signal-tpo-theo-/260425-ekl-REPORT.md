# Báo cáo phân tích triển khai Signal TPO

## Phạm vi

Quick task này chỉ lập tài liệu theo `D:/Aureus/tpo_indi.txt`. Không implement, không sửa runtime source, tests, migrations, config hay database schema.

## 1. Hiện trạng TPO indicator

Dựa trên `services/aureus-signal/engine/signals/tpo.py` và `services/aureus-signal/tests/test_tpo_signal.py`, TPO hiện tại đang là indicator nền, chưa phải trade signal.

### Đã có

- `TPOSignal` là `SignalType.INDICATOR`.
- Tính 3 khung TPO:
  - `tpo_d1`: D1 today-only theo mốc ngày UTC-style bằng `now_ts % 86400`.
  - `tpo_h1`: block H1 sliding, lấy block gần nhất trong 6 block gần đây.
  - `tpo_m30`: block M30 sliding, lấy block gần nhất trong 6 block gần đây.
- Mỗi block trả các field đã được test xác nhận:
  - `POC`
  - `VAH`
  - `VAL`
  - `shape`
  - `shape_confidence_pct`
  - `shape_scores_pct`
- `shape` hiện hỗ trợ 4 loại: `D`, `B`, `p`, `b`.
- Có cache cho closed bucket H1/M30 qua `state_obj.tpo_cache`; current bucket vẫn rebuild khi có nến mới.
- `_build_tpo_block` đã được tối ưu theo hướng build counts một lần rồi dùng lại cho profile và shape classification.

### Ý nghĩa hiện tại

Indicator hiện tại đã đủ làm profile engine ban đầu: nó cung cấp vùng giá trị, POC và ngữ cảnh shape cho từng timeframe. Đây là nền tốt để phát triển signal TPO theo hướng trong `tpo_indi.txt`: indicator → feature layer → rule engine → signal → backtest → production.

## 2. Khoảng trống để trở thành signal thực chiến

Các khoảng trống chính chưa nên nhảy thẳng vào lệnh:

### 2.1. Thiếu price relation

Output hiện tại chưa cho biết giá hiện tại đang ở đâu so với `POC/VAH/VAL`:

- `above_vah`
- `inside_upper_va`
- `near_poc`
- `inside_lower_va`
- `below_val`
- reclaimed/breakdown quanh `VAL/VAH`

Không có lớp này thì detector phải tự diễn giải raw levels, dễ trùng logic và sai semantic.

### 2.2. Thiếu `va_width` và profile metadata

Hiện block chỉ có 6 field chính. Để phân biệt balance/expansion cần thêm trong future implementation:

- `va_width = VAH - VAL`
- `range_high`
- `range_low`
- `total_tpos`
- `levels_count`
- `poc_idx` hoặc metadata tương đương nếu cần debug/calibration

### 2.3. Thiếu history để đo shift/transition

`state_obj.tpo_profile` hiện chỉ giữ snapshot hiện tại. Signal TPO cần history theo D1/H1/M30 để đo:

- `poc_shift`: up/down/flat
- `va_expansion` hoặc contraction
- `shape_transition`: ví dụ `D -> p`, `D -> b`
- acceptance/rejection qua nhiều nến

Không có history thì các setup như breakout acceptance, POC slope, balance → imbalance gần như không thể xác nhận chắc chắn.

### 2.4. Thiếu acceptance/rejection state

`tpo_indi.txt` nhấn mạnh cần phân biệt:

- giá acceptance ngoài value area
- rejection quay lại value area
- failed auction quanh VAH/VAL

Hiện indicator chỉ trả snapshot, chưa có state machine hoặc feature để xác định hành vi sau khi giá vượt VAH/VAL.

### 2.5. Thiếu setup detector

Chưa có các detector độc lập như:

- `VARejectionDetector`
- `VABreakoutAcceptanceDetector`
- `TrendPullbackDetector`
- `POCMagnetDetector` (có thể để sau)
- `BalanceImbalanceDetector` (có thể để sau)

### 2.6. Thiếu scorer và strategy template contract

Chưa có lớp tổng hợp để emit các TPO signal tags và chưa có strategy templates tương ứng trong format hiện hành của `services/aureus-signal/engine/strategies/seed_strategies.py`.

Thiết kế TPO strategy không nên tạo contract trade riêng ngoài hệ thống. Nó phải đi qua cùng format seed strategy đang dùng:

```python
{
  "name": "TPO_VA_REJECTION_BULL",
  "is_active": True,
  "description": "...",
  "min_score": 6.0,
  "config": {
    "min_score_threshold": 6.0,
    "context_filters": [{"type": "tpo_context", "setup": "va_rejection"}],
    "sequence": [
      {"tag": "tpo_va_rejection_bull", "weight": 4.0, "required": True, "max_wait": 20, "reset_signals": ["tpo_va_rejection_bear"]}
    ],
    "trade_execution": {
      "direction": "BUY",
      "entry_type": "MARKET",
      "entry_method": "CURRENT",
      "size_mode": "RISK_FIXED_AMOUNT",
      "size_value": 50.0,
      "sl": {"type": "PIVOT_POINT", "offset_pips": 1},
      "tp": {"type": "RR_RATIO", "value": 1.5},
      "trailing": {"type": "BREAKEVEN", "activation_pips": 300},
      "capital_risk_pct": 1.0,
      "early_exits": ["tpo_va_rejection_bear"]
    }
  }
}
```

TPO layer nên emit tags như `tpo_va_rejection_bull/bear`, `tpo_va_breakout_bull/bear`, `tpo_trend_pullback_bull/bear`; strategy engine dùng `context_filters`, `sequence`, `trade_execution` để quyết định entry như các strategy hiện tại.

### 2.7. Thiếu backtest/calibration trước production

Trước khi dùng production cần có replay/backtest theo từng setup để đo:

- winrate
- average R
- expectancy
- MFE/MAE
- số lệnh theo regime
- độ nhạy threshold confidence

## 3. Rủi ro theo `tpo_indi.txt`

### 3.1. Rủi ro overfit shape

`shape` hiện là heuristic classification. Không nên dùng `shape == "D"` hoặc `shape == "p"` như điều kiện vào lệnh độc lập. Shape nên là feature phụ trong scorer, kết hợp với price relation, POC shift, acceptance/rejection và regime.

### 3.2. Rủi ro nhầm indicator với trigger

TPO cho context rất tốt nhưng không tự động là trigger. Trigger vẫn cần xác nhận bằng price action, breakout confirmation hoặc momentum ngắn hơn. Nếu nhồi logic vào `TPOSignal`, indicator sẽ bị lẫn trách nhiệm với strategy signal.

### 3.3. Rủi ro session definition

D1 hiện tính theo UTC-style day boundary. Cách này hợp lý hơn với crypto 24/7, nhưng với futures/chứng khoán hoặc session cụ thể theo exchange có thể làm méo profile, VAH/VAL và signal intraday.

### 3.4. Rủi ro thiếu history

Nếu chỉ dựa vào snapshot hiện tại, signal sẽ không biết POC đang dịch chuyển, value area đang mở rộng/co hẹp, hoặc giá đã acceptance/rejection thật sự chưa. Đây là rủi ro lớn nhất trước khi triển khai detector.

### 3.5. Rủi ro backtest trộn regime

TPO setup phụ thuộc mạnh vào market regime. Nếu backtest không tách trend day/range day/high vol/low vol, kết quả dễ bị nhiễu và threshold dễ overfit.

## 4. Kết luận

Hiện trạng TPO đã đủ tốt để giữ làm profile engine. Bước tiếp theo không nên là vào lệnh trực tiếp, mà nên tạo future implementation theo 4 lớp:

1. `TPOContextBuilder`: chuẩn hóa feature state từ output indicator.
2. Detector library: bắt đầu với 3 setup ít overfit nhất.
3. `TPOStrategySignal`: scorer và conflict resolution.
4. Backtest/calibration: đo edge trước production.

Quick task này chỉ tạo report/plan; runtime source không được chỉnh trong phạm vi này.
