# Architecture Advisory 260513-9x3: Pending order fill gateway response

**Mode:** report-only  
**Scope:** review lại plan `260513-8z8`, không sửa source  
**Source code edited:** No source code edited / không sửa source

## Context

Vấn đề cần giải quyết:

```text
Market order có phản hồi lifecycle bình thường.
Pending order đã fill nhưng gateway/journal không nhận hoặc không update đúng.
```

Artifact này review độc lập theo 4 bước, dùng làm tài liệu yêu cầu cho bước thực thi/kiểm thử tiếp theo.

Nguồn dùng:

- `260513-8z8` report: `.planning/quick/260513-8z8-ph-n-ti-ch-la-i-mql5-aureusprovider-v2-m/260513-8z8-REPORT.md`
- Source: `mql5/AureusProvider_v2.mq5`
- MQL5 docs:
  - `https://www.mql5.com/en/book/automation/experts/experts_pending`
  - `https://www.mql5.com/en/book/automation/experts/experts_modify_order`

Docs access note:

- `WebFetch` bị chặn với `mql5.com`.
- Đã fetch bằng Python `urllib.request` trong shell.
- Extracted docs facts được dùng ở dưới, không bịa.

## 1. Neutral Listing

Các phương án/giả thuyết kỹ thuật để xử lý pending order fill không phản hồi gateway:

### 1.1 Socket disconnect drop

- Pending fill event đi qua `OnTradeTransaction` sau thời điểm đặt lệnh.
- Code kiểm tra `g_socket.IsConnected()` trước `PushOrderFilled`.
- Nếu socket disconnected, event return và không replay.
- Market order không cần chờ fill sau này; nó emit `ORDER_OPENED` ngay trong `ExecuteOpenOrder`.

### 1.2 `HistoryDealSelect(trans.deal)` fail

- `OnTradeTransaction` chỉ tiếp tục khi `HistoryDealSelect(trans.deal)` true.
- Nếu deal vừa phát sinh nhưng history chưa select được, code return.
- Không có log ở gate này.

### 1.3 `DEAL_ENTRY` hoặc magic gate loại event

- Code chỉ xử lý `DEAL_ENTRY_IN` và `DEAL_ENTRY_OUT`.
- Code bỏ qua `DEAL_MAGIC == 0`.
- Nếu pending fill deal không có magic hoặc entry khác kỳ vọng, code return.

### 1.4 Pending fill recognition fail ở `HistoryOrderSelect(DEAL_ORDER)` / `ORDER_TYPE`

- Với `DEAL_ENTRY_IN`, code lấy `DEAL_ORDER` thành `orderTicket`.
- Code gọi `HistoryOrderSelect(orderTicket)`.
- Code chỉ gọi `PushOrderFilled` nếu `ORDER_TYPE` thuộc pending types:
  - `ORDER_TYPE_BUY_LIMIT`
  - `ORDER_TYPE_SELL_LIMIT`
  - `ORDER_TYPE_BUY_STOP`
  - `ORDER_TYPE_SELL_STOP`
  - `ORDER_TYPE_BUY_STOP_LIMIT`
  - `ORDER_TYPE_SELL_STOP_LIMIT`
- Nếu select fail hoặc type không match, code return im lặng.
- Đây là pending fill detection gap chính.

### 1.5 Pending mapping miss / correlation loss

- Pending accepted path lưu mapping:
  - key: `result.order`
  - values: `traceId`, `cmdId`, `comment`, `strategyName`
- Fill path pop mapping bằng `orderTicket = DEAL_ORDER`.
- Mapping miss không chặn `PushOrderFilled` trong code hiện tại.
- Mapping miss làm `cmd_id` rỗng và `trace_id` phụ thuộc comment.
- Gateway/trader/journal có thể nhận event nhưng khó correlate.

### 1.6 `SendJSON` failure không quan sát được

- `PushOrderFilled` build JSON rồi gọi `g_socket.SendJSON(json)`.
- Code không kiểm tra return status của `SendJSON`.
- Debug log `ORDER_FILLED pushed` in sau call, không chứng minh gateway nhận.

### 1.7 Backend/gateway validation hoặc correlation issue

