# Kế hoạch triển khai future Signal TPO

## Nguyên tắc phạm vi

Tài liệu này là kế hoạch cho future implementation. Quick task `260425-ekl` không implement runtime code, không sửa tests, migrations, config hoặc database.

## Mục tiêu kiến trúc

Triển khai theo pipeline:

```text
TPOSignal indicator → TPO feature/context layer → setup rule engine → strategy signal → backtest/calibration → production
```

Nguyên tắc quan trọng: giữ `TPOSignal` là indicator gốc, không nhồi logic vào lệnh vào class này.

## Independent Architecture Review

### Step 1 — Neutral Listing

Các phương án kiến trúc phổ biến để triển khai TPO signal từ indicator:

| Phương án | Đặc điểm kỹ thuật thuần túy |
|---|---|
| Monolithic indicator-driven signal | Mở rộng trực tiếp `TPOSignal` để vừa tính profile, vừa phát hiện setup, vừa emit trade-oriented signal. Context, detector, scorer và output signal cùng nằm gần logic indicator. |
| Feature/context layer + rule detectors + scorer/strategy bridge | Giữ `TPOSignal` là indicator facts. Thêm `TPOContextBuilder` để chuẩn hóa price relation/history, detector deterministic để tạo setup candidates, scorer/bridge để emit TPO tags vào strategy engine hiện hữu. |
| Pure strategy-template gating | Không tạo detector riêng đáng kể. Chủ yếu thêm `context_filters` và `sequence` trong `seed_strategies.py`, để strategy engine quyết định matching từ các indicator/context fields đã có. |
| ML/statistical classifier từ TPO features | Sinh feature vector từ TPO profile/history/price action, huấn luyện classifier hoặc statistical model để dự đoán setup/side/confidence. Runtime load model và emit tag/score theo inference. |
| External/backtest-first research module | Tách TPO analysis khỏi runtime signal path ban đầu. Script/replay module đọc dữ liệu lịch sử, sinh report/threshold/calibration; chỉ promote rule đã kiểm chứng vào runtime sau. |

### Step 2 — Attribute Mapping

| Tiêu chí | Mạnh nhất về mặt kỹ thuật | Trade-off chính |
|---|---|---|
| Tốc độ thực thi/runtime cost | Monolithic indicator-driven signal hoặc pure strategy-template gating | Monolithic ít lớp trung gian nhưng tăng coupling vào `TPOSignal`; pure gating nhẹ runtime nhưng thiếu detector state rõ nghĩa và dễ dồn semantic phức tạp vào filter. |
| Latency trong signal service Python | Monolithic nếu chỉ dùng dữ liệu đã tính sẵn; pure gating nếu filter đơn giản | Đổi lại mất khả năng test độc lập context/detector; khi rule phức tạp hơn, latency có thể tăng khó kiểm soát vì logic nằm lẫn trong indicator hoặc strategy matching. |
| Maintainability | Feature/context layer + rule detectors + scorer/strategy bridge | Có thêm file/lớp cần quản lý, nhưng boundary rõ: indicator facts, context semantics, detector candidates, strategy tags. |
| Tích hợp với `seed_strategies.py` | Feature/context layer + scorer/strategy bridge hoặc pure strategy-template gating | Pure gating khớp trực tiếp seed strategy nhưng thiếu thư viện detector; feature bridge cần thêm tag/context contract nhưng vẫn giữ `context_filters` + `sequence` + `trade_execution`. |
| Testability | Feature/context layer + rule detectors + external/backtest-first module | Cần viết nhiều test hơn, nhưng có thể test context, history, detector, scorer, seed strategy contract và replay riêng biệt. |
| Rủi ro overfit | External/backtest-first module thấp nhất ở giai đoạn nghiên cứu; deterministic rule detectors thấp nếu có calibration | ML classifier và detector threshold đều có thể overfit nếu không split train/validation theo thời gian. Monolithic dễ che giấu overfit vì signal logic lẫn indicator. |
| Độ phức tạp rollout | Pure strategy-template gating thấp nhất; feature/context + detector ở mức trung bình | Pure gating nhanh nhưng có thể thiếu edge/observability. Feature bridge rollout chậm hơn nhưng có guardrails trước production. |
| Observability/debug reasons | Feature/context layer + rule detectors + scorer/strategy bridge | Phải thiết kế `reasons`/metadata ngay từ đầu. Monolithic hoặc ML classifier dễ khó giải thích nếu không ép contract debug. |

Trade-off cụ thể:

