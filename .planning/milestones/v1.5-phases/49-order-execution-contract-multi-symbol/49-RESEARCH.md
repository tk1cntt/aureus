# Phase 49: order-execution-contract-multi-symbol - Research

**Researched:** 2026-04-20
**Domain:** ORDER_OPEN contract normalization + multi-symbol execution consume path (Redis Streams)
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
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

### Deferred Ideas (OUT OF SCOPE)
### Reviewed Todos (not folded)
- `2026-03-28-investigate-sweep-triggers-after-broken-pending.md` — không fold vào phase 49 (liên quan signal quality investigation, không phải order execution contract wiring).
- `2026-03-28-remove-market-regime-use-htf-trend.md` — không fold vào phase 49 (cleanup strategy logic ngoài boundary ORDER contract multi-symbol).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ORDER-01 | aureus-trader service nhận strategy match từ Redis pub/sub | Chuẩn hóa shape `ORDER_OPEN` từ `orders.py` và consume path Redis Streams để execution client nhận đúng dữ liệu theo symbol [VERIFIED: D:/Aureus/services/aureus-signal/engine/orders.py; D:/Aureus/services/aureus-nautilus-node/execution_client.py] |
| ORDER-02 | Tạo và gửi market order xuống MT5 qua TCP | Preserve mapping field bắt buộc (`trace_id/symbol/side/qty`) và conversion sang execution orders (ENTRY/SL/TP) để flow tới execution không reject giả [VERIFIED: D:/Aureus/services/aureus-nautilus-node/execution_client.py] |
| ORDER-03 | Tạo và gửi pending order (limit/stop) xuống MT5 qua TCP | `type` mapping hiện đã hỗ trợ MARKET/LIMIT/STOP trong bridge mapper; cần giữ contract nhất quán từ signal->bridge->node [VERIFIED: D:/Aureus/services/aureus-nautilus-bridge/mapper.py] |
| PH45-05 | Idempotency strict theo `trace_id` cho `symbol + strategy + origin_timestamp` | `orders.py` tạo trace_id theo symbol+strategy_id+origin_t; execution client đã reject duplicate trace_id [VERIFIED: D:/Aureus/services/aureus-signal/engine/orders.py; D:/Aureus/services/aureus-nautilus-node/execution_client.py] |
| PH45-06 | Circuit-breaker + backlog threshold độc lập theo từng symbol | Multi-stream discover/poll + per-stream last_id là nền để metrics/reject per-symbol có ý nghĩa vận hành [VERIFIED: D:/Aureus/services/aureus-nautilus-node/execution_client.py] |
| PH45-07 | Shadow -> Canary -> Full với auto-rollback theo SLO per-symbol | Phase 49 cần giữ reject reason code/metrics machine-readable để rollout gate và rollback evidence theo symbol [VERIFIED: D:/Aureus/services/aureus-nautilus-node/execution_client.py; CITED: .planning/REQUIREMENTS.md] |
</phase_requirements>

## Summary

Phase 49 là phase đóng gap integration chứ không phải phase thêm capability mới. Trục chính là đồng bộ contract `ORDER_OPEN` giữa producer (`orders.py`) và consumer (`execution_client.py`) theo multi-symbol runtime, đồng thời loại bỏ các điểm hardcode `XAUUSD` còn sót ở execution path [VERIFIED: D:/Aureus/.planning/phases/49-order-execution-contract-multi-symbol/49-CONTEXT.md; D:/Aureus/services/aureus-nautilus-node/execution_client.py].

Hiện trạng cho thấy nhiều nền tảng đã sẵn: `orders.py` đã publish theo `aureus:stream:{symbol}:orders`, có `trace_id/strategy_id/strategy_name`, có optional metadata (`entry_policy`, `expiry_policy`, `backfill_status`) [VERIFIED: D:/Aureus/services/aureus-signal/engine/orders.py]. `execution_client.py` đã có stream discovery theo pattern `aureus:stream:*:orders`, per-stream `last_id`, reject reason `SYMBOL_STREAM_MISMATCH`, metrics reject chi tiết [VERIFIED: D:/Aureus/services/aureus-nautilus-node/execution_client.py].