- Gateway model `OrderFilledEvent` accept `cmd_id: Optional[str]`.
- Gateway publish `ORDER_FILLED` nếu payload valid.
- Trader listener gọi `journal.on_order_filled(event)` với mọi `ORDER_FILLED`, kể cả không có pending future match.
- Sau quick `260512-q15`, backend fallback theo `pending_order_id/cmd_id` đã được bổ sung.
- Do đó backend ít khả năng là nguyên nhân chính nếu gateway không hề thấy event.

### 1.8 Market-order path không tương đương pending-fill path

- Market:
  - `OrderSend` khớp ngay.
  - `ExecuteOpenOrder` tự resolve position/price.
  - Emit `ORDER_OPENED` ngay.
- Pending:
  - `OrderSend` chỉ đặt order chờ.
  - Fill xảy ra sau qua trade transaction/history deal.
  - Emit `ORDER_FILLED` chỉ nếu pending fill detection pass.

## 2. Attribute Mapping

### 2.1 Correctness

Mạnh nhất về correctness: xử lý dựa trên `OnTradeTransaction` + deal/order history evidence.

Lý do:

- Pending fill là sự kiện deal về sau, không cùng thời điểm pending placement.
- `OnTradeTransaction` là điểm duy nhất hiện code dùng để emit `ORDER_FILLED`.
- Root cause phải chứng minh event dừng ở gate nào trước `PushOrderFilled`.

Yếu nếu chỉ sửa placement retcode:

- MQL5 docs `experts_pending` mô tả pending order dùng `TRADE_ACTION_PENDING` và method `placed()` kiểm `retcode != TRADE_RETCODE_DONE && retcode != TRADE_RETCODE_DONE_PARTIAL` thì fail.
- MQL5 docs `experts_modify_order` mô tả modify pending order có `modified()` chấp nhận `TRADE_RETCODE_DONE` và `TRADE_RETCODE_PLACED`.
- Vì vậy không đủ cơ sở nói pending placement chính lỗi vì thiếu `TRADE_RETCODE_PLACED`.

### 2.2 Observability

Mạnh nhất về observability: thêm log diagnostic tại các early-return gates trong `OnTradeTransaction`.

Cần log:

- `trans.type`
- `trans.deal`
- `HistoryDealSelect` result
- `DEAL_ENTRY`
- `DEAL_MAGIC`
- `DEAL_ORDER`
- `HistoryOrderSelect` result
- `ORDER_TYPE`
- `isPendingFill`
- `g_socket.IsConnected()`
- `PopPendingOrderMapping` result
- `SendJSON` result nếu API hỗ trợ

Trade-off:

- Thêm log không tự fix behavior.
- Nhưng giảm rủi ro sửa nhầm vào retcode/DB/backend khi lỗi nằm ở pending fill detection gap.

### 2.3 Blast radius

Mạnh nhất về blast radius thấp: chỉ thêm diagnostic + không đổi market-order path.

Rủi ro thấp vì:

- Không đổi `ExecuteOpenOrder` market branch.
- Không đổi journal SQL.
- Không đổi gateway schema.
- Chỉ làm rõ pending branch.

Rủi ro cao hơn: gửi `ORDER_FILLED` cho mọi `DEAL_ENTRY_IN` có magic.

- Có thể duplicate market order open event.
- Có thể gửi event cho DCA/managed entries không phải pending accepted từ gateway.
- Có thể làm journal update nhầm nếu trace/cmd/pending missing.

### 2.4 Testability

Mạnh nhất về testability: event-driven contract tests + manual MT5 fill smoke.

Cần tách 4 state:

1. Pending accepted emitted.
2. Pending filled detected in `OnTradeTransaction`.
3. `ORDER_FILLED` sent to gateway.
4. Gateway/trader/journal consumed event.

Nếu test chỉ nhìn DB, không phân biệt được event drop ở provider hay correlation fail ở journal.

### 2.5 MQL5 semantic fit

Mạnh nhất về semantic fit:

- Placement: dùng `TRADE_ACTION_PENDING`, verify order exists by order ticket after `OrderSend`.
- Modify: dùng `TRADE_ACTION_MODIFY`, success can include `TRADE_RETCODE_PLACED` per docs modify page.
- Fill: observe through deal transaction/history, not placement retcode.