- Chọn monolithic thay vì feature/context layer sẽ được runtime path ngắn hơn, nhưng mất separation of concerns và làm `TPOSignal` khó giữ vai trò indicator nền.
- Chọn pure strategy-template gating thay vì detector library sẽ giảm số file mới, nhưng mất khả năng biểu diễn acceptance/rejection state, stale multi-timeframe context và conflict resolution một cách testable.
- Chọn ML/statistical classifier thay vì deterministic detectors sẽ có khả năng bắt quan hệ phi tuyến tốt hơn, nhưng mất explainability, tăng yêu cầu data labeling/backtest và khó kiểm soát contract strategy.
- Chọn external/backtest-first module thay vì runtime detector ngay sẽ giảm rủi ro production sớm, nhưng chưa cung cấp signal live cho strategy engine cho đến khi promote rule đã calibration.

### Step 3 — Contextual Recommendation

Với context Aureus hiện tại, lựa chọn tối ưu là **Feature/context layer + deterministic rule detectors + scorer/strategy bridge**, kết hợp backtest/calibration trước production.

Lý do:

- Hệ thống hiện tại đã có signal service Python và `TPOSignal` đang là `SignalType.INDICATOR`; giữ indicator thuần giúp tránh phá profile engine đã có.
- Strategy activation hiện phải đi qua format seed strategy trong `services/aureus-signal/engine/strategies/seed_strategies.py`, nên TPO runtime nên emit tags để `context_filters` + `sequence` + `trade_execution` xử lý entry, không tạo final trade contract riêng.
- TPO setup phụ thuộc nhiều vào price relation, history, acceptance/rejection và conflict timeframe; các phần này cần test độc lập hơn là nhồi vào template hoặc indicator.
- Deterministic detectors có thể tạo `reasons` rõ ràng cho Telegram/log/replay, phù hợp yêu cầu ổn định và kiểm toán edge trước production.

Giới hạn bắt buộc của khuyến nghị:

- Không deploy production nếu chưa có replay/backtest và calibration threshold.
- Không dùng `shape` làm gate duy nhất; shape chỉ là feature cộng điểm hoặc context phụ.
- Không tạo output strategy contract riêng ngoài `context_filters` + `sequence` + `trade_execution`.
- Không thêm persistence database nếu chưa có plan riêng; nếu có persistence mới thì phải có e2e test với database theo `CLAUDE.md`.

### Step 4 — Adversarial Mode

Giả sử chọn Feature/context layer + deterministic rule detectors + scorer/strategy bridge, các kịch bản fail cần tấn công trước:

| Fail scenario / rủi ro kiến trúc | Cách thất bại cụ thể | Mitigation bắt buộc |
|---|---|---|
| Stale hoặc misaligned multi-timeframe TPO context | D1/H1/M30 được build từ mốc thời gian khác nhau; detector đọc H1 mới nhưng D1/H1/M30 history chưa đồng bộ, dẫn tới signal reclaim/breakout sai. | Context builder phải ghi timestamp/source bucket cho từng timeframe; detector phải reject khi context stale hoặc thiếu timeframe bắt buộc; test stale/misaligned D1/H1/M30. |
| Detector threshold overfit/false edge | Rule như `near_poc`, acceptance 1-2 nến, confidence shape được tune trên một đoạn dữ liệu nhỏ và fail ở regime khác. | Backtest split train/validation theo thời gian, report theo regime/symbol/timeframe, không production nếu threshold chưa calibration; threshold phải config/calibration-driven thay vì hardcode tùy tiện. |
| Runtime/cache/memory growth hoặc duplicate history | TPO history append trùng timestamp/timeframe hoặc không giới hạn length, làm memory tăng và shift calculation sai. | History store phải limit length, chống duplicate cùng timestamp/timeframe, có test append/dedup/limit và verify current bucket không làm bẩn closed bucket cache. |
| Contract drift với seed strategies | TPO strategy template thêm field riêng hoặc thiếu `sequence.reset_signals`/`trade_execution` fields, làm strategy engine match sai hoặc khó seed/upsert. | Test seed strategy TPO phải assert đủ top-level/config/sequence/trade_execution fields theo `seed_strategies.py`; không cho final trade contract riêng bypass engine. |
| Observability/replay không đủ để debug | Signal tag được emit nhưng không có `reasons`, không biết detector nào thắng, conflict nào bị loại, hoặc snapshot nào tạo ra score. | Detector/scorer phải emit debug metadata/reasons; replay phải deterministic và tái tạo được quyết định từ cùng input candles/context. |

### Final Recommendation

Lựa chọn tốt nhất là triển khai theo pipeline hiện có: `TPOSignal indicator → TPO feature/context layer → deterministic detectors → scorer/strategy bridge → seed strategy templates → replay/backtest/calibration → production`.