Gap chính còn lại để planner bẻ task: (1) chuẩn hóa field-name xuyên service (`qty` vs `quantity`) để tránh reject giả; (2) xóa fallback/hardcode XAUUSD trong default policy/discovery; (3) củng cố test matrix multi-symbol + contract mismatch để chứng minh đóng 3 integration gaps đã nêu trong roadmap [VERIFIED: D:/Aureus/.planning/ROADMAP.md; D:/Aureus/services/aureus-nautilus-bridge/mapper.py; D:/Aureus/services/aureus-nautilus-node/tests/test_execution_client_policy.py].

**Primary recommendation:** Triển khai “minimum-change contract adapter” tại biên consume (`execution_client._validate_and_build_orders`) để chấp nhận có kiểm soát cả `qty` và `quantity`, đồng thời loại toàn bộ default XAUUSD trong execution settings/policy/discovery; giữ reject reasons + metrics hiện có làm evidence rollout [VERIFIED: D:/Aureus/services/aureus-nautilus-node/execution_client.py; D:/Aureus/services/aureus-nautilus-node/settings.py].

## Project Constraints (from CLAUDE.md)

- Mọi trao đổi dùng tiếng Việt [VERIFIED: D:/Aureus/CLAUDE.md].
- Khi command lỗi, tham khảo RUN_SERVICES.md [VERIFIED: D:/Aureus/CLAUDE.md].
- Giữ thay đổi tối giản, không mở rộng scope, không refactor lan ngoài yêu cầu [VERIFIED: D:/Aureus/CLAUDE.md].
- Chỉ sửa các dòng truy vết trực tiếp tới yêu cầu phase; không cleanup lân cận không liên quan [VERIFIED: D:/Aureus/CLAUDE.md].
- Với code-modification tasks: bắt buộc GitNexus impact trước sửa symbol và detect_changes trước commit [VERIFIED: D:/Aureus/CLAUDE.md].

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| redis (Python) | 7.2.0 (repo pin), latest 7.4.0 | Redis Streams pub/sub + xread/xadd/scan [VERIFIED: D:/Aureus/services/aureus-nautilus-bridge/requirements.txt; VERIFIED: PyPI redis] | Core transport đã dùng xuyên signal/node/bridge; không nên hand-roll broker [VERIFIED: D:/Aureus/services/aureus-signal/engine/orders.py; D:/Aureus/services/aureus-nautilus-node/execution_client.py] |
| Python runtime | 3.10.11 (available) | Runtime cho services phase 49 [VERIFIED: local command `python3 --version`] | Đồng bộ với test/runtime hiện có [VERIFIED: local command `pytest --version`] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | 9.0.2 available, latest 9.0.3 | Unit/integration contract tests cho execution/bridge [VERIFIED: local command `pytest --version`; VERIFIED: PyPI pytest] | Bắt buộc cho test matrix đóng gap integration |
| pydantic | 2.12.5 (bridge pin), latest 2.13.3 | Data validation/modeling ở bridge service [VERIFIED: D:/Aureus/services/aureus-nautilus-bridge/requirements.txt; VERIFIED: PyPI pydantic] | Khi cần envelope validation explicit cho payload evolution |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| redis streams scan + xread trong node hiện tại | Separate execution-router service | Tăng boundary/system complexity, trái D-10 minimum-change [VERIFIED: D:/Aureus/.planning/phases/49-order-execution-contract-multi-symbol/49-CONTEXT.md] |

**Installation:**
```bash
pip install redis pytest pydantic
```

