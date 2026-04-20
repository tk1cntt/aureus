---
phase: 28-aureusprovider-mq5-bidirectional-extension
verified: 2026-04-20T16:42:00Z
status: human_needed
score: 3/3 requirements mapped with evidence
overrides_applied: 0
human_verification:
  - test: "MT5 terminal thực thi OPEN_ORDER/CLOSE_ORDER với broker/session thật"
    expected: "EA trả ACK/NACK đúng protocol và phát ORDER_OPENED/ORDER_CLOSED/ORDER_FAILED đúng lifecycle"
    why_human: "Cần runtime MT5 live; static evidence + unit test gateway chưa đủ chứng minh execution thật"
---

# Phase 28: AureusProvider.mq5 Bidirectional Extension Verification Report

**Phase Goal:** Mở rộng AureusProvider.mq5 thành luồng hai chiều để nhận lệnh order, execute, và phát sự kiện order qua gateway.
**Verified:** 2026-04-20T16:42:00Z
**Status:** human_needed
**Re-verification:** No — backfill verification cho phase 47

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | EA parse và xử lý command OPEN_ORDER/CLOSE_ORDER qua TCP | VERIFIED | `mql5/AureusProvider.mq5` được mở rộng với command handling path, parser helper và execution handlers (theo 28-01-SUMMARY). |
| 2 | Protocol ACK/NACK với `cmd_id` và dedup command đã được wire | VERIFIED | Summary phase 28 ghi FIFO dedup (`InpMaxCmdIdHistory`, `IsDuplicateCmd`, `RecordCmdId`) và ACK/NACK reason codes chuẩn. |
| 3 | Gateway validate order events và publish Redis channel `aureus:mt5:events` | VERIFIED | `services/aureus-gateway/main.py` có model/event routing cho ORDER_OPENED/CLOSED/FAILED + ACK/NACK; test file `services/aureus-gateway/tests/test_order_events.py`. |

## Requirements Coverage

| Requirement | Status | Evidence |
| --- | --- | --- |
| ORDER-04 | human_needed | **Artifact/code-path:** `mql5/AureusProvider.mq5` command handlers (`ProcessOrderCommand`, `ExecuteOpenOrder`, `ExecuteCloseOrder` theo plan/summary phase 28). **Test/command:** `python3 -m pytest services/aureus-gateway/tests/test_order_events.py -q -x`. **Flow/key-link:** Trader publish `aureus:mt5:commands` -> gateway forward TCP -> EA `OrderSend`. **Confidence note:** thiếu bằng chứng live MT5 trong môi trường hiện tại nên chưa thể `passed`. |
| ORDER-05 | human_needed | **Artifact/code-path:** `mql5/AureusProvider.mq5` push `ORDER_OPENED/ORDER_CLOSED/ORDER_FAILED`; `services/aureus-gateway/main.py` validate + publish sự kiện. **Test/command:** `python3 -m pytest services/aureus-gateway/tests/test_order_events.py -q -x`. **Flow/key-link:** EA `SendJSON` -> gateway `process_message()` -> Redis `aureus:mt5:events`. **Confidence note:** cần runtime trade lifecycle thực để chốt full E2E. |
| ORDER-06 | human_needed | **Artifact/code-path:** ACK/NACK schema và routing trong `mql5/AureusProvider.mq5` + `services/aureus-gateway/main.py`. **Test/command:** `python3 -m pytest services/aureus-gateway/tests/test_order_events.py -q -x`. **Flow/key-link:** `cmd_id` dedup ở EA + gateway publish ACK/NACK event. **Confidence note:** static/unit evidence tốt, nhưng chưa có manual MT5 session để xác nhận hành vi thực tế khi broker reject/accept. |

## Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| `aureus-trader` | `services/aureus-gateway/main.py` | publish Redis `aureus:mt5:commands` | WIRED | Key-link xuất hiện trong 28-01-PLAN frontmatter. |
| `services/aureus-gateway/main.py` | `mql5/AureusProvider.mq5` | TCP forward command theo `active_connections[symbol]` | WIRED | Đây là nhịp command gateway -> EA. |
| `mql5/AureusProvider.mq5` | `services/aureus-gateway/main.py` | `SendJSON` ACK/NACK/ORDER events | WIRED | Luồng ngược để gateway chuẩn hóa event. |
| `services/aureus-gateway/main.py` | Redis `aureus:mt5:events` | validate model và publish | WIRED | Chứng cứ qua test gateway và summary phase 28. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| --- | --- | --- | --- |
| Gateway order event tests | `python3 -m pytest services/aureus-gateway/tests/test_order_events.py -q -x` | Executed in phase 47-01 | PASS |

## Human Verification Required

1. Chạy MT5 terminal test account, gửi OPEN_ORDER/CLOSE_ORDER thật qua `aureus:mt5:commands`, xác nhận ACK/NACK + ORDER events phản ánh đúng trạng thái broker.
2. Kiểm tra path ORDER_CLOSED từ `OnTradeTransaction` với dữ liệu P&L thực (profit/commission/swap).

## Gaps Summary

Không thêm runtime/business fix mới trong phase 47. Trạng thái `human_needed` được giữ để tránh over-claim cho các hành vi phụ thuộc MT5 live.

---

_Verified: 2026-04-20T16:42:00Z_
_Verifier: Claude (phase 47 execute)_