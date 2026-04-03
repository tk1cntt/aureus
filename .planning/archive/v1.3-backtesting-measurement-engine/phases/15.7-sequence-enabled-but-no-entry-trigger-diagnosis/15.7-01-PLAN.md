---
phase: "15.7"
plan: "01"
title: "Diagnose No-Entry Path Despite Enabled Strategy Sequences"
wave: 1
depends_on: []
files_modified:
  - .planning/phases/15.7-sequence-enabled-but-no-entry-trigger-diagnosis/15.7-CONTEXT.md
  - .planning/phases/15.7-sequence-enabled-but-no-entry-trigger-diagnosis/15.7-RESEARCH.md
  - .planning/phases/15.7-sequence-enabled-but-no-entry-trigger-diagnosis/15.7-VALIDATION.md
  - services/aureus-signal/engine/strategies/registry.py
  - services/aureus-signal/engine/strategies/template.py
  - services/aureus-signal/engine/orders.py
  - services/aureus-signal/engine/live_engine.py
autonomous: true
requirements_addressed: [INTERNAL-ENTRY-GATING-OBSERVABILITY]
---

<objective>
Xác định checkpoint đầu tiên gây no-entry khi sequence conditions được bật/đạt, bằng cách phân tách rõ 4 lớp pipeline: A (`on_bar_close`), B (`validate_entry`), C (`build_order_plan`), D (`process_triggers`).
</objective>

<must_haves>
- Có evidence checklist cho từng checkpoint A/B/C/D
- Có ma trận reason_code và rejection-path theo `strategy_id` + `bar_t`
- Có đề xuất fix scope nhỏ, không mở rộng ngoài no-entry diagnosis boundary
- Plan discoverable cho `/gsd-execute-phase 15.7`
</must_haves>

---

<task id="15.7-01-T1" title="Baseline evidence mapping for checkpoint A and reason-code surface">
<read_first>
- services/aureus-signal/engine/strategies/registry.py
- services/aureus-signal/engine/strategies/template.py
- .planning/phases/15.7-sequence-enabled-but-no-entry-trigger-diagnosis/15.7-CONTEXT.md
- .planning/phases/15.7-sequence-enabled-but-no-entry-trigger-diagnosis/15.7-RESEARCH.md
</read_first>

<action>
Thiết lập baseline diagnosis cho checkpoint A:
1. Xác nhận các event `on_bar_close` đã có log prefix nhất quán (`start/no_intent/intent`).
2. Tách rõ trường hợp `SEQUENCE_NOT_MATCHED` vs `CONTEXT_FILTER_FAILED` vs `OK`.
3. Chuẩn bị format evidence tối thiểu cho mỗi candle: `bar_t`, `strategy_id`, `intent_id`, `reason_code`, `is_actionable`.
</action>

<acceptance_criteria>
- Có bảng mapping checkpoint A cho ít nhất một replay/live trace
- Có phân loại được nguyên nhân không có intent hoặc intent không actionable
- Không có thay đổi business rule strategy trong bước baseline
</acceptance_criteria>
</task>

<task id="15.7-01-T2" title="Diagnose validation gate failures at checkpoint B">
<read_first>
- services/aureus-signal/engine/strategies/registry.py
- services/aureus-signal/engine/strategies/base.py
- services/aureus-signal/engine/strategies/template.py
- .planning/phases/15.7-sequence-enabled-but-no-entry-trigger-diagnosis/15.7-VALIDATION.md
</read_first>

<action>
Khoanh vùng reject tại `validate_entry`:
1. Thu thập `failed_rules`, `evaluated_rules`, `reason_code` cho mỗi reject.
2. Liên kết reject với intent nguồn cùng `intent_id`.
3. Chốt nhóm reject nào là expected guard vs bất thường cần fix.
</action>

<acceptance_criteria>
- Có danh sách reason_code checkpoint B theo tần suất
- Mỗi reject có thể truy ngược về intent gốc
- Đề xuất rõ phần cần instrument thêm nếu dữ liệu hiện tại chưa đủ
</acceptance_criteria>
</task>

<task id="15.7-01-T3" title="Diagnose order-plan and execution guards at checkpoints C/D and prepare fix-input">
<read_first>
- services/aureus-signal/engine/strategies/registry.py
- services/aureus-signal/engine/orders.py
- services/aureus-signal/engine/live_engine.py
- .planning/phases/15.7-sequence-enabled-but-no-entry-trigger-diagnosis/15.7-VALIDATION.md
</read_first>

<action>
Phân tích phần cuối pipeline trước khi order submission:
1. Xác định reject tại C: `invalid_shape`, `ORDER_PLAN_INCOMPLETE`, hoặc reason_code khác `OK`.
2. Xác định guard skip tại D: `missing_origin_timestamp`, `duplicate_trace`, `sl_tp_calc_failed`.
3. Tổng hợp decision log để tạo input cho phase execution/fix (scope nhỏ, kiểm thử được).
</action>

<acceptance_criteria>
- Có ma trận checkpoint C/D với trace_id correlation
- Chỉ ra được checkpoint đầu tiên gây no-entry cho case đã khảo sát
- Có danh sách đề xuất fix tasks đủ cụ thể để chạy `/gsd-execute-phase 15.7`
</acceptance_criteria>
</task>

---

<verification>
1. `Get-ChildItem ".planning/phases/15.7-sequence-enabled-but-no-entry-trigger-diagnosis/*"`
2. `node ".agent/get-shit-done/bin/gsd-tools.cjs" phase-plan-index "15.7"`
3. `node ".agent/get-shit-done/bin/gsd-tools.cjs" init execute-phase "15.7"`
</verification>