**Version verification:**
```bash
python3 -c "import json,urllib.request;print(json.load(urllib.request.urlopen('https://pypi.org/pypi/redis/json'))['info']['version'])"
python3 -c "import json,urllib.request;print(json.load(urllib.request.urlopen('https://pypi.org/pypi/pydantic/json'))['info']['version'])"
python3 -c "import json,urllib.request;print(json.load(urllib.request.urlopen('https://pypi.org/pypi/pytest/json'))['info']['version'])"
```

## Architecture Patterns

### Recommended Project Structure
```text
services/
├── aureus-signal/engine/            # ORDER_OPEN producer
├── aureus-nautilus-node/            # execution consume + risk policy
└── aureus-nautilus-bridge/          # intent/event mapping + lifecycle bridging
```

### Pattern 1: Contract-first consume with deterministic reject codes
**What:** Validate critical fields trước khi generate orders; reject có reason code ổn định.
**When to use:** Mọi event `ORDER_OPEN` vào execution.
**Example:**
```python
# Source: D:/Aureus/services/aureus-nautilus-node/execution_client.py
for field in ("trace_id", "symbol", "side", "qty"):
    ...
if missing_critical_fields:
    return False, "ORDER_OPEN_MISSING_CRITICAL_FIELD", [], []
```

### Pattern 2: Multi-stream discovery with per-stream cursor
**What:** Poll nhiều stream `aureus:stream:*:orders` và giữ `_last_ids` theo stream.
**When to use:** Runtime multi-symbol.
**Example:**
```python
# Source: D:/Aureus/services/aureus-nautilus-node/execution_client.py
streams = await self._discover_order_streams()
result = await self.redis_client.xread(streams, count=10, block=1000)
self._last_ids[stream_str] = message_id
```

### Anti-Patterns to Avoid
- **Hardcode symbol singleton (`XAUUSD`) ở default runtime path:** gây bias consume và reject sai khi mở rộng symbol [VERIFIED: D:/Aureus/services/aureus-nautilus-node/execution_client.py; D:/Aureus/services/aureus-nautilus-node/settings.py].
- **Field-shape drift (`qty` vs `quantity`) giữa signal/node/bridge:** làm fail mapping/reject giả [VERIFIED: D:/Aureus/services/aureus-nautilus-node/execution_client.py; D:/Aureus/services/aureus-nautilus-bridge/mapper.py].

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Message transport + fanout | Custom socket queue | Redis Streams pattern hiện hữu | Đã có semantics stream/cursor/group và đang chạy production path [VERIFIED: D:/Aureus/services/aureus-signal/engine/orders.py; D:/Aureus/services/aureus-nautilus-bridge/main.py] |
| Runtime dedupe | Custom in-memory global dedupe service | trace_id + existing dedupe/reject metrics | Đã có trace_id strict theo phase constraints và reject duplicate sẵn [VERIFIED: D:/Aureus/services/aureus-signal/engine/orders.py; D:/Aureus/services/aureus-nautilus-node/execution_client.py] |

**Key insight:** Phase này là gap-closure wiring; thêm service/abstraction mới sẽ tăng rủi ro integration drift mà không giúp đạt goal nhanh hơn [VERIFIED: D:/Aureus/.planning/phases/49-order-execution-contract-multi-symbol/49-CONTEXT.md].

## Common Pitfalls

### Pitfall 1: Critical field mismatch giữa producer và consumer
**What goes wrong:** Producer gửi `volume/quantity` nhưng consumer bắt buộc `qty` -> reject `ORDER_OPEN_MISSING_CRITICAL_FIELD`.
**Why it happens:** Contract chưa canonical hóa ở biên consume.
**How to avoid:** Chọn canonical field (`qty`) và alias một chiều có metric/fallback counter.
**Warning signs:** reject_total tăng + reason missing critical field, trong khi payload vẫn có volume-like field [VERIFIED: D:/Aureus/services/aureus-nautilus-node/execution_client.py; D:/Aureus/services/aureus-signal/engine/orders.py].

