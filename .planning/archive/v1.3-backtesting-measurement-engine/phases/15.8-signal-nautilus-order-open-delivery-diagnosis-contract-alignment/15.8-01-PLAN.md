---
phase: "15.8"
plan: "01"
title: "Diagnose ORDER_OPEN Delivery Breaks and Align Runtime Contract Across Signal→Nautilus"
wave: 1
depends_on: []
files_modified:
  - .planning/phases/15.8-signal-nautilus-order-open-delivery-diagnosis-contract-alignment/15.8-CONTEXT.md
  - .planning/phases/15.8-signal-nautilus-order-open-delivery-diagnosis-contract-alignment/15.8-RESEARCH.md
  - .planning/phases/15.8-signal-nautilus-order-open-delivery-diagnosis-contract-alignment/15.8-VALIDATION.md
  - services/aureus-signal/engine/orders.py
  - services/aureus-nautilus-node/main.py
  - services/aureus-nautilus-node/execution_client.py
  - services/aureus-nautilus-bridge/main.py
autonomous: true
requirements_addressed: [INTERNAL-RUNTIME-INTEGRATION-DEBUG-ALIGNMENT]
---

<objective>
Xác định và đóng các điểm đứt khiến `ORDER_OPEN` không đi xuyên suốt từ `aureus-signal` tới pipeline thực thi Nautilus, bằng cách khóa rõ runtime ownership, stream/symbol contract và payload validation contract theo hướng multi-symbol an toàn.
</objective>

<must_haves>
- Có bằng chứng checkpoint chain producer→stream→consumer cho ít nhất 2 symbol runtime
- Có quyết định rõ stream/symbol contract, không hardcode duy nhất `XAUUSD`
- Có mapping payload `ORDER_OPEN` theo nhóm critical/optional + fallback/reject policy
- Có reason-code taxonomy và metric bucket để truy reject path end-to-end
</must_haves>

---

<task id="15.8-01-T1" title="Map runtime breakpoints from producer to active consumer owners">
<read_first>
- services/aureus-signal/engine/orders.py
- services/aureus-nautilus-node/main.py
- services/aureus-nautilus-node/execution_client.py
- services/aureus-nautilus-bridge/main.py
- .planning/phases/15.8-signal-nautilus-order-open-delivery-diagnosis-contract-alignment/15.8-CONTEXT.md
- .planning/phases/15.8-signal-nautilus-order-open-delivery-diagnosis-contract-alignment/15.8-RESEARCH.md
</read_first>

<action>
Thiết lập bản đồ breakpoints runtime với output cụ thể:
1. Xác nhận producer publish vào key format `aureus:stream:{symbol}:orders` và ghi rõ các field tối thiểu (`trace_id`, `symbol`, `side`, `qty`).
2. Xác nhận runtime ownership tại consumer: bridge là ingress chuẩn multi-symbol; node execution client chỉ hoạt động khi explicit mode/flag.
3. Liệt kê chính xác điểm đứt đầu tiên theo chain: publish thành công nhưng không có consumer polling phù hợp, hoặc consumer polling nhưng không start trong runtime chính.
4. Chốt artifact evidence dạng bảng gồm `symbol`, `stream_key`, `consumer_owner`, `runtime_started`, `first_breakpoint`.
</action>

<acceptance_criteria>
- Có bảng evidence chứa tối thiểu 2 symbol runtime (`XAUUSD`, `ETHUSD`) với đủ cột `symbol`, `stream_key`, `consumer_owner`, `runtime_started`, `first_breakpoint`
- `services/aureus-signal/engine/orders.py` còn publish theo format `aureus:stream:{symbol}:orders`
- `services/aureus-nautilus-node/main.py` thể hiện rõ trạng thái wiring execution pipeline (started hoặc warning explicit mode)
- `services/aureus-nautilus-bridge/main.py` thể hiện cơ chế wildcard stream scan cho orders
</acceptance_criteria>
</task>

<task id="15.8-01-T2" title="Align stream discovery and symbol contract for multi-symbol runtime">
<read_first>
- services/aureus-nautilus-node/execution_client.py
- services/aureus-nautilus-bridge/main.py
- services/aureus-signal/engine/orders.py
- .planning/phases/15.8-signal-nautilus-order-open-delivery-diagnosis-contract-alignment/15.8-CONTEXT.md
- .planning/phases/15.8-signal-nautilus-order-open-delivery-diagnosis-contract-alignment/15.8-RESEARCH.md
</read_first>

