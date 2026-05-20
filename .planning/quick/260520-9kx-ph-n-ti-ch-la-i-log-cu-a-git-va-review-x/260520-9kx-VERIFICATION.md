status: human_needed

# Verification quick-260520-9kx sau continuation commit 4fe9793

Mục tiêu: proven regression fix, không random fallback, ORDER_CLOSED giữ exact cmd_id/trace_id correlation.

Kết luận: code gaps trước đã đóng. Automated verification pass. Còn cần human/live MT5 verification vì MQL5 compile/deploy và lifecycle close thật chưa có bằng chứng độc lập trong repo.

## Must-haves

| # | Must-have | Trạng thái | Bằng chứng |
|---|---|---|---|
| 1 | Mapping sống từ pending fill tới close bằng exact position ticket | passed | `D:/Aureus/mql5/AureusProvider_v2.mq5`: `DEAL_ENTRY_IN` dùng `GetPendingOrderMapping(orderTicket, ...)` thay vì pop, rồi `StorePendingOrderMapping(ticket, ...)` theo `DEAL_POSITION_ID`. `DEAL_ENTRY_OUT` dùng `PopPendingOrderMapping(ticket, ...)` và truyền `mappedCmdId` vào `PushOrderClosed`. |
| 2 | Gateway `OrderClosedEvent` giữ `cmd_id` qua model validation | passed | `D:/Aureus/services/aureus-gateway/main.py`: `OrderClosedEvent` có `cmd_id: Optional[str] = None`; `process_message` publish `valid_event.model_dump_json()`, nên field không bị drop. |
| 3 | Test tồn tại và pass evidence trong summary | passed | `D:/Aureus/services/aureus-gateway/tests/test_order_events.py`: `test_order_closed_event` gửi `cmd_id` và assert Redis payload giữ `cmd_id`. Chạy lại: `python -m pytest "D:/Aureus/services/aureus-gateway/tests/test_order_events.py" -q` -> `14 passed in 0.19s`. SUMMARY cũng ghi `14 passed`. |
| 4 | Không random/symbol/time fallback cho close correlation | passed | Diff `4fe9793` chỉ thêm exact map lookup/copy theo order ticket -> position ticket, thêm gateway schema/test. Không thấy fallback symbol/time/random trong changed diff. |
| 5 | Root cause/culprit proven bằng git/log/DB evidence | human_needed | SUMMARY có culprit `add3910`, runtime log, DB evidence. Verifier không có log/DB snapshot độc lập để tái xác thực ngoài summary. |

Score: 4/5 automated verified, 1/5 cần human/e2e.

## Prior gaps closure

| Gap cũ | Trạng thái | Bằng chứng |
|---|---|---|
| Fill branch pop mapping trước close | closed | `PopPendingOrderMapping(orderTicket, ...)` ở `DEAL_ENTRY_IN` đã đổi thành `GetPendingOrderMapping(orderTicket, ...)`; mapping được copy sang `ticket` position. |
| Gateway drop `cmd_id` ORDER_CLOSED | closed | `OrderClosedEvent` khai báo `cmd_id`; test assert payload Redis giữ `cmd_id`. |
| Test thiếu cho gateway cmd_id preservation | closed | `test_order_closed_event` có input `cmd_id` và assert output JSON. |

## Key links

| Link | Trạng thái | Bằng chứng |
|---|---|---|
| ORDER_OPENED pending order id -> pending fill | passed | `StorePendingOrderMapping(result.order, traceId, cmdId, ...)` lưu pending order id; fill dùng `GetPendingOrderMapping(orderTicket, ...)`, không xóa. |
| Pending fill -> close position ticket | passed | Khi fill có mapping và `ticket > 0`, code gọi `StorePendingOrderMapping(ticket, mappedTraceId, mappedCmdId, ...)`. |
| Close position ticket -> ORDER_CLOSED payload | passed | `DEAL_ENTRY_OUT` gọi `PopPendingOrderMapping(ticket, ...)`, rồi `PushOrderClosed(..., traceId, "", mappedCmdId)`. |
| Provider ORDER_CLOSED -> gateway Redis payload | passed | Provider JSON có `"cmd_id":"%s"`; gateway model có `cmd_id`; test chứng minh publish payload giữ field. |

## Behavioral spot-checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Gateway preserves ORDER_CLOSED cmd_id | `python -m pytest "D:/Aureus/services/aureus-gateway/tests/test_order_events.py" -q` | `14 passed in 0.19s` | passed |
| Continuation commit contains expected fix files | `git -C "D:/Aureus" show --stat --oneline 4fe9793` | 3 files: provider, gateway main, gateway tests | passed |
| MQL5 compile/live lifecycle | not run | MT5/MetaEditor unavailable per SUMMARY; verifier không start external service | human_needed |

## Anti-pattern scan

| File | Pattern | Severity | Impact |
|---|---|---|---|
| `D:/Aureus/mql5/AureusProvider_v2.mq5` | No symbol/time/random fallback in changed diff | none | Exact-key invariant preserved. |
| `D:/Aureus/services/aureus-gateway/main.py` | Optional additive field only | none | Validation now preserves provider field. |

## Human verification required

1. Build/deploy MT5 provider từ `D:/Aureus/mql5/AureusProvider_v2.mq5`.
   Expected: compile pass, EX5 deployed đúng terminal.
   Why human: MetaEditor/MT5 path không khả dụng trong verifier environment.

2. Chạy pending order lifecycle thật.
   Expected: ORDER_OPENED có `cmd_id`/ticket, pending fill log có `GetPendingOrderMapping result=true`, close log có `mapped=true mapped_cmd_id=... mapped_trace_id=...`, Redis ORDER_CLOSED còn `cmd_id` và `trace_id`.
   Why human: cần broker/MT5 runtime và event thật.

3. Kiểm tra notifier/DB sau close thật.
   Expected: không còn `Skip ORDER_CLOSED notification: unresolved strategy context` cho ticket hợp lệ; lifecycle không kẹt SENT-only.
   Why human: cần DB/live service state.

## Gaps

Không còn automated code gap từ verification trước. Trạng thái tổng là `human_needed` vì live MT5 build/e2e và DB/notifier evidence chưa tự xác thực được.

Verified: 2026-05-20
Verifier: Claude gsd-verifier