### Pitfall 2: Symbol leakage từ default XAUUSD
**What goes wrong:** Runtime vẫn đọc/poll stream XAUUSD dù whitelist thực tế đã multi-symbol.
**Why it happens:** default constructor/settings fallback để `XAUUSD`.
**How to avoid:** ép cấu hình symbol whitelist explicit từ env cho mọi runtime mode phase 49.
**Warning signs:** logs luôn chứa `aureus:stream:XAUUSD:orders` dù test đang chạy symbol khác [VERIFIED: D:/Aureus/services/aureus-nautilus-node/execution_client.py; D:/Aureus/services/aureus-nautilus-node/settings.py].

### Pitfall 3: Mất lineage strategy trong lifecycle fallback
**What goes wrong:** execution event thiếu `strategy_id/correlation_id` khi lifecycle report tới trước/không có pending intent.
**Why it happens:** fallback payload synthesize thiếu context.
**How to avoid:** ưu tiên reuse pending_intents + merge lineage fields từ report.
**Warning signs:** event có trace_id nhưng strategy_id rỗng [VERIFIED: D:/Aureus/services/aureus-nautilus-bridge/main.py; D:/Aureus/services/aureus-nautilus-bridge/tests/test_bridge_lineage.py].

## Code Examples

### Producer publishes ORDER_OPEN per symbol
```python
# Source: D:/Aureus/services/aureus-signal/engine/orders.py
await self.r.xadd(f"aureus:stream:{symbol}:orders", {
    "type": stream_type,
    "data": json.dumps(order)
})
```

### Consumer rejects symbol-stream mismatch deterministically
```python
# Source: D:/Aureus/services/aureus-nautilus-node/execution_client.py
if stream_symbol and symbol != stream_symbol:
    self.metrics["order_open_reject_symbol_mismatch_total"] += 1
    return False, "SYMBOL_STREAM_MISMATCH", [], []
```