<action>
Khóa stream/symbol contract bằng giá trị cụ thể:
1. Không hardcode duy nhất `aureus:stream:XAUUSD:orders`; dùng discovery pattern `aureus:stream:*:orders` kết hợp symbol allowlist config.
2. Định nghĩa `payload.symbol` là source-of-truth; stream-key symbol chỉ dùng cross-check.
3. Khi `payload.symbol != stream_symbol`: reject với reason-code `SYMBOL_STREAM_MISMATCH` và tăng counter metric `order_open_reject_symbol_mismatch_total`.
4. Khi symbol thuộc allowlist: cho phép đi tiếp pipeline; khi ngoài allowlist: reject với `SYMBOL_NOT_ALLOWED` + metric bucket tương ứng.
</action>

<acceptance_criteria>
- `execution_client.py` hoặc consumer owner được chỉ định không còn phụ thuộc bắt buộc vào chuỗi cố định `aureus:stream:XAUUSD:orders`
- Có định nghĩa rõ ràng rule `payload.symbol` là source-of-truth và stream symbol là cross-check
- Có reason-code literal `SYMBOL_STREAM_MISMATCH` và `SYMBOL_NOT_ALLOWED` trong contract/diagnostic flow
- Có định danh metric bucket `order_open_reject_symbol_mismatch_total` hoặc mapping tương đương được tài liệu hóa rõ
</acceptance_criteria>
</task>

<task id="15.8-01-T3" title="Lock ORDER_OPEN payload contract and reject/fallback observability semantics">
<read_first>
- services/aureus-signal/engine/orders.py
- services/aureus-nautilus-node/execution_client.py
- .planning/phases/15.8-signal-nautilus-order-open-delivery-diagnosis-contract-alignment/15.8-CONTEXT.md
- .planning/phases/15.8-signal-nautilus-order-open-delivery-diagnosis-contract-alignment/15.8-RESEARCH.md
- .planning/phases/15.8-signal-nautilus-order-open-delivery-diagnosis-contract-alignment/15.8-VALIDATION.md
</read_first>

<action>
Chuẩn hóa payload contract với policy cụ thể:
1. Nhóm **critical required**: `trace_id`, `symbol`, `side`, `qty`; nếu thiếu thì reject với reason-code `ORDER_OPEN_MISSING_CRITICAL_FIELD`.
2. Nhóm **optional with fallback**: `entry_policy`, `expiry_policy`, `backfill_status`; nếu thiếu thì set fallback mặc định, emit warning metric `order_open_optional_fallback_total`.
3. SL/TP semantics: nếu strategy yêu cầu bracket thì thiếu `sl`/`tp` phải reject với reason-code `ORDER_OPEN_SLTP_REQUIRED_MISSING`.
4. Chuẩn hóa log payload-validation theo format chứa `trace_id`, `symbol`, `reason_code`, `fallback_applied`, `consumer_owner`.
5. Tổng hợp ma trận contract outcome gồm `case`, `required_fields_present`, `fallback_fields_missing`, `reason_code`, `expected_action`.
</action>

<acceptance_criteria>
- Có mapping field-group `critical required` và `optional with fallback` trong artifacts phase 15.8
- Có reason-code literal `ORDER_OPEN_MISSING_CRITICAL_FIELD` và `ORDER_OPEN_SLTP_REQUIRED_MISSING`
- Có metric bucket `order_open_optional_fallback_total` hoặc tên tương đương được xác nhận
- Có ma trận contract outcome với ít nhất 4 case: valid, missing optional, missing critical, symbol mismatch
</acceptance_criteria>
</task>

---

<verification>
1. `Get-ChildItem ".planning/phases/15.8-signal-nautilus-order-open-delivery-diagnosis-contract-alignment/*"`
2. `node ".agent/get-shit-done/bin/gsd-tools.cjs" phase-plan-index "15.8"`
3. `node ".agent/get-shit-done/bin/gsd-tools.cjs" init execute-phase "15.8"`
</verification>