Điểm khác biệt quan trọng là phải coi các guardrails từ Adversarial Mode là yêu cầu thực thi và kiểm thử bắt buộc: chống stale multi-timeframe context, chống overfit threshold, giới hạn history/cache, giữ contract seed strategy, và đảm bảo observability/replay trước production.

## Strategy template contract bắt buộc

Khi triển khai TPO thành strategy, phần design **phải tuân theo format seed strategy hiện hành** trong `services/aureus-signal/engine/strategies/seed_strategies.py`. Không tạo output strategy contract tự do tách khỏi hệ thống hiện có.

Mỗi TPO strategy template cần theo cấu trúc:

```python
{
    "name": "TPO_VA_REJECTION_BULL",
    "is_active": True,
    "description": "BUY khi giá reject/reclaim VAL theo TPO context, có xác nhận trigger bullish.",
    "min_score": 6.0,
    "config": {
        "min_score_threshold": 6.0,
        "context_filters": [
            {
                "type": "tpo_context",
                "setup": "va_rejection",
                "required_direction": "bullish",
                "timeframes": ["d1", "h1", "m30"],
                "price_location": ["below_val_reclaimed", "inside_lower_va"],
                "d1_bias": ["bullish", "neutral"],
                "shape_preference": ["D", "B", "p"],
                "min_confidence_pct": 55
            }
        ],
        "sequence": [
            {"tag": "tpo_va_rejection_bull", "weight": 4.0, "required": True, "max_wait": 20, "reset_signals": ["tpo_va_rejection_bear", "choch_down"]},
            {"tag": "choch_up", "weight": 2.0, "required": False, "max_wait": 20, "reset_signals": ["choch_down"]}
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
            "early_exits": ["tpo_va_rejection_bear", "choch_down"]
        }
    }
}
```

Các field bắt buộc phải giữ đồng bộ với seed strategies hiện có:

- top-level: `name`, `is_active`, `description`, `min_score`, `config`
- `config.min_score_threshold`
- `config.context_filters`
- `config.sequence`
- `config.trade_execution`
- trong `sequence`: `tag`, `weight`, `required`, `max_wait`, `reset_signals`
- trong `trade_execution`: `direction`, `entry_type`, `entry_method`, `size_mode`, `size_value`, `sl`, `tp`, `trailing`, `capital_risk_pct`, `early_exits`

TPO implementation có thể sinh các signal tag mới như `tpo_va_rejection_bull`, `tpo_va_rejection_bear`, `tpo_va_breakout_bull`, `tpo_va_breakout_bear`, nhưng strategy activation/entry phải đi qua `sequence` + `context_filters` + `trade_execution` giống các strategy seed hiện hành.

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

## Slice 4 — TPO strategy seed templates + scorer alignment

### Mục tiêu

Tổng hợp detector output thành các signal tags phù hợp với strategy engine hiện tại, sau đó thiết kế TPO strategy templates theo đúng format `seed_strategies.py`. Không sinh final trade contract riêng ngoài hệ thống `context_filters` + `sequence` + `trade_execution`.

### File dự kiến sẽ sửa/tạo trong future implementation

- Tạo mới: `services/aureus-signal/engine/signals/tpo_strategy.py` hoặc detector/scorer tương đương để emit signal tags.
- Sửa: `services/aureus-signal/engine/strategies/seed_strategies.py` để thêm TPO strategy templates theo format hiện hành.
- Có thể cập nhật registry signal nếu project có cơ chế đăng ký signal.
- Test: `services/aureus-signal/tests/test_tpo_strategy_signal.py`
- Test: `services/aureus-signal/tests/test_seed_strategies_tpo.py` nếu chưa có coverage seed strategy template.

### Signal tags đề xuất

Detector/scorer chỉ nên emit các tag rõ nghĩa để strategy template dùng trong `sequence`:

- `tpo_va_rejection_bull`
- `tpo_va_rejection_bear`
- `tpo_va_breakout_bull`
- `tpo_va_breakout_bear`
- `tpo_trend_pullback_bull`
- `tpo_trend_pullback_bear`

Mỗi tag nên mang metadata/debug context trong signal snapshot, nhưng strategy matching vẫn phải dựa trên `tag`, `weight`, `required`, `max_wait`, `reset_signals` giống các strategy hiện có.

### Strategy templates đề xuất

Future implementation nên thêm tối thiểu 6 templates theo cặp bull/bear:

1. `TPO_VA_REJECTION_BULL`
2. `TPO_VA_REJECTION_BEAR`
3. `TPO_VA_BREAKOUT_BULL`
4. `TPO_VA_BREAKOUT_BEAR`
5. `TPO_TREND_PULLBACK_BULL`
6. `TPO_TREND_PULLBACK_BEAR`