### Bridge mapping currently expects quantity
```python
# Source: D:/Aureus/services/aureus-nautilus-bridge/mapper.py
"quantity": float(order_payload.get("quantity", 1.0)),
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single-symbol mental model (`XAUUSD`) in defaults | Multi-symbol stream pattern (`aureus:stream:*:orders`) + per-stream last_id | Đã hiện diện trước phase 49; roadmap xác nhận gap closure cần hoàn tất | Phase 49 chỉ cần xóa phần hardcode còn sót + test chứng minh [VERIFIED: D:/Aureus/services/aureus-nautilus-node/execution_client.py; D:/Aureus/.planning/ROADMAP.md] |

**Deprecated/outdated:**
- “Assume quantity field name is uniform across services” — không đúng với code hiện tại (`qty` ở node, `quantity` ở bridge) [VERIFIED: D:/Aureus/services/aureus-nautilus-node/execution_client.py; D:/Aureus/services/aureus-nautilus-bridge/mapper.py].

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Alias `qty`/`quantity` nên xử lý tại execution consume boundary thay vì producer | Architecture Patterns | Có thể tạo duplicate normalization path nếu codebase đã có canonical adapter khác [ASSUMED] |
| A2 | Không cần migration dữ liệu lịch sử vì phase 49 chủ yếu xử lý live stream contract | Summary | Có thể bỏ sót replay/backfill flows nếu có consumer đọc lịch sử stream [ASSUMED] |

## Open Questions (RESOLVED)

1. **Canonical field cuối cùng cho volume là `qty` hay `quantity`? — RESOLVED**
   - Decision: Canonical field tại execution consume boundary là `qty`; bridge mapper vẫn chấp nhận alias `quantity|qty` và canonicalize output intent về `quantity` để tương thích backward path.
   - Rationale: Giữ minimum-change wiring theo runtime hiện tại (`execution_client` dùng `qty`) đồng thời đóng mismatch liên-service bằng adapter một chiều + regression tests.

2. **Có cần giữ fallback stream `aureus:stream:XAUUSD:orders` khi discovery rỗng? — RESOLVED**
   - Decision: Không giữ fallback hardcode `aureus:stream:XAUUSD:orders`; discovery/poll hoàn toàn theo pattern + whitelist cấu hình multi-symbol.
   - Rationale: Loại bias singleton XAUUSD, phù hợp D-04/D-06 và được khóa bằng test contract multi-symbol/cursor độc lập.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| python3 | service runtime + pytest | ✓ | 3.10.11 | — |
| pytest | contract/unit tests | ✓ | 9.0.2 | `python3 -m pytest ...` |
| node/npm | script tooling (không critical cho service python) | ✓ | node v22.22.0 / npm 11.12.0 | — |
| redis-cli | local Redis probing | ✗ | — | dùng integration tests với mocked redis client |

**Missing dependencies with no fallback:**
- None blocking cho planning stage [VERIFIED: local command outputs].

**Missing dependencies with fallback:**
- `redis-cli` thiếu, nhưng test phase có thể dùng AsyncMock/unit contract tests [VERIFIED: D:/Aureus/services/aureus-nautilus-node/tests/test_execution_client.py].

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (Python) [VERIFIED: local command `pytest --version`] |
| Config file | `D:/Aureus/services/aureus-gateway/tests/pytest.ini` (global pytest.ini riêng cho gateway; các service khác dùng pytest defaults) [VERIFIED: glob result] |
| Quick run command | `python3 -m pytest D:/Aureus/services/aureus-nautilus-node/tests/test_execution_client.py -q -x` |
| Full suite command | `python3 -m pytest D:/Aureus/services/aureus-nautilus-node/tests D:/Aureus/services/aureus-nautilus-bridge/tests -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ORDER-01 | Consume ORDER_OPEN đúng contract và generate orders | unit | `python3 -m pytest D:/Aureus/services/aureus-nautilus-node/tests/test_execution_client.py -q -x` | ✅ |
| ORDER-02 | ENTRY + SL/TP contingent generation cho market flow | unit | `python3 -m pytest D:/Aureus/services/aureus-nautilus-node/tests/test_execution_risk_controls.py::test_valid_order_generates_entry_plus_sl_tp_contingents -q` | ✅ |
| ORDER-03 | Type/order intent mapping support cho pending semantics | unit | `python3 -m pytest D:/Aureus/services/aureus-nautilus-bridge/tests/test_mapper.py -q -x` | ✅ |
| PH45-05 | Reject duplicate trace_id strict | unit | `python3 -m pytest D:/Aureus/services/aureus-nautilus-node/tests/test_execution_risk_controls.py::test_duplicate_trace_id_is_ignored -q` | ✅ |
| PH45-06 | Multi-symbol stream polling + symbol mismatch guard | unit/integration-lite | `python3 -m pytest D:/Aureus/services/aureus-nautilus-node/tests/test_execution_client_policy.py -q -x` | ✅ |
| PH45-07 | Idempotency/lineage evidence phục vụ rollout gate per-symbol | unit | `python3 -m pytest D:/Aureus/services/aureus-nautilus-bridge/tests/test_bridge_idempotency.py D:/Aureus/services/aureus-nautilus-bridge/tests/test_bridge_lineage.py -q` | ✅ |

