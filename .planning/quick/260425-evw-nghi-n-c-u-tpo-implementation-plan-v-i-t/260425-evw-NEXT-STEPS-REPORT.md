# Báo cáo bước tiếp theo để implement TPO theo chuẩn GSD

## Mục tiêu

Lưu lại khuyến nghị về bước tiếp theo để triển khai Signal TPO theo kế hoạch hiện có tại:

- `.planning/quick/260425-ekl-l-n-k-hoa-ch-tri-n-khai-signal-tpo-theo-/260425-ekl-TPO-IMPLEMENTATION-PLAN.md`

Báo cáo này chỉ là tài liệu điều hướng triển khai. Chưa implement runtime code, chưa sửa tests, migrations, config hoặc database schema.

## Kết luận ngắn

Không nên nhảy thẳng vào toàn bộ Signal TPO trong một lần. Theo chuẩn GSD, nên triển khai theo từng slice nhỏ, có validation rõ ràng.

Bước tiếp theo được khuyến nghị nhất:

```text
/gsd:quick --validate Implement TPOContextBuilder foundation from .planning/quick/260425-ekl-l-n-k-hoa-ch-tri-n-khai-signal-tpo-theo-/260425-ekl-TPO-IMPLEMENTATION-PLAN.md. Create context layer only, with tests for price location, va_width, missing timeframe blocks, and no trade signal emission. Keep TPOSignal as indicator and do not change database/schema.
```

Lý do: đây là slice nền nhỏ nhất, ít rủi ro nhất, giúp chuẩn hóa raw TPO indicator thành context có semantic rõ ràng trước khi thêm history, detector, strategy bridge hoặc backtest.

## Vì sao không nên implement toàn bộ ngay

Signal TPO hiện là một kế hoạch lớn gồm nhiều lớp:

1. `TPOContextBuilder`
2. TPO history store
3. Detector library
4. Strategy tag bridge
5. Seed strategy templates
6. Replay/backtest/calibration
7. Production readiness

Nếu implement toàn bộ trong một task sẽ có các rủi ro:

- Khó verify từng lớp độc lập.
- Dễ nhồi trade logic vào `TPOSignal`, làm mất vai trò indicator nền.
- Dễ tạo strategy contract riêng, lệch khỏi `seed_strategies.py`.
- Khó kiểm soát overfit threshold.
- Khó debug khi signal tag sai vì context/history/detector/scorer cùng thay đổi.

Vì vậy nên dùng GSD quick `--validate` cho từng slice nhỏ, hoặc tạo phase chính thức nếu muốn gom thành roadmap work lớn.

## Lộ trình đề xuất

### Slice 1 — TPOContextBuilder foundation

Mục tiêu:

- Tạo lớp context/feature để diễn giải output hiện tại của `TPOSignal`.
- Không emit trade signal.
- Không sửa database/schema.
- Giữ `TPOSignal` là indicator.

File dự kiến:

- Tạo mới: `services/aureus-signal/engine/signals/tpo_context.py`
- Test: `services/aureus-signal/tests/test_tpo_context.py`

Context fields nên bắt đầu tối thiểu:

- `price_location` theo từng timeframe.
- distance tới `POC`, `VAH`, `VAL`.
- `va_width = VAH - VAL`.
- safe handling khi D1/H1/M30 block bị thiếu.

Test cần có:

- `close > VAH` → `above_vah`.
- `close < VAL` → `below_val`.
- close gần `POC` → `near_poc`.
- `VAH - VAL` → `va_width`.
- D1/H1/M30 missing block không crash.
- Không emit trade tag.

GSD command đề xuất:

```text
/gsd:quick --validate Implement TPOContextBuilder foundation from .planning/quick/260425-ekl-l-n-k-hoa-ch-tri-n-khai-signal-tpo-theo-/260425-ekl-TPO-IMPLEMENTATION-PLAN.md. Create context layer only, with tests for price location, va_width, missing timeframe blocks, and no trade signal emission. Keep TPOSignal as indicator and do not change database/schema.
```

### Slice 2 — TPO history store

Mục tiêu:

- Lưu history tối thiểu cho D1/H1/M30.
- Không append duplicate cùng timestamp/timeframe.
- Giới hạn length để tránh memory growth.
- Tính được `poc_shift`, `va_width_change`, `shape_transition`.
- Có safeguard cho stale/misaligned multi-timeframe context.

File dự kiến:

- Có thể tạo: `services/aureus-signal/engine/signals/tpo_history.py`
- Có thể sửa nhẹ: `services/aureus-signal/engine/signals/tpo.py`
- Test: `services/aureus-signal/tests/test_tpo_history.py`

GSD command đề xuất:

```text
/gsd:quick --validate Implement TPO history store from TPO plan. Add bounded D1/H1/M30 history, duplicate prevention, poc_shift/va_width_change helpers, stale context safeguards, and unit tests.
```

### Slice 3 — Detector đầu tiên: VARejectionDetector

Mục tiêu:

- Implement detector đầu tiên, chưa làm toàn bộ detector library.
- Detector nhận context từ `TPOContextBuilder`.
- Output candidate có `setup`, `side`, `valid`, `score`, `entry_zone`, `invalidation`, `reasons`.
- Không vào lệnh trực tiếp.
- Không dùng shape làm gate duy nhất.

File dự kiến:

- Tạo mới: `services/aureus-signal/engine/signals/tpo_detectors.py`
- Test: `services/aureus-signal/tests/test_tpo_detectors.py`

