# Phase 15.15: Align strategy with new tags — Research

## Objective
Chuẩn hóa tag taxonomy dùng bởi strategy + AI trigger pipeline để loại bỏ mismatch khi runtime phát tín hiệu.

## Current Evidence

### A) Canonical normalization (`engine/event_policy.py`)
- `_AI_TAG_TO_TRIGGER` map tags runtime (`choch_*`, `bos_*`, `sweep_*`, `ob_*`, `fvg_*`) sang normalized AI events.
- `_TRIGGER_PRIORITY` đảm bảo deterministic ordering khi nhiều tag cùng candle.
- `evaluate_ai_trigger_events(transient_signals)` chỉ đọc `transient_signals.keys()`.

### B) Runtime consumer (`engine/live_engine.py`)
- Mỗi candle, engine gọi:
  - `for ai_event in evaluate_ai_trigger_events(state.transient_signals): state.request_ai_update(ai_event)`
- Nghĩa là nếu tag không nằm trong `_AI_TAG_TO_TRIGGER`, AI pulse trigger bị drop.

### C) Strategy tag usage (`engine/strategies/*.py`)
- `seed_strategies.py` dùng tags như `choch_up`, `sweep_bull` (aligned với mapping hiện tại).
- `smc_trend_scalping.py` còn dùng `sweep_point` (không thấy trong `_AI_TAG_TO_TRIGGER`).

## Drift Risks
1. **Silent no-op trigger**: strategy hoặc signal phát tag ngoài canonical map → không tạo AI trigger.
2. **Template divergence**: DB-seeded templates và hardcoded strategy templates theo 2 naming systems.
3. **Future regression**: thêm tag mới nhưng quên update map + priority + tests.

## Recommended Alignment Model
1. Chốt canonical strategy-facing tag inventory (single source of truth).
2. Áp dụng alias compatibility layer tạm thời cho legacy tags (nếu còn dùng production).
3. Bắt buộc cập nhật đồng bộ 3 điểm mỗi khi thêm tag:
   - `_AI_TAG_TO_TRIGGER`
   - `_TRIGGER_PRIORITY`
   - `tests/test_event_policy.py`

## Verification Targets
- Unit test mapping cho tất cả tags canonical + aliases.
- Unit test priority order không đổi ngoài expected additions.
- Smoke test trong engine loop đảm bảo event được queue khi transient tag xuất hiện.