### Sampling Rate
- **Per task commit:** `python3 -m pytest D:/Aureus/services/aureus-nautilus-node/tests/test_execution_client.py D:/Aureus/services/aureus-nautilus-node/tests/test_execution_client_policy.py -q`
- **Per wave merge:** `python3 -m pytest D:/Aureus/services/aureus-nautilus-node/tests D:/Aureus/services/aureus-nautilus-bridge/tests -q`
- **Phase gate:** Full suite green trước `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `D:/Aureus/services/aureus-nautilus-node/tests/test_execution_multi_symbol_contract.py` — dedicated tests cho `qty`/`quantity` compatibility + XAUUSD fallback removal [ASSUMED]
- [ ] `D:/Aureus/services/aureus-nautilus-bridge/tests/test_order_payload_qty_alias.py` — explicit mapper compatibility test cho volume naming [ASSUMED]

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | N/A for internal stream contract path [ASSUMED] |
| V3 Session Management | no | N/A for this phase scope [ASSUMED] |
| V4 Access Control | yes | Symbol whitelist guard trong execution client [VERIFIED: D:/Aureus/services/aureus-nautilus-node/execution_client.py] |
| V5 Input Validation | yes | Critical-field validation + typed coercion + reject reasons [VERIFIED: D:/Aureus/services/aureus-nautilus-node/execution_client.py; D:/Aureus/services/aureus-nautilus-bridge/mapper.py] |
| V6 Cryptography | no | Không có crypto change trong phase 49 scope [VERIFIED: D:/Aureus/.planning/phases/49-order-execution-contract-multi-symbol/49-CONTEXT.md] |

### Known Threat Patterns for Redis-stream execution stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Payload tampering / malformed JSON | Tampering | Parse+validate; reject `MALFORMED_PAYLOAD` và không generate order [VERIFIED: D:/Aureus/services/aureus-nautilus-node/execution_client.py] |
| Cross-symbol injection (wrong stream vs payload symbol) | Spoofing/Tampering | Reject `SYMBOL_STREAM_MISMATCH` + counter metric [VERIFIED: D:/Aureus/services/aureus-nautilus-node/execution_client.py] |
| Replay/duplicate ORDER_OPEN | Replay | `_seen_trace_ids` reject duplicate trace_id [VERIFIED: D:/Aureus/services/aureus-nautilus-node/execution_client.py] |

## Sources

### Primary (HIGH confidence)
- `D:/Aureus/.planning/phases/49-order-execution-contract-multi-symbol/49-CONTEXT.md` - locked decisions/scope for phase 49.
- `D:/Aureus/.planning/ROADMAP.md` - phase goal, gap-closure targets, requirement links.
- `D:/Aureus/.planning/REQUIREMENTS.md` - ORDER-01..03, PH45-05..07 requirement definitions.
- `D:/Aureus/services/aureus-signal/engine/orders.py` - producer payload fields, stream publish pattern.
- `D:/Aureus/services/aureus-nautilus-node/execution_client.py` - multi-stream polling, validation, reject reasons, metrics.
- `D:/Aureus/services/aureus-nautilus-node/settings.py` - symbol whitelist and stream pattern defaults.
- `D:/Aureus/services/aureus-nautilus-bridge/mapper.py` - field mapping (`quantity`, `event_time`, `type`).
- `D:/Aureus/services/aureus-nautilus-bridge/main.py` - bridge lifecycle handling + lineage retention.
- `D:/Aureus/services/aureus-nautilus-node/tests/test_execution_client.py`
- `D:/Aureus/services/aureus-nautilus-node/tests/test_execution_client_policy.py`
- `D:/Aureus/services/aureus-nautilus-node/tests/test_execution_risk_controls.py`
- `D:/Aureus/services/aureus-nautilus-bridge/tests/test_mapper.py`
- `D:/Aureus/services/aureus-nautilus-bridge/tests/test_bridge_idempotency.py`
- `D:/Aureus/services/aureus-nautilus-bridge/tests/test_bridge_lineage.py`
- PyPI JSON API: `https://pypi.org/pypi/redis/json`, `https://pypi.org/pypi/pydantic/json`, `https://pypi.org/pypi/pytest/json` - latest package versions + upload time.

### Secondary (MEDIUM confidence)
- None.

### Tertiary (LOW confidence)
- None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - versions verified from repo pins + PyPI queries.
- Architecture: HIGH - derived trực tiếp từ runtime code paths và tests hiện có.
- Pitfalls: HIGH - dựa trên mismatch/hardcode patterns xác nhận trong code.

**Research date:** 2026-04-20
**Valid until:** 2026-05-20 (30 days)