Docs-backed correction:

- Không claim `TRADE_RETCODE_PLACED` là main pending placement success signal.
- Không claim `TRADE_RETCODE_DONE` là only universal success for all pending lifecycle.
- Đúng hơn: placement success and later fill detection là 2 lifecycle phases khác nhau.

### 2.6 Risk of masking root cause

Phương án dễ mask root cause:

- Fallback gửi `ORDER_FILLED` khi mapping miss mà không log `HistoryOrderSelect`/`ORDER_TYPE`.
- Tăng backend fallback nhưng provider vẫn không send.
- Treat `ORDER_OPENED` pending accepted như executed trade.
- Chỉ thêm `TRADE_RETCODE_PLACED` vào success condition mà không chứng minh current broker trả code đó.

## 3. Contextual Recommendation

### 3.1 Context cụ thể Aureus

- `AureusProvider_v2.mq5` đã có market path hoạt động tương đối ổn.
- `260512-q15` đã thêm pending mapping và backend fallback.
- User quan sát pending order đã fill nhưng gateway không có phản hồi đúng.
- DB gần đây cho thấy nhiều limit strategy vẫn `TRIGGERED`, không có `pending_order_id`, `ticket`, `cmd_id`.
- Previous report `260513-8z8` đúng khi chỉ ra gates, nhưng chưa đủ sắc vì chưa nhấn mạnh delta pending vs market.

### 3.2 Lựa chọn tối ưu

Lựa chọn tối ưu: **instrument and harden pending fill detection path**, không sửa rộng retcode/backend trước.

Cụ thể:

1. Giữ market-order path nguyên vẹn.
2. Pending accepted path cần verify order exists sau `OrderSend` bằng `OrderSelect(result.order)` hoặc wait ngắn theo tinh thần MQL5 `placed()` docs.
3. `OnTradeTransaction` cần diagnostic logs tại mọi gate trước `PushOrderFilled`.
4. Pending fill detection không nên silent-return khi `HistoryOrderSelect(DEAL_ORDER)` fail.
5. Mapping miss phải được log là correlation degradation, không coi là send blocker.
6. `PushOrderFilled` cần log/check `SendJSON` result nếu wrapper trả bool/status.
7. Test phải chứng minh gateway nhận `ORDER_FILLED` payload trước khi assert DB.

### 3.3 Vì sao không chọn retcode-only fix

Retcode-only fix có vẻ nhanh nhưng thiếu cơ sở.

Docs evidence:

- `experts_pending`: pending placement method `placed()` kiểm `TRADE_RETCODE_DONE` và `TRADE_RETCODE_DONE_PARTIAL`, rồi wait order exists.
- `experts_modify_order`: pending modify method `modified()` kiểm `TRADE_RETCODE_DONE` và `TRADE_RETCODE_PLACED`.

Do đó thêm `TRADE_RETCODE_PLACED` vào placement branch có thể hữu ích với broker-specific behavior, nhưng không phải root fix được chứng minh.

### 3.4 Best suggestion

Best suggestion:

```text
Phase 1: add pending-fill diagnostic + send result visibility.
Phase 2: run MT5 pending fill smoke and classify exact gate.
Phase 3: only then change detection behavior if evidence shows HistoryOrderSelect/orderType gate is wrong.
```

Nếu cần một code fix nhỏ ngay sau advisory:

- Thêm helper log `TracePendingEntryDeal(...)`.
- Trong `DEAL_ENTRY_IN`, log before return:
  - `orderTicket`
  - `historyOrderSelected`
  - `orderType`
  - `isPendingFill`
  - `hasPendingMapping`
- Không gửi event fallback rộng trong lần đầu.

## 4. Adversarial Mode

Giả sử chọn recommendation ở Bước 3: thêm diagnostic + harden pending fill detection trước khi đổi behavior.

### 4.1 Fail scenario 1: lỗi thật nằm ở gateway, không ở provider

Kịch bản:

