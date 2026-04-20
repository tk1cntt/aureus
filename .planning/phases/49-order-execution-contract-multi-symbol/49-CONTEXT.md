# Phase 49: order-execution-contract-multi-symbol - Context

**Gathered:** 2026-04-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Chuẩn hóa `ORDER_OPEN` payload contract và execution consume path multi-symbol để loại bỏ reject sai, loại bỏ hardcode `XAUUSD`, và đảm bảo luồng live `orders.py -> execution_client.py -> execution stream` chạy đúng theo từng symbol trong runtime hiện tại.

Không mở rộng scope sang capability mới (new risk engine, new order types, UI mới, hoặc redesign service boundary).

</domain>

<decisions>
## Implementation Decisions

### ORDER_OPEN Contract Completeness
- **D-01:** Chuẩn hóa payload `ORDER_OPEN` theo contract-first, coi `trace_id`, `symbol`, `side`, `qty` là critical fields bắt buộc; không fallback âm thầm cho các field này.
- **D-02:** Nhóm optional control fields (`entry_policy`, `expiry_policy`, `backfill_status`) giữ backward-compatible nhưng phải có semantics rõ: fallback có đo đếm metric và có đường nâng chuẩn dần.
- **D-03:** `strategy_id` và `strategy_name` phải được giữ xuyên suốt trong payload/event path để truy vết reject/accept theo strategy khi multi-symbol.

### Multi-Symbol Stream & Consume Path
- **D-04:** Execution client phải discover/poll theo pattern multi-symbol (`aureus:stream:*:orders`) với per-stream last_id, không hardcode stream đơn `XAUUSD`.
- **D-05:** Chặn sai lệch `symbol` giữa stream và payload bằng reject có reason code ổn định (`SYMBOL_STREAM_MISMATCH`), tránh consume nhầm symbol.
- **D-06:** Whitelist symbol vẫn là guardrail runtime, nhưng cấu hình phải mang tính multi-symbol thực tế (không mặc định logic chỉ phù hợp 1 symbol duy nhất).

### Integration Semantics (Signal → Bridge/Node)
- **D-07:** Mapping intent/event giữa signal/bridge/node phải thống nhất định danh order fields (`quantity/qty`, `type`, `event_time`) để không tạo reject giả do lệch shape.
- **D-08:** Luồng bridge khi nhận lifecycle report phải ưu tiên giữ correlation/strategy context từ order intent đã đăng ký; chỉ synthesize fallback tối thiểu khi thiếu dữ liệu.

### Reliability & Observability
- **D-09:** Mọi reject quan trọng trong execution path cần reason code machine-readable + metric counter để verifier có thể chứng minh đóng gap bằng evidence.
- **D-10:** Ưu tiên minimum-change wiring trên path hiện có (`orders.py`, `execution_client.py`, `mapper.py`, `main.py`) thay vì tách service mới.

### Claude's Discretion
- Tên helper nội bộ để normalize field mapping (`qty`/`quantity`) miễn không phá contract cũ.
- Cách tổ chức test matrix (unit/integration) để chứng minh đủ 3 gap integration của phase 49.
- Mức refactor nhỏ nhất để loại bỏ hardcode `XAUUSD` mà không lan sang scope khác.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope + requirement traceability
- `.planning/ROADMAP.md` (Phase 49 section) — goal, dependencies, 3 integration gaps cần đóng.
- `.planning/REQUIREMENTS.md` — ORDER-01..03 + PH45-05..07 traceability cho phase 49.
- `.planning/PROJECT.md` — milestone v1.5 boundary và out-of-scope guardrails.

### Prior decisions that constrain Phase 49
- `.planning/phases/29-mt5-order-execution-service/29-CONTEXT.md` — idempotency/retry/mapping decisions từ order execution baseline.
- `.planning/phases/45-h-tr-x-ly-song-song-signal-strategy-cho-nhi-u-symbol-m-t-/45-CONTEXT.md` — per-symbol runtime/FIFO/idempotency constraints cần giữ khi đi qua execution path.
- `.planning/phases/48-performance-backtest-api-wiring/48-CONTEXT.md` — minimum-change wiring principle và contract consistency pattern.
- `.planning/phases/48-performance-backtest-api-wiring/48-VERIFICATION.md` — bằng chứng verifier gần nhất về contract-first + error envelope discipline.

### Runtime code paths (source of truth)
- `services/aureus-signal/engine/orders.py` — phát sinh `ORDER_OPEN` payload và publish vào `aureus:stream:{symbol}:orders`.
- `services/aureus-nautilus-node/execution_client.py` — `_poll_loop`, `_discover_order_streams`, `_validate_and_build_orders` consume/validate multi-symbol orders.
- `services/aureus-nautilus-node/settings.py` — whitelist/pattern cấu hình runtime cho multi-symbol.
- `services/aureus-nautilus-bridge/mapper.py` — `map_order_intent` + `build_execution_event` field mapping.
- `services/aureus-nautilus-bridge/main.py` — bridge processor, stream discovery, publish execution events.

### Verification baseline artifacts
- `.planning/phases/47-verification-backfill-v1-5/47-02-SUMMARY.md` — deferred integration notes dẫn sang phase 48/49.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `orders.py` đã có khung reject reason codes + order-plan validation + publish stream theo symbol.
- `execution_client.py` đã có stream discovery pattern và metrics reject tương đối đầy đủ để gắn thêm evidence verifier.
- `mapper.py`/`main.py` ở bridge đã tách mapper + processor, thuận lợi cho sửa contract mapping tại một điểm tập trung.

### Established Patterns
- Event-driven qua Redis Streams (`aureus:stream:{symbol}:orders` -> consume -> `aureus:stream:{symbol}:execution`).
- Contract validation theo reason code machine-readable trong execution client.
- Runtime guardrails theo symbol whitelist và per-stream sequencing (`last_id`) để giữ deterministic consume behavior.

### Integration Points
- Điểm nối chính 1: `SimulatedTradeManager.process_triggers()` trong `orders.py` -> event `ORDER_OPEN`.
- Điểm nối chính 2: `AureusExecutionClient._handle_message/_validate_and_build_orders()` trong node.
- Điểm nối chính 3: `map_order_intent` + `BridgeProcessor` path trong bridge cho lifecycle/report mapping.

</code_context>

<specifics>
## Specific Ideas

- Ưu tiên fix theo triết lý “minimum-change wiring” đã dùng ở phase 48: vá đúng path contract và consume, không redesign hệ thống.
- Evidence thành công phase 49 phải thể hiện được: cùng logic chạy được trên nhiều symbol, không còn fallback/hardcode gây bias `XAUUSD`.

</specifics>

<deferred>
## Deferred Ideas

### Reviewed Todos (not folded)
- `2026-03-28-investigate-sweep-triggers-after-broken-pending.md` — không fold vào phase 49 (liên quan signal quality investigation, không phải order execution contract wiring).
- `2026-03-28-remove-market-regime-use-htf-trend.md` — không fold vào phase 49 (cleanup strategy logic ngoài boundary ORDER contract multi-symbol).

</deferred>

---

*Phase: 49-order-execution-contract-multi-symbol*
*Context gathered: 2026-04-20*
