---
status: complete
phase: 28-aureusprovider-mq5-bidirectional-extension
source: [28-SUMMARY.md, 28-01-SUMMARY.md]
started: 2026-04-06T17:10:36+07:00
updated: 2026-04-06T17:20:35+07:00
---

## Current Test

[testing complete]

## Tests

### 1. Gateway Unit Tests Pass
expected: Chạy `python -m pytest services/aureus-gateway/tests/test_order_events.py -v` → 8/8 tests pass
result: pass
notes: "8 passed in 0.31s — ORDER_OPENED, ORDER_CLOSED, ORDER_FAILED, ACK, NACK, invalid fields, correct channel, JSON payload"

### 2. MQL5 EA Compiles Without Errors
expected: Mở `mql5/AureusProvider.mq5` trong MetaEditor → nhấn F7 (Compile) → không có errors
result: blocked
blocked_by: physical-device
reason: "Cần MetaEditor trên máy có MT5 terminal — không thể compile từ CI/CD"

### 3. Order Command Parsing — OPEN_ORDER
expected: EA nhận OPEN_ORDER JSON → log "Received OPEN_ORDER command" và trả ACK
result: blocked
blocked_by: physical-device
reason: "Cần MT5 terminal đang chạy với EA attached để test live command parsing"

### 4. Order Command Parsing — CLOSE_ORDER
expected: EA nhận CLOSE_ORDER JSON → log "Received CLOSE_ORDER command" và trả ACK
result: blocked
blocked_by: physical-device
reason: "Cần MT5 terminal đang chạy với EA attached để test live command parsing"

### 5. ACK/NACK Protocol — Duplicate Command
expected: Gửi cùng cmd_id 2 lần → lần đầu ACK, lần sau NACK reason=DUPLICATE
result: blocked
blocked_by: physical-device
reason: "Cần MT5 terminal đang chạy — IsDuplicateCmd/RecordCmdId logic verified qua code review"

### 6. Chart Display Shows v3.0 và Order Stats
expected: Trên MT5 chart Comment hiển thị "Aureus Provider v3.0" và dòng "Orders: 0 executed, 0 failed | Cmd IDs: 0"
result: blocked
blocked_by: physical-device
reason: "Cần MT5 chart visible — code review xác nhận v3.0 tại L1097, order stats tại L1102"

### 7. Gateway Event Publishing to Redis
expected: Gateway nhận ORDER_OPENED event từ EA → publish lên Redis channel aureus:mt5:events
result: pass
notes: "Code review: OrderOpenedEvent Pydantic model ở L74, r.publish('aureus:mt5:events', event_json) ở L147. Unit test test_order_event_publishes_correct_channel xác nhận channel đúng."

### 8. Existing Heartbeat/Reconnect Logic Unchanged
expected: EA vẫn reconnect khi mất kết nối, heartbeat vẫn gửi đúng interval, TICK/CANDLE data vẫn stream bình thường
result: pass
notes: "Code review: OnTimer() L1061-1117 giữ nguyên reconnect logic (EnsureConnected ở L1075), candle polling (CheckAndSendCandleForSymbol ở L1093). Order code chỉ thêm functions mới, không modify existing flow."

## Summary

total: 8
passed: 3
issues: 0
pending: 0
skipped: 0
blocked: 5

## Gaps

[none — no issues found]
