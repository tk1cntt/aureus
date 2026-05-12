---
phase: 260512-ojj-khi-t-l-nh-limit-th-id-c-a-l-nh-limit-l-
plan: 01
subsystem: trader-journal
tags: [quick, report-only, limit-order, journal, mt5]
dependency_graph:
  requires: [services/aureus-trader/journal.py, services/aureus-trader/dispatcher.py, mql5/AureusProvider_v2.mq5]
  provides: [260512-ojj-REPORT.md]
  affects: []
tech_stack:
  added: []
  patterns: [report-only-code-trace]
key_files:
  created:
    - .planning/quick/260512-ojj-khi-t-l-nh-limit-th-id-c-a-l-nh-limit-l-/260512-ojj-REPORT.md
    - .planning/quick/260512-ojj-khi-t-l-nh-limit-th-id-c-a-l-nh-limit-l-/260512-ojj-SUMMARY.md
  modified: []
decisions:
  - Không sửa source vì task hỏi cơ chế hiện tại; report nêu rõ mapping có tồn tại nhưng `trace_id` vẫn là điều kiện bắt buộc khi journal update.
metrics:
  completed_date: 2026-05-12
  tasks_completed: 2
  tests_run: 1
---

# Quick 260512-ojj Summary: Cơ chế map pending limit order sang position ticket

## One-liner

Report-only trace xác nhận `ORDER_FILLED` mang `pending_order_id` + `position_ticket`, journal lưu `ticket`/`position_id`/`entry_deal_ticket`, nhưng code hiện tại vẫn bắt buộc `trace_id` để update row.

## Tasks Completed

| Task | Kết quả | Files |
|---|---|---|
| Task 1: Trace limit order lifecycle hiện tại | Hoàn tất. Xác nhận flow pending placed → pending filled → journal EXECUTED. | `services/aureus-trader/journal.py`, `services/aureus-trader/dispatcher.py`, `mql5/AureusProvider_v2.mq5`, `services/aureus-trader/scripts/verify_limit_order_lifecycle_db_e2e.py` |
| Task 2: Viết report giải thích cơ chế và rủi ro | Hoàn tất. Report tiếng Việt có lifecycle, bảng field mapping, điều kiện update đúng, case fail, kết luận. | `.planning/quick/260512-ojj-khi-t-l-nh-limit-th-id-c-a-l-nh-limit-l-/260512-ojj-REPORT.md` |

## Evidence chính

- `journal.py::on_order_pending_placed`: lưu `pending_order_id` khi journal còn `TRIGGERED` và `ticket` chưa có.
- `AureusProvider_v2.mq5::PushOrderFilled`: gửi `ORDER_FILLED` gồm `pending_order_id`, `position_ticket`, `deal_ticket`, `trace_id`, `open_price`, `time`.
- `dispatcher.py::event_listener`: nhận realtime `ORDER_FILLED`, gọi `journal.on_order_filled(event)` async.
- `journal.py::on_order_filled`: normalize `position_ticket` thành `ticket` và `position_id`.
- `journal.py::on_order_opened`: update row `TRIGGERED`, set `status = EXECUTED`, `ticket`, `position_id`, `entry_deal_ticket`; code hiện tại bắt buộc `trace_id`, còn `pending_order_id`/`cmd_id` không fallback độc lập nếu thiếu `trace_id`.

## Verification

```bash
python -m pytest services/aureus-trader/tests/test_journal.py -k "pending or filled" -q
```

Kết quả:

```text
2 passed, 79 deselected in 0.17s
```

Report verify:

```bash
test -f .planning/quick/260512-ojj-khi-t-l-nh-limit-th-id-c-a-l-nh-limit-l-/260512-ojj-REPORT.md && grep -q "pending_order_id" .planning/quick/260512-ojj-khi-t-l-nh-limit-th-id-c-a-l-nh-limit-l-/260512-ojj-REPORT.md && grep -q "ORDER_FILLED" .planning/quick/260512-ojj-khi-t-l-nh-limit-th-id-c-a-l-nh-limit-l-/260512-ojj-REPORT.md && grep -q "position_ticket" .planning/quick/260512-ojj-khi-t-l-nh-limit-th-id-c-a-l-nh-limit-l-/260512-ojj-REPORT.md && grep -q "entry_deal_ticket" .planning/quick/260512-ojj-khi-t-l-nh-limit-th-id-c-a-l-nh-limit-l-/260512-ojj-REPORT.md
```

Kết quả: pass.

## Deviations from Plan

None - plan executed report-only. Không sửa source code. Không commit docs theo constraint orchestrator.

## Known Stubs

None.

## Threat Flags

Không có surface mới. Report-only, không sửa network endpoint, auth path, file access, schema, hoặc trust boundary.

## Self-Check: PASSED

- Report tạo đúng path.
- Summary tạo đúng path.
- Source code không sửa.
- Không commit docs artifacts.
