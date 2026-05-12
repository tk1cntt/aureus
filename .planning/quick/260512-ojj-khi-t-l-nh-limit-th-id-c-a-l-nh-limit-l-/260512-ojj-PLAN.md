---
phase: 260512-ojj-khi-t-l-nh-limit-th-id-c-a-l-nh-limit-l-
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - .planning/quick/260512-ojj-khi-t-l-nh-limit-th-id-c-a-l-nh-limit-l-/260512-ojj-REPORT.md
autonomous: true
requirements:
  - QUICK-260512-OJJ
must_haves:
  truths:
    - "Người dùng biết cơ chế hiện tại map pending limit order id sang position ticket như nào."
    - "Người dùng biết event nào tạo pending_order_id, event nào cập nhật ticket mới khi limit khớp."
    - "Người dùng biết điều kiện nào làm journal update đúng hoặc fail."
  artifacts:
    - path: ".planning/quick/260512-ojj-khi-t-l-nh-limit-th-id-c-a-l-nh-limit-l-/260512-ojj-REPORT.md"
      provides: "Report giải thích cơ chế mapping hiện tại, file/symbol liên quan, điểm rủi ro"
      min_lines: 40
  key_links:
    - from: "mql5/AureusProvider_v2.mq5::PushOrderFilled"
      to: "services/aureus-trader/journal.py::on_order_filled"
      via: "ORDER_FILLED event chứa pending_order_id + position_ticket + deal_ticket"
      pattern: "ORDER_FILLED.*pending_order_id.*position_ticket"
    - from: "services/aureus-trader/journal.py::on_order_filled"
      to: "services/aureus-trader/journal.py::on_order_opened"
      via: "normalize position_ticket thành ticket/position_id rồi gọi on_order_opened"
      pattern: "event\[\"ticket\"\].*position_ticket"
    - from: "services/aureus-trader/journal.py::on_order_opened"
      to: "aureus_trade_journal"
      via: "UPDATE theo trace_id hoặc pending_order_id hoặc cmd_id, set ticket=position_ticket và entry_deal_ticket=deal_ticket"
      pattern: "pending_order_id = \\\$9"
---

# Quick Plan: Phân tích cơ chế mapping limit order id hiện tại

<objective>
Tạo report trả lời câu hỏi: khi đặt lệnh limit, pending order id khác position ticket sau khi khớp, cơ chế hiện tại đang map và update journal như nào.

Purpose: user cần hiểu lifecycle hiện tại trước khi quyết định có cần sửa code không.
Output: `.planning/quick/260512-ojj-khi-t-l-nh-limit-th-id-c-a-l-nh-limit-l-/260512-ojj-REPORT.md`.
</objective>

<execution_context>
@D:/Aureus/.claude/get-shit-done/workflows/execute-plan.md
@D:/Aureus/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@CLAUDE.md
@services/aureus-trader/journal.py
@services/aureus-trader/dispatcher.py
@mql5/AureusProvider_v2.mq5
@services/aureus-trader/scripts/verify_limit_order_lifecycle_db_e2e.py

Key code points already identified:
- `journal.py::on_order_pending_placed`: stores `pending_order_id` while journal remains `TRIGGERED` and `ticket` remains null.
- `journal.py::on_order_filled`: maps `position_ticket` into `ticket` and `position_id`, then delegates to `on_order_opened`.
- `journal.py::on_order_opened`: updates row by `trace_id`, or by `pending_order_id` when trace_id missing, or by `cmd_id` when trace_id missing.
- `AureusProvider_v2.mq5::PushOrderFilled`: sends `ORDER_FILLED` with `pending_order_id`, `position_ticket`, `deal_ticket`, `trace_id`, `comment`, `time`.
- `dispatcher.py::event_listener`: handles realtime `ORDER_FILLED` asynchronously for journal.
- `verify_limit_order_lifecycle_db_e2e.py`: DB E2E proof for pending placed → filled → closed lifecycle.
</context>

<tasks>

