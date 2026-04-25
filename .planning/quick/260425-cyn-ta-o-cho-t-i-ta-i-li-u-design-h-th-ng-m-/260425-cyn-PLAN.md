---
phase: 260425-cyn-ta-o-cho-t-i-ta-i-li-u-design-h-th-ng-m-
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - docs/system-design-strategy-trigger-data-flow.md
autonomous: true
requirements:
  - QUICK-260425-CYN
must_haves:
  truths:
    - "Tài liệu mô tả đúng luồng sau khi strategy trigger được tạo"
    - "Tài liệu giải thích data được xử lý/persist trong journal như thế nào"
    - "Tài liệu mô tả payload tối thiểu được dispatch sang MT5 và cách nhận kết quả"
    - "Tài liệu mô tả dữ liệu được gửi lên Telegram cho signal/order lifecycle"
    - "Tài liệu có Mermaid sequence diagram thể hiện chuyển động giữa các service"
  artifacts:
    - path: "docs/system-design-strategy-trigger-data-flow.md"
      provides: "Design document tiếng Việt về luồng strategy trigger → journal → MT5 → Telegram"
      contains: "```mermaid"
  key_links:
    - from: "Strategy trigger flow"
      to: "Journal persistence"
      via: "on_strategy_match / trace_id lifecycle được mô tả từ code thực tế"
      pattern: "trace_id"
    - from: "Order dispatch"
      to: "MT5 bridge/client"
      via: "dispatch_order payload và ACK/result/NACK được mô tả từ code thực tế"
      pattern: "MT5"
    - from: "Order/signal events"
      to: "Telegram notification"
      via: "Telegram formatter/sender được mô tả từ code thực tế"
      pattern: "Telegram"
---

<objective>
Tạo một tài liệu design hệ thống bằng tiếng Việt mô tả factual flow sau khi strategy trigger: data đi qua service nào, được journal/persist ra sao, payload được đẩy sang MT5 như thế nào, và thông tin nào được đẩy lên Telegram.

Purpose: Giúp đọc nhanh end-to-end lifecycle của một strategy match/order mà không phải tự lần code.
Output: `docs/system-design-strategy-trigger-data-flow.md` có mô tả theo bước, bảng payload/trách nhiệm service, và Mermaid sequence diagram giữa các service.
</objective>

<execution_context>
@D:/Aureus/.claude/get-shit-done/workflows/execute-plan.md
@D:/Aureus/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@D:/Aureus/CLAUDE.md
@D:/Aureus/.planning/STATE.md

Executor cần inspect code thực tế trước khi viết doc. Ưu tiên dùng GitNexus theo project rule để tìm execution flow thay vì grep mù:
- `gitnexus_query({query: "strategy trigger dispatch order MT5 Telegram journal"})`
- `gitnexus_query({query: "on_strategy_match dispatch_order ORDER_OPENED Telegram"})`
- `gitnexus_context({name: "dispatch_order"})` nếu symbol tồn tại
- `gitnexus_context({name: "on_strategy_match"})` nếu symbol tồn tại

Các quick task gần đây trong STATE.md rất liên quan và nên đọc SUMMARY nếu tồn tại để tránh sai flow:
- `D:/Aureus/.planning/quick/260423-t4w-t-i-u-ph-n-g-i-data-sang-mt5-cho-t-i-chi/`
- `D:/Aureus/.planning/quick/260424-1d1-chuy-n-ph-n-x-ly-asyncio-create-task-jou/`
- `D:/Aureus/.planning/quick/260424-a6a-v-n-l-i-trace-id-none-trace-id-c-ta-o-ra/`
- `D:/Aureus/.planning/quick/260424-c55-fix-runtime-warning-missing-trace-id-in-/`
- `D:/Aureus/.planning/quick/260424-sbg-ph-n-ti-ch-nguy-n-nh-n-timeout-cu-a-lu-n/`
- `D:/Aureus/.planning/quick/260425-ch4-th-c-hi-n-t-i-u-journal-py-theo-summary-/`
</context>

<tasks>

<task type="auto">
  <name>Task 1: Trace factual strategy/order/Telegram flow from code</name>
  <files>docs/system-design-strategy-trigger-data-flow.md</files>
  <action>Không sửa production code. Dùng GitNexus query/context và đọc các file source/SUMMARY liên quan để xác định luồng thật: nơi strategy trigger được tạo, nơi gọi `journal.on_strategy_match`, nơi `trace_id` được tạo/truyền, nơi `dispatch_order` build payload tối thiểu sang MT5, cách xử lý ACK/result/NACK/timeout, nơi xử lý `ORDER_OPENED`/`ORDER_CLOSED`, và nơi format/gửi Telegram. Ghi lại danh sách file/symbol đã đối chiếu vào phần "Nguồn đối chiếu" trong tài liệu. Nếu tên symbol khác so với gợi ý, dùng tên thật trong code.</action>
  <verify>
    <automated>test -n "$(git -C D:/Aureus status --short)" || true</automated>
  </verify>
  <done>Có đủ nguồn factual để viết doc; không có thay đổi code ngoài tài liệu dự kiến.</done>
</task>

