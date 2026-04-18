# Phase 45: h-tr-x-ly-song-song-signal-strategy-cho-nhi-u-symbol-m-t- - Context

**Gathered:** 2026-04-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Hỗ trợ xử lý song song signal + strategy cho nhiều symbol cùng lúc trong `aureus-signal`, thay cho luồng tuần tự hiện tại, nhưng vẫn giữ độ đúng trading và khả năng rollback an toàn.

Phạm vi phase này tập trung vào cơ chế thực thi song song, thứ tự/nhất quán dữ liệu theo symbol, cô lập lỗi nghẽn theo symbol, và rollout an toàn. Không mở rộng capability mới ngoài boundary này.

</domain>

<decisions>
## Implementation Decisions

### Mô hình song song
- **D-01:** Chọn mô hình **per-symbol worker** làm lõi (mỗi symbol một worker/task riêng).
- **D-02:** Áp dụng song song **đồng thời cho cả signal + strategy** trong phase này.
- **D-03:** Concurrency mặc định **theo số symbol active** (1 worker/symbol).
- **D-04:** Khi quá tải, ưu tiên **độ đúng**: chậm thì xếp hàng, không drop vì mục tiêu realtime.

### Thứ tự & nhất quán dữ liệu
- **D-05:** Trong mỗi symbol, xử lý **FIFO strict theo candle t**.
- **D-06:** Candle đến trễ/out-of-order: **bỏ candle trễ** (không reorder window).
- **D-07:** Strategy trigger bắt buộc dùng **đúng snapshot của cùng candle**.
- **D-08:** Giữ **trace_id strict per symbol+candle** để chống duplicate trigger/order.

### Cô lập lỗi & nghẽn
- **D-09:** Dùng **circuit-breaker riêng theo symbol**; symbol lỗi tạm dừng, symbol khác vẫn chạy.
- **D-10:** Dùng **ngưỡng backlog per-symbol + cảnh báo** (không dùng ngưỡng global duy nhất).

### Rollout an toàn
- **D-11:** Rollout theo chuỗi **Shadow -> Canary -> Full**.
- **D-12:** Cho phép **rollback tự động theo SLO per-symbol** (lag/backlog/error-rate vượt ngưỡng liên tiếp thì hạ về chế độ tuần tự cho symbol đó).

### Claude's Discretion
- Thiết kế chi tiết các ngưỡng SLO cụ thể (giá trị, số phút liên tiếp, hysteresis).
- Cách tổ chức metric/telemetry chi tiết cho dashboard vận hành.
- Cấu trúc implementation chi tiết của worker lifecycle miễn không vi phạm các quyết định D-01..D-12.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope và milestone constraints
- `.planning/ROADMAP.md` — Khai báo Phase 45 và dependency từ Phase 44.
- `.planning/PROJECT.md` — Mục tiêu milestone v1.5, ưu tiên ổn định pipeline signal/strategy.
- `.planning/REQUIREMENTS.md` — Ràng buộc liên quan pipeline signal/strategy và trade execution trong v1.5.

### Runtime flow hiện tại (cần chuyển từ tuần tự sang song song)
- `services/aureus-signal/engine/live_engine.py` — Main candle consumer loop, update state, execute signals, emit per-symbol signal stream.
- `services/aureus-signal/engine/strategy_executor.py` — Strategy consumer loop theo stream signals, evaluate_all, process_triggers.
- `services/aureus-signal/engine/orders.py` — Trigger dedupe, trace_id, order_plan snapshot và publish order events.
- `services/aureus-signal/engine/manager.py` — Window/state update theo symbol.

### Regression/safety reference
- `services/aureus-signal/tests/test_multi_symbol.py` — Kiểm tra orchestration đa symbol (routing/lock isolation cơ bản).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `symbol_locks` trong `live_engine.py`: đã có primitive cô lập xử lý theo symbol, phù hợp mở rộng thành per-symbol worker model.
- Per-symbol streams (`aureus:stream:{symbol}:candle`, `aureus:stream:{symbol}:signals`) trong `live_engine.py` và `strategy_executor.py`: sẵn pattern phân luồng theo symbol.
- `trace_id`/dedupe trong `orders.py`: có nền tảng để giữ idempotency strict per symbol+candle.

### Established Patterns
- Event-driven qua Redis Streams (`xreadgroup`, `xack`) là pattern runtime chính.
- Luồng hiện tại vẫn có đoạn xử lý tuần tự trong vòng lặp đọc stream; lock theo symbol đang dùng như bảo vệ critical section.
- Strategy executor đã tách per-symbol state/registry nhưng vẫn chạy trong consumer loop tập trung.

### Integration Points
- Điểm cắm chính để song song hóa signal: `run_signal_engine()` trong `live_engine.py`.
- Điểm cắm chính để song song hóa strategy: main loop trong `strategy_executor.py`.
- Điểm liên quan consistency/idempotency: `orders.py` (trace_id, duplicate guard).
- Điểm rollout safety: feature flags + health/backlog metrics quanh consumer loops.

</code_context>

<specifics>
## Specific Ideas

- Người dùng muốn tập trung tuyệt đối vào mục tiêu: **xử lý song song signal/strategy đa symbol**; không gộp thêm các todo cleanup logic tín hiệu khác trong phase này.
- Ưu tiên của người dùng: **correctness trước latency** khi hệ thống bị quá tải.
- Chính sách out-of-order được chốt dứt khoát: **drop candle trễ**.

</specifics>

<deferred>
## Deferred Ideas

### Reviewed Todos (not folded)
- `2026-03-28-investigate-sweep-triggers-after-broken-pending.md` — không fold vào phase 45 vì là luồng điều tra signal quality riêng, không thuộc trọng tâm song song hóa runtime.
- `2026-03-28-remove-market-regime-use-htf-trend.md` — không fold vào phase 45 vì là cleanup/điều chỉnh logic tín hiệu, tách phase để tránh loãng scope.

</deferred>

---

*Phase: 45-h-tr-x-ly-song-song-signal-strategy-cho-nhi-u-symbol-m-t*
*Context gathered: 2026-04-18*