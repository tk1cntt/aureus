# Phase 15.7: Strategy Sequences Enabled but No Entry — Research

## Objective
Làm rõ vì sao strategy có sequence conditions đạt nhưng không tạo được đường đi hoàn chỉnh đến order submission.

## Scope
- Pipeline chính: `on_bar_close` → `validate_entry` → `build_order_plan` → `process_triggers`
- Tập trung vào no-entry/no-order, không thay đổi business rule lớn

## Symptom Decomposition
1. **Checkpoint A (Intent stage):** Không có `intent` từ `on_bar_close`
2. **Checkpoint B (Validation stage):** Có `intent` nhưng bị reject ở `validate_entry`
3. **Checkpoint C (Plan stage):** Qua validate nhưng `build_order_plan` invalid/reject
4. **Checkpoint D (Execution stage):** Có trigger nhưng bị guard tại `process_triggers`

## Key Pipeline Evidence (Current Code)
- `services/aureus-signal/engine/strategies/registry.py`
  - `[PIPELINE][{symbol}][A][on_bar_close][start|no_intent|intent]`
  - `[PIPELINE][{symbol}][B][validate_entry][reject]`
  - `[PIPELINE][{symbol}][C][build_order_plan][invalid_shape|reject|ok|accepted]`
- `services/aureus-signal/engine/orders.py`
  - `[PIPELINE][{symbol}][D][process_triggers][missing_origin_timestamp|duplicate_trace|sl_tp_calc_failed|order_plan_incomplete|new_trade]`
- `services/aureus-signal/engine/strategies/template.py`
  - `reason_code` tại `on_bar_close`: `CONTEXT_FILTER_FAILED` / `SEQUENCE_NOT_MATCHED` / `OK`

## Prioritized Hypotheses
1. **H1 — Context/sequence mismatch:** `SEQUENCE_NOT_MATCHED` dù người vận hành kỳ vọng đã đủ điều kiện.
2. **H2 — Validation rejection:** `validate_entry` fail bởi rule/risk nhưng thiếu correlation theo candle.
3. **H3 — Order-plan incompletion:** thiếu key bắt buộc dẫn tới `ORDER_PLAN_INCOMPLETE`.
4. **H4 — Execution guard skip:** duplicate trace hoặc thiếu `origin_timestamp` gây bỏ trigger.

## Investigation Outputs Required for Planning
- Bảng map checkpoint A/B/C/D theo từng `bar_t` + `strategy_id`
- Danh sách reason_code chủ đạo theo tần suất
- Xác định minimal instrumentation/log additions (nếu cần) và phạm vi fix

## Research Outcome
Phase 15.7 có thể tiến hành theo hướng **diagnosis-first** với replay/trace có cấu trúc, sau đó mới chốt fix path tương ứng từng checkpoint.