- Provider log `ORDER_FILLED pushed`.
- `SendJSON` thực sự gửi thành công.
- Gateway validation/publish fail hoặc Redis consumer bỏ event.

Rủi ro bị bỏ qua:

- Chỉ nhìn MT5 log sẽ tưởng provider ổn.
- Cần gateway raw log hoặc Redis event capture.

Falsify bằng test:

- Capture gateway log line:
  - `Order event ORDER_FILLED ... published to aureus:mt5:events`
- Capture Redis event payload.

### 4.2 Fail scenario 2: `OnTradeTransaction` không chạy cho fill trong môi trường thật

Kịch bản:

- EA bị restart/reloaded.
- Fill xảy ra khi EA detached or not running.
- Transaction event không được delivered.

Rủi ro bị bỏ qua:

- Thêm gate logs không giúp nếu handler không chạy.

Falsify bằng test:

- Log heartbeat EA running.
- Log all `OnTradeTransaction` type counts.
- Compare MT5 account history fill time with EA runtime window.

### 4.3 Fail scenario 3: mapping RAM-only mất sau restart

Kịch bản:

- Pending order đặt xong.
- EA restart trước khi fill.
- `StorePendingOrderMapping` đã mất.
- Fill event vẫn có thể gửi nhưng thiếu `cmd_id/trace_id`.

Rủi ro bị bỏ qua:

- Diagnostic thấy mapping miss, nhưng nếu logic chỉ dựa mapping để classify pending, sẽ drop event.

Falsify bằng test:

- Place pending, restart EA, fill pending.
- Expect `ORDER_FILLED` still emitted with `pending_order_id`, even if `cmd_id` empty.
- Journal fallback must use `pending_order_id` if `on_order_pending_placed` had persisted it earlier.

### 4.4 Fail scenario 4: `HistoryOrderSelect(DEAL_ORDER)` behavior khác broker/tester

Kịch bản:

- `DEAL_ORDER` exists but `HistoryOrderSelect` returns false at transaction time.
- Later it becomes selectable.
- Or order type transformed after fill.

Rủi ro bị bỏ qua:

- Code silent-return loses event permanently.
- Delayed availability needs wait/retry or fallback classification.

Falsify bằng test:

- Log immediate select result.
- Retry short wait 100-500ms in diagnostic build.
- Compare immediate vs delayed `HistoryOrderSelect`.

### 4.5 Fail scenario 5: fallback emits duplicate or wrong `ORDER_FILLED`

Kịch bản:

- Broad fallback sends `ORDER_FILLED` for all `DEAL_ENTRY_IN` with magic.
- Market entries/DCA entries generate duplicate lifecycle events.
- Journal marks wrong `TRIGGERED` row executed.

Rủi ro bị bỏ qua:

- Fix event drop but corrupts journal semantic.

Falsify bằng test:

- Market order smoke: no extra `ORDER_FILLED` for market path unless explicitly intended.
- DCA entry smoke: no journal mutation for unrelated managed entry without trace/pending correlation.

### 4.6 Fail scenario 6: retcode assumption still broker-specific

Kịch bản:

- Some broker returns `TRADE_RETCODE_PLACED` for pending placement even though docs pending page sample checks `DONE/DONE_PARTIAL`.
- Current code would mark accepted pending as failed.

Rủi ro bị bỏ qua:

- Advisory rejects retcode-only as root cause, but real broker might still need additional accepted retcode.

Falsify bằng test:

- Log `result.retcode`, `result.order`, `request.action`, `request.type` for every pending placement.
- If observed `TRADE_RETCODE_PLACED` with valid `result.order`, add accepted retcode condition for pending branch.

## Execution Requirements

Future implementation should meet these requirements:

1. Preserve market-order path behavior.
2. Add pending placement log:
   - `cmd_id`
   - `orderType`
   - `request.action`
   - `request.type`
   - `result.retcode`
   - `result.order`
   - `result.price`