Test cần có:

- Long valid.
- Short valid.
- Invalid khi thiếu context.
- Invalid khi conflict long/short.
- `reasons` đủ debug.

GSD command đề xuất:

```text
/gsd:quick --validate Implement first TPO detector: VARejectionDetector only. It must consume TPOContextBuilder output, emit candidate/reasons, avoid shape-only gating, reject missing/conflicting context, and include unit tests.
```

### Slice 4 — Các detector còn lại

Sau khi `VARejectionDetector` ổn, triển khai tiếp:

- `VABreakoutAcceptanceDetector`
- `TrendPullbackDetector`

GSD command đề xuất:

```text
/gsd:quick --validate Implement remaining deterministic TPO detectors: VABreakoutAcceptanceDetector and TrendPullbackDetector, with long/short/invalid tests, conflict handling, and reasons metadata.
```

### Slice 5 — Strategy tag bridge + seed strategy templates

Chỉ làm sau khi detector đã có test.

Mục tiêu:

- Tạo scorer/bridge để emit tags cho strategy engine.
- Không tạo final trade contract riêng.
- Strategy templates phải tuân theo `services/aureus-signal/engine/strategies/seed_strategies.py`.

Signal tags dự kiến:

- `tpo_va_rejection_bull`
- `tpo_va_rejection_bear`
- `tpo_va_breakout_bull`
- `tpo_va_breakout_bear`
- `tpo_trend_pullback_bull`
- `tpo_trend_pullback_bear`

Seed templates dự kiến:

- `TPO_VA_REJECTION_BULL`
- `TPO_VA_REJECTION_BEAR`
- `TPO_VA_BREAKOUT_BULL`
- `TPO_VA_BREAKOUT_BEAR`
- `TPO_TREND_PULLBACK_BULL`
- `TPO_TREND_PULLBACK_BEAR`

Test cần có:

- Emit đúng tag bull/bear.
- Score thấp không emit tag.
- Conflict long/short không emit trade tag.
- Seed strategy templates đủ top-level fields: `name`, `is_active`, `description`, `min_score`, `config`.
- `config` đủ: `min_score_threshold`, `context_filters`, `sequence`, `trade_execution`.
- `sequence` item đủ: `tag`, `weight`, `required`, `max_wait`, `reset_signals`.
- `trade_execution` đủ fields theo convention hiện tại.

GSD command đề xuất:

```text
/gsd:quick --validate Implement TPO strategy tag bridge and seed strategy templates. Emit TPO tags for tested detectors, add seed strategies following seed_strategies.py contract, and add contract tests to prevent drift.
```

### Slice 6 — Replay/backtest/calibration

Mục tiêu:

- Chưa bật production.
- Có replay deterministic.
- Có report để đo edge trước khi dùng live.

Metrics cần đo:

- Số setup theo loại.
- Winrate.
- Average R.
- Expectancy.
- MFE/MAE nếu có đủ dữ liệu.
- Distribution theo regime.
- Sensitivity theo confidence/threshold.

GSD command đề xuất:

```text
/gsd:quick --validate Add deterministic replay/backtest harness for TPO signal calibration. It must not change production behavior and must report setup counts, regime breakdown, and threshold sensitivity.
```

## Khi nào nên tạo phase thay vì quick

Nên dùng quick `--validate` nếu mỗi lần chỉ làm một slice nhỏ.

Nên tạo phase chính thức nếu muốn gom nhiều slice thành một workstream lớn, ví dụ:

- Phase name: `TPO Signal Foundation`
- Slug: `tpo-signal-foundation`

Phase có thể chia thành các plan:

1. Context builder
2. History store
3. Detectors
4. Strategy bridge
5. Replay/calibration

Tuy nhiên, khuyến nghị hiện tại là bắt đầu bằng quick `--validate` cho Slice 1. Sau khi Slice 1 và Slice 2 ổn, có thể cân nhắc tạo phase chính thức cho detector + strategy bridge + backtest.

## Lưu ý bắt buộc theo repo rules

Khi bắt đầu implement code:

- Trước khi sửa symbol/function/class phải chạy GitNexus impact analysis.
- Nếu sửa `TPOSignal`, phải impact `TPOSignal` hoặc method cụ thể như `_build_tpo_block` trước.
- Nếu sửa `seed_system_strategies`, phải impact trước vì liên quan strategy seed DB.
- Nếu có persistence database mới, phải có e2e test với database thật theo `CLAUDE.md`.
- Không sửa schema database trong các slice đầu nếu chưa cần.
- Không production TPO signal nếu chưa có replay/backtest/calibration.
- Không dùng `shape` làm trigger độc lập.
- Strategy TPO phải đi qua `context_filters` + `sequence` + `trade_execution`, không tạo final trade contract riêng.

## Recommendation cuối cùng

Bước tiếp theo nên chạy:

```text
/gsd:quick --validate Implement TPOContextBuilder foundation from .planning/quick/260425-ekl-l-n-k-hoa-ch-tri-n-khai-signal-tpo-theo-/260425-ekl-TPO-IMPLEMENTATION-PLAN.md. Create context layer only, with tests for price location, va_width, missing timeframe blocks, and no trade signal emission. Keep TPOSignal as indicator and do not change database/schema.
```

Đây là bước nhỏ nhất, đúng process GSD, có validation, ít rủi ro, và là nền bắt buộc trước khi triển khai history, detectors, strategy bridge hoặc backtest.