<task type="auto">
  <name>Task 1: Trace limit order lifecycle hiện tại</name>
  <files>services/aureus-trader/journal.py, services/aureus-trader/dispatcher.py, mql5/AureusProvider_v2.mq5, services/aureus-trader/scripts/verify_limit_order_lifecycle_db_e2e.py</files>
  <action>Dùng GitNexus query/context nếu có để xác nhận flow unfamiliar về pending limit fill. Sau đó đọc code liên quan và lập trace theo thứ tự: strategy match tạo journal TRIGGERED → ORDER_PENDING_PLACED lưu `pending_order_id` → MT5 OnTradeTransaction phát hiện pending fill → ORDER_FILLED gửi `pending_order_id`, `position_ticket`, `deal_ticket` → dispatcher gọi `journal.on_order_filled` → `on_order_opened` update `ticket`, `position_id`, `entry_deal_ticket`, `status=EXECUTED`. Không sửa code vì user hỏi "cơ chế hiện tại như nào".</action>
  <verify>
    <automated>python -m pytest services/aureus-trader/tests/test_journal.py -k "pending or filled" -q</automated>
  </verify>
  <done>Executor nắm được cơ chế mapping hiện tại, có file/symbol/field cụ thể, không còn điểm mơ hồ về pending_order_id vs ticket.</done>
</task>

<task type="auto">
  <name>Task 2: Viết report giải thích cơ chế và rủi ro</name>
  <files>.planning/quick/260512-ojj-khi-t-l-nh-limit-th-id-c-a-l-nh-limit-l-/260512-ojj-REPORT.md</files>
  <action>Tạo report tiếng Việt, markdown, không HTML. Nội dung bắt buộc: tóm tắt ngắn; lifecycle hiện tại dạng bullet; bảng mapping field (`pending_order_id`, `position_ticket`, `deal_ticket`, `ticket`, `position_id`, `cmd_id`, `trace_id`); điều kiện update journal đúng; các case có thể fail (thiếu trace_id và không có pending_order_id/cmd_id, thiếu ticket/open_price/time, provider không gửi ORDER_FILLED); kết luận có cần sửa code hay chưa dựa trên code hiện tại. Nếu thấy code hiện tại đã có cơ chế mapping, nói rõ "đã có" và chỉ nêu điểm cần verify bằng DB E2E, không tự đề xuất sửa speculative.</action>
  <verify>
    <automated>test -f .planning/quick/260512-ojj-khi-t-l-nh-limit-th-id-c-a-l-nh-limit-l-/260512-ojj-REPORT.md && grep -q "pending_order_id" .planning/quick/260512-ojj-khi-t-l-nh-limit-th-id-c-a-l-nh-limit-l-/260512-ojj-REPORT.md && grep -q "ORDER_FILLED" .planning/quick/260512-ojj-khi-t-l-nh-limit-th-id-c-a-l-nh-limit-l-/260512-ojj-REPORT.md</automated>
  </verify>
  <done>Report trả lời trực tiếp câu hỏi của user, chỉ report-only, có chứng cứ từ code và verification command.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| MT5 provider → Redis event → trader journal | Event từ MT5/provider đi vào Python service và update DB journal. |
| Trader service → PostgreSQL | Journal update trạng thái trade và ticket thật. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-260512-ojj-01 | Tampering | `ORDER_FILLED` event payload | accept | Report-only. Ghi rõ code hiện tại phụ thuộc `trace_id`/`pending_order_id`/`cmd_id`; không thay đổi validation trong quick này. |
| T-260512-ojj-02 | Repudiation | journal lifecycle audit | accept | Report-only. Nêu field `entry_deal_ticket`, `pending_order_id`, `ticket` là audit link hiện tại. |
| T-260512-ojj-03 | Denial of Service | async journal update | accept | Report-only. Nêu dispatcher chạy `ORDER_FILLED` journal task async ở event listener; không sửa flow. |
</threat_model>

<verification>
- `python -m pytest services/aureus-trader/tests/test_journal.py -k "pending or filled" -q`
- Nếu môi trường DB sẵn: `python services/aureus-trader/scripts/verify_limit_order_lifecycle_db_e2e.py`
- Report tồn tại và có `pending_order_id`, `ORDER_FILLED`, `position_ticket`, `entry_deal_ticket`.
</verification>

<success_criteria>
- Có report tiếng Việt trả lời "cơ chế hiện tại như nào".
- Report chỉ ra mapping chính: pending order id được lưu ở `pending_order_id`; khi khớp, `position_ticket` trở thành `ticket`/`position_id`; `deal_ticket` lưu vào `entry_deal_ticket`.
- Không sửa code trừ khi executor chứng minh code thiếu hoặc sai rõ ràng; nếu sửa thì phải dừng, chạy GitNexus impact trước, và DB E2E theo CLAUDE.md.
</success_criteria>

<output>
Sau hoàn thành, tạo `.planning/quick/260512-ojj-khi-t-l-nh-limit-th-id-c-a-l-nh-limit-l-/260512-ojj-SUMMARY.md`.
</output>