<task type="auto">
  <name>Task 2: Write Vietnamese system design document with Mermaid sequence</name>
  <files>docs/system-design-strategy-trigger-data-flow.md</files>
  <action>Tạo `docs/system-design-strategy-trigger-data-flow.md` bằng tiếng Việt. Nội dung bắt buộc: (1) phạm vi và giả định, (2) actors/services tham gia, (3) flow từng bước từ strategy trigger → journal/persistence → MT5 dispatch → MT5 result/order lifecycle → Telegram, (4) bảng data/payload chính gồm strategy payload, signal snapshot/journal fields, MT5 dispatch payload tối thiểu, Telegram message context, (5) Mermaid `sequenceDiagram` thể hiện chuyển động giữa Strategy/Signal service, Journal/DB, MT5 dispatcher/bridge, MT5 terminal/EA, Telegram service/bot, (6) failure paths chính: missing trace_id, ACK timeout, result timeout, NACK duplicate, thiếu journal context khi ORDER_CLOSED, (7) "Nguồn đối chiếu" liệt kê file/symbol đã đọc. Không dùng wording suy đoán nếu chưa xác nhận; nếu điểm nào chưa tìm thấy trong code, ghi rõ "Chưa xác định từ source đã đọc" thay vì bịa.</action>
  <verify>
    <automated>test -f D:/Aureus/docs/system-design-strategy-trigger-data-flow.md && grep -q '```mermaid' D:/Aureus/docs/system-design-strategy-trigger-data-flow.md && grep -q 'sequenceDiagram' D:/Aureus/docs/system-design-strategy-trigger-data-flow.md && grep -qi 'MT5' D:/Aureus/docs/system-design-strategy-trigger-data-flow.md && grep -qi 'Telegram' D:/Aureus/docs/system-design-strategy-trigger-data-flow.md</automated>
  </verify>
  <done>Tài liệu tồn tại, có Mermaid sequence diagram, mô tả đầy đủ data flow sang MT5 và Telegram bằng tiếng Việt.</done>
</task>

<task type="auto">
  <name>Task 3: Verify doc scope and record summary</name>
  <files>docs/system-design-strategy-trigger-data-flow.md, .planning/quick/260425-cyn-ta-o-cho-t-i-ta-i-li-u-design-h-th-ng-m-/260425-cyn-SUMMARY.md</files>
  <action>Review tài liệu để đảm bảo chỉ thay đổi documentation, không sửa code. Chạy `git diff -- docs/system-design-strategy-trigger-data-flow.md` để tự kiểm tra nội dung có factual và đủ các phần bắt buộc. Vì project yêu cầu GitNexus trước commit/change-scope, chạy `gitnexus_detect_changes()` nếu MCP có sẵn; nếu không có MCP, ghi rõ trong SUMMARY là tool không khả dụng. Tạo SUMMARY nêu file đã tạo, các source/symbol chính đã đối chiếu, và lệnh verify đã chạy.</action>
  <verify>
    <automated>test -f D:/Aureus/.planning/quick/260425-cyn-ta-o-cho-t-i-ta-i-li-u-design-h-th-ng-m-/260425-cyn-SUMMARY.md && git -C D:/Aureus diff --name-only | grep -E '^(docs/system-design-strategy-trigger-data-flow.md|\.planning/quick/260425-cyn-ta-o-cho-t-i-ta-i-li-u-design-h-th-ng-m-/260425-cyn-SUMMARY.md)$'</automated>
  </verify>
  <done>SUMMARY được tạo; diff chỉ gồm tài liệu design và summary quick task.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Documentation only | Plan chỉ tạo tài liệu, không thay đổi runtime boundary hay production behavior |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-260425-cyn-01 | I | docs/system-design-strategy-trigger-data-flow.md | mitigate | Không đưa secret/token/credential vào tài liệu; chỉ mô tả field/payload shape ở mức cần thiết |
| T-260425-cyn-02 | T | documentation accuracy | mitigate | Bắt buộc đối chiếu source/SUMMARY và liệt kê "Nguồn đối chiếu"; các điểm chưa xác nhận phải ghi rõ chưa xác định |
</threat_model>

<verification>
- `test -f D:/Aureus/docs/system-design-strategy-trigger-data-flow.md`
- `grep -q '```mermaid' D:/Aureus/docs/system-design-strategy-trigger-data-flow.md`
- `grep -q 'sequenceDiagram' D:/Aureus/docs/system-design-strategy-trigger-data-flow.md`
- `git -C D:/Aureus diff --name-only` chỉ hiển thị doc và quick SUMMARY.
</verification>

<success_criteria>
- Có một tài liệu design tiếng Việt mô tả end-to-end strategy trigger data flow.
- Mermaid sequence diagram thể hiện luồng giữa các service chính.
- Tài liệu nêu rõ data đi sang MT5 và Telegram như thế nào dựa trên source thực tế.
- Không có production code/config/database change.
</success_criteria>

<output>
After completion, create `D:/Aureus/.planning/quick/260425-cyn-ta-o-cho-t-i-ta-i-li-u-design-h-th-ng-m-/260425-cyn-SUMMARY.md`
</output>
