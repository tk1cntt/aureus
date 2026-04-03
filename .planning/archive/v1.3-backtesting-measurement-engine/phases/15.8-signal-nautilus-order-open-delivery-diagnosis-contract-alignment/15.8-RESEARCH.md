# Phase 15.8: Signal→Nautilus order-open delivery diagnosis & contract alignment — Research

## Objective
Khoanh vùng điểm đứt chính trong chuỗi `aureus-signal` → Redis stream orders → Nautilus consumer runtime, đồng thời chốt contract stream/symbol và payload `ORDER_OPEN` để phase execution có thể sửa đúng trọng tâm.

## Scope
- Runtime chain: producer `aureus-signal` → stream `aureus:stream:{symbol}:orders` → consumer `aureus-nautilus-node`/`aureus-nautilus-bridge`
- Contract alignment: stream/symbol routing + payload required/optional/fallback
- Observability alignment: reject reason-code taxonomy + metric buckets

## Key Findings (Current Code)
1. `services/aureus-signal/engine/orders.py` publish event theo stream động theo symbol: `aureus:stream:{symbol}:orders`.
2. `services/aureus-nautilus-node/execution_client.py` đang poll fixed stream `aureus:stream:XAUUSD:orders`.
3. `services/aureus-nautilus-node/main.py` báo warning auxiliary execution pipeline chưa được start trong runtime chính.
4. `services/aureus-nautilus-bridge/main.py` quét wildcard `aureus:stream:*:orders`, nên hỗ trợ multi-symbol tốt hơn node execution client hiện tại.
5. Validation ở execution side khá strict; payload drift dễ dẫn tới reject nếu thiếu trường bắt buộc.

## Prioritized Hypotheses
1. **H1 — Wiring gap:** runtime node không start execution pipeline nên không consume được order-open path như kỳ vọng.
2. **H2 — Stream mismatch:** producer dùng dynamic symbol stream nhưng consumer node poll stream fixed `XAUUSD`.
3. **H3 — Symbol contract drift:** `payload.symbol` và stream-key symbol có thể lệch; hiện chưa có cross-check taxonomy rõ ràng.
4. **H4 — Payload contract drift:** thiếu trường mới hoặc naming mismatch gây reject trước khi tới execution.

## Recommended Technical Approach
1. Giữ `aureus-nautilus-bridge` làm ingress chuẩn cho multi-symbol; node execution client chỉ bật khi explicit mode/flag.
2. Chuẩn hóa stream discovery theo wildcard + allowlist symbol config (không hardcode `XAUUSD`).
3. Chốt `payload.symbol` là source-of-truth; stream symbol chỉ dùng cross-check, mismatch => reject có reason-code + metric.
4. Áp dụng compatibility fallback có kiểm soát cho optional fields; hard reject chỉ cho critical fields (`trace_id`, `symbol`, `side`, `qty`, và SL/TP khi required).
5. Chuẩn hóa reason-code taxonomy chung producer/consumer để truy được reject bucket end-to-end.

## Validation Architecture
### Evidence checkpoints
- CP-A: Producer publish stream đúng symbol runtime (`XAUUSD`, `ETHUSD`) và payload có trường critical.
- CP-B: Consumer discovery tìm thấy stream runtime (không bỏ sót stream không phải `XAUUSD`).
- CP-C: Contract validation phân loại đúng `critical_missing` vs `optional_fallback` vs `symbol_mismatch`.
- CP-D: Observability xuất log + metric bucket nhất quán cho mỗi reject/pass path.

### Minimum test matrix for execution phase
1. Multi-symbol publish: cả `XAUUSD` và `ETHUSD` đều đi vào consumer pipeline đúng.
2. Missing optional field: sự kiện vẫn qua được với warning metric.
3. Missing critical field: reject đúng reason-code và counter.
4. Symbol mismatch payload-vs-stream: reject theo taxonomy đã chốt.

## Research Outcome
Phase 15.8 nên đi theo hướng **contract-first diagnosis**: khóa stream/symbol contract và payload contract trước, rồi mới chỉnh runtime wiring để tránh fix lệch symptom.
