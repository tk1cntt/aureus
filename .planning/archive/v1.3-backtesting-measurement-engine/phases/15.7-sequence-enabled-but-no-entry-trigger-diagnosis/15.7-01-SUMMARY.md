---
phase: 15.7-sequence-enabled-but-no-entry-trigger-diagnosis
plan: "01"
subsystem: strategy-entry-diagnosis
tags: [pipeline, no-entry, sequence, observability]
requires:
  - phase: 15.7
    provides: Planning context and checkpoint scope
provides:
  - Static checkpoint evidence map for A/B/C/D
  - Root-cause candidates prioritized by earliest rejection point
  - Focused fix-input proposals for next execution wave
affects: [strategy-registry, template-strategy, order-processing, live-engine, backtest-engine]
key-files:
  modified:
    - .planning/phases/15.7-sequence-enabled-but-no-entry-trigger-diagnosis/15.7-01-SUMMARY.md
requirements-completed: [INTERNAL-ENTRY-GATING-OBSERVABILITY]
completed: 2026-03-24
---

# Phase 15.7 Plan 01 — Execution Summary

## Scope Executed
Thực hiện diagnosis tĩnh theo checkpoint pipeline:
- **A**: `on_bar_close` intent emission
- **B**: `validate_entry` gate rejection
- **C**: `build_order_plan` acceptance/rejection
- **D**: `process_triggers` execution guards

## Checkpoint Findings

### A — Intent emission (`registry.py`, `template.py`)
- Registry đã log rõ `start`, `no_intent`, `intent` với `strategy_id` + `bar_t`.
- Với `TemplateStrategy`, `intent` có thể tồn tại nhưng `is_actionable=false` khi sequence/context chưa đạt.
- Phân biệt chính tại intent layer:
  - `SEQUENCE_NOT_MATCHED`
  - `CONTEXT_FILTER_FAILED`
  - `OK`

### B — Validation rejection (`registry.py`, `template.py`, `base.py`)
- `validate_entry` reject path được log tập trung tại `[PIPELINE][B][validate_entry][reject]`.
- Template strategy reject chính:
  - `NO_INTENT` (intent missing)
  - `BACKFILL_NOT_READY`
  - `SEQUENCE_NOT_MATCHED` (intent không actionable)
- Registry lưu `failed_rules` + `evaluated_rules` vào rejection buffer để downstream correlation.

### C — Order-plan construction (`registry.py`, `template.py`)
- Registry reject nếu `build_order_plan` trả non-dict (`ORDER_PLAN_INVALID_SHAPE`).
- Registry reject nếu `order_plan.reason_code != OK`.
- Plan hợp lệ được emit accepted decision với `origin_timestamp`, `side`, `entry_type`, `size`, `sl/tp`...

### D — Trigger execution guards (`orders.py`, `live_engine.py`, `backtest_engine.py`)
- Guard skip tại `process_triggers` gồm:
  - `missing_origin_timestamp`
  - `duplicate_trace`
  - `sl_tp_calc_failed`
  - `order_plan_incomplete` (emit `ORDER_REJECTED` stream event)
- `live_engine` chỉ gọi `process_triggers` khi có accepted decisions; do đó no-entry có thể dừng ở A/B/C trước khi đến D.
- `backtest_engine` có luồng tương tự nhưng dùng `SimulatedTradeManager` riêng cho replay context.

## Earliest-Failure Decision Ladder (for triage)
1. Không có `[A][intent]`  → kiểm tra sequence/context matching tại strategy
2. Có `[A][intent]` nhưng có `[B][reject]` → kiểm tra `failed_rules`/`evaluated_rules`
3. Qua B nhưng có `[C][reject]` → kiểm tra `reason_code` từ order-plan
4. Qua C nhưng không có order mở → kiểm tra `[D]` guard logs và stream `ORDER_REJECTED`

## Fix-Input Recommendations (next actionable step)
1. **Correlation key chuẩn hóa**: đảm bảo mọi reject payload A/B/C/D chứa đủ `strategy_id`, `intent_id`, `bar_t`, `origin_timestamp`.
2. **Checkpoint matrix emitter**: bổ sung lightweight diagnostic aggregation theo candle để gom A→D trong một record triage.
3. **Targeted replay case**: chạy 1 case sequence-enabled-but-no-entry với capture logs theo prefix `[PIPELINE]` để chốt checkpoint đầu tiên.

## Verification Evidence Captured
- `Get-ChildItem ".planning/phases/15.7-sequence-enabled-but-no-entry-trigger-diagnosis/*"`
- `node ".agent/get-shit-done/bin/gsd-tools.cjs" phase-plan-index "15.7"`
- `node ".agent/get-shit-done/bin/gsd-tools.cjs" init execute-phase "15.7"`

## Deviations
- CLI hiện tại không có command `execute-phase` trực tiếp; thực thi theo cơ chế manual execution theo plan artifacts.
- Không thay đổi runtime code ở phase này; output là diagnosis + fix-input.