Mỗi template phải có:

- `name`: uppercase snake case, ngắn gọn.
- `is_active`: mặc định `True` hoặc theo quyết định rollout.
- `description`: mô tả setup và sequence.
- `min_score`: khớp với tổng weight/min threshold.
- `config.min_score_threshold`: cùng semantic với các seed strategy hiện tại.
- `config.context_filters`: dùng filter type mới `tpo_context` để kiểm D1/H1/M30 context.
- `config.sequence`: chứa TPO tag chính, có thể thêm CHOCH/CISD/EMA tag phụ nếu muốn xác nhận entry.
- `config.trade_execution`: giữ format hiện tại (`direction`, `entry_type`, `entry_method`, `size_mode`, `size_value`, `sl`, `tp`, `trailing`, `capital_risk_pct`, `early_exits`).

### Example seed templates

```python
{
    "name": "TPO_VA_REJECTION_BULL",
    "is_active": True,
    "description": "BUY khi TPO xác nhận reclaim/rejection quanh VAL, có thể xác nhận thêm CHOCH bullish.",
    "min_score": 6.0,
    "config": {
        "min_score_threshold": 6.0,
        "context_filters": [
            {
                "type": "tpo_context",
                "setup": "va_rejection",
                "required_direction": "bullish",
                "timeframes": ["d1", "h1", "m30"],
                "price_location": ["below_val_reclaimed", "inside_lower_va"],
                "d1_bias": ["bullish", "neutral"],
                "min_confidence_pct": 55
            }
        ],
        "sequence": [
            {"tag": "tpo_va_rejection_bull", "weight": 4.0, "required": True, "max_wait": 20, "reset_signals": ["tpo_va_rejection_bear", "choch_down"]},
            {"tag": "choch_up", "weight": 2.0, "required": False, "max_wait": 20, "reset_signals": ["choch_down"]}
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
            "early_exits": ["tpo_va_rejection_bear", "choch_down"]
        }
    }
}
```

Bear template phải đối xứng:

- `required_direction`: `bearish`
- `sequence.tag`: `tpo_va_rejection_bear`
- optional confirmation: `choch_down`
- `trade_execution.direction`: `SELL`
- trailing/SL semantic dùng `SWING_HIGH` hoặc existing convention phù hợp.

### Scoring gợi ý trong signal layer

- D1 context cùng chiều: +15 đến +20.
- H1 price relation rõ ràng: +15 đến +25.
- M30 trigger/reclaim: +20 đến +30.
- POC shift cùng chiều: +10 đến +15.
- Shape hỗ trợ: +5 đến +10.
- Conflict timeframe: trừ điểm hoặc không emit tag.

Mapping v1:

- score đủ threshold detector → emit TPO tag tương ứng.
- score dưới threshold → không emit tag hoặc emit debug-only indicator, không đưa vào `sequence`.
- conflict long/short → không emit trade tag.

### Test dự kiến trước khi implement

- TPO signal layer emit đúng tag bull/bear theo detector context.
- Không emit tag khi score dưới threshold.
- Conflict long/short không emit trade tag.
- Seed strategy templates TPO có đủ top-level keys `name`, `is_active`, `description`, `min_score`, `config`.
- `config` của mỗi template có đủ `min_score_threshold`, `context_filters`, `sequence`, `trade_execution`.
- `sequence` item có đủ `tag`, `weight`, `required`, `max_wait`, `reset_signals`.
- `trade_execution` có đủ các field theo convention seed hiện tại.

### Tiêu chí không overfit

- Threshold detector phải được xác nhận bằng backtest/calibration trước production.
- Không tối ưu riêng cho một symbol/timeframe.
- `shape` chỉ là feature cộng điểm/context filter phụ, không là gate duy nhất.
- Strategy template phải vẫn dùng confirmation signal hiện hữu như CHOCH/CISD nếu backtest cho thấy TPO tag đơn lẻ nhiễu.

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
- Replay/backtest deterministic với cùng input data và có split train/validation theo thời gian.
- Output signal có contract ổn định.
- Seed strategy templates TPO không contract drift khỏi fields hiện hữu trong `seed_strategies.py`.
- Detector có `reasons` đủ để debug Telegram/log/replay.
- Detector không emit trade tag khi conflict long/short hoặc thiếu context bắt buộc.
- History/cache có giới hạn length, không duplicate cùng timestamp/timeframe, và xử lý stale/misaligned D1/H1/M30.
- Không dùng shape như trigger đơn độc.
- Không deploy production nếu chưa có calibration threshold.
- Nếu future implementation thêm persistence database, phải có e2e test với database theo `CLAUDE.md`.