3. After pending `OrderSend` success, verify order exists or log if not found.
4. Add `OnTradeTransaction` diagnostic for `DEAL_ENTRY_IN` before all pending-return gates.
5. Log `HistoryDealSelect` fail with `trans.deal`.
6. Log `DEAL_ENTRY`, `DEAL_MAGIC`, `DEAL_ORDER`, `DEAL_TYPE` for bot magic deals.
7. Log `HistoryOrderSelect(orderTicket)` result and `ORDER_TYPE`.
8. Log `isPendingFill` false instead of silent return.
9. Log `PopPendingOrderMapping` result.
10. Ensure mapping miss does not by itself block `ORDER_FILLED` once pending fill is otherwise proven.
11. Check/log `SendJSON` result in `PushOrderFilled` if API exposes status.
12. Do not change DB/journal SQL unless evidence shows gateway receives valid `ORDER_FILLED` but journal fails.
13. If DB behavior changes later, run DB E2E per project rule.
14. Keep report-only artifacts separate from source commits.

## Test Basis

### Test 1: pending placement accepted

Goal:

```text
LIMIT/STOP placement emits accepted event and stores mapping.
```

Checks:

- MT5 log has pending placement retcode and order ticket.
- Provider logs `StorePendingOrderMapping` with same order ticket.
- Gateway receives `ORDER_OPENED` for pending accepted.
- Journal row gets `pending_order_id` if backend path involved.

### Test 2: pending filled while socket connected

Goal:

```text
Pending fill emits ORDER_FILLED to gateway.
```

Checks:

- `OnTradeTransaction` logs `DEAL_ENTRY_IN`.
- `HistoryOrderSelect`/`ORDER_TYPE` evidence logged.
- Provider logs pending fill detected.
- Gateway log publishes `ORDER_FILLED`.
- Payload includes:
  - `pending_order_id`
  - `position_ticket`
  - `deal_ticket`
  - `symbol`
  - `direction`
  - `volume`
  - `open_price`
  - `magic`
  - `trace_id` if available
  - `cmd_id` if mapping available

### Test 3: pending filled while socket disconnected

Goal:

```text
Classify whether event is dropped or replay/reconcile needed.
```

Checks:

- Provider logs `g_socket.IsConnected() == false` at fill transaction.
- No silent return.
- Decide later whether to queue/replay or reconcile by polling history.

### Test 4: mapping miss / EA restart

Goal:

```text
Mapping miss degrades correlation, not event emission.
```

Steps:

- Place pending.
- Restart EA before fill.
- Fill pending.

Checks:

- `hasPendingMapping=false` logged.
- `ORDER_FILLED` still emitted if pending fill proven.
- Gateway receives event with `pending_order_id`.
- Journal update depends on persisted `pending_order_id` from placement.

### Test 5: `HistoryOrderSelect` / order type evidence

Goal:

```text
Prove exact behavior at pending fill detection gap.
```

Checks:

- Immediate `HistoryOrderSelect(DEAL_ORDER)` result.
- Delayed retry result if implemented.
- `ORDER_TYPE` numeric value logged.
- Compare with expected pending type constants.

### Test 6: market order regression

Goal:

```text
Market-order path unchanged.
```

Checks:

- Market order still emits one terminal event expected by dispatcher.
- No duplicate `ORDER_FILLED` for normal market open unless explicitly designed.
- Journal still updates `TRIGGERED -> EXECUTED` through `ORDER_OPENED`.

### Test 7: gateway/journal full path

Goal:

```text
Provider event reaches DB lifecycle.
```

Checks:

- Gateway log publish `ORDER_FILLED`.
- Trader event listener logs event receipt.
- Journal `on_order_filled` returns true.
- DB row moves `TRIGGERED -> EXECUTED`.
- Required if implementation touches DB or journal.

## Final Suggestion

Best next work item:

```text
Implement minimal observability patch in AureusProvider_v2.mq5 for pending placement and pending fill gates, compile, then run a real pending limit fill smoke test before changing fallback behavior.
```

Do not implement retcode-only fix as primary plan. Treat `TRADE_RETCODE_PLACED` as broker-observed optional acceptance only if runtime log proves it for `TRADE_ACTION_PENDING` placement.

Core conclusion:

```text
pending fill detection gap > retcode assumption
```

`OnTradeTransaction` + `HistoryOrderSelect(DEAL_ORDER)` + pending `ORDER_TYPE` gate is the main point to prove or fix.
