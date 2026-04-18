# Phase 45: h-tr-x-ly-song-song-signal-strategy-cho-nhi-u-symbol-m-t- - Research

**Researched:** 2026-04-18
**Domain:** Parallel multi-symbol signal + strategy execution trong `aureus-signal`
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
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

### Deferred Ideas (OUT OF SCOPE)
### Reviewed Todos (not folded)
- `2026-03-28-investigate-sweep-triggers-after-broken-pending.md` — không fold vào phase 45 vì là luồng điều tra signal quality riêng, không thuộc trọng tâm song song hóa runtime.
- `2026-03-28-remove-market-regime-use-htf-trend.md` — không fold vào phase 45 vì là cleanup/điều chỉnh logic tín hiệu, tách phase để tránh loãng scope.
</user_constraints>

## Project Constraints (from CLAUDE.md)

- Mọi trao đổi và tài liệu phase dùng tiếng Việt. [VERIFIED: codebase Read /d/Aureus/CLAUDE.md]
- Chỉ thay đổi tối thiểu đúng scope, không kéo cleanup/refactor ngoài yêu cầu. [VERIFIED: codebase Read /d/Aureus/CLAUDE.md]
- Ưu tiên đơn giản, tránh abstraction thừa chưa được yêu cầu. [VERIFIED: codebase Read /d/Aureus/CLAUDE.md]
- Trước khi sửa symbol phải chạy impact analysis bằng GitNexus; trước commit phải chạy detect_changes. [VERIFIED: codebase Read /d/Aureus/CLAUDE.md]
- Nếu command lỗi, tham chiếu RUN_SERVICES.md để phục hồi/chạy hệ thống. [VERIFIED: codebase Read /d/Aureus/CLAUDE.md]

## Summary

Hiện trạng đã có nền tảng per-symbol khá mạnh ở cả signal engine và strategy executor: stream đã tách theo symbol (`aureus:stream:{symbol}:candle`, `aureus:stream:{symbol}:signals`), lock theo symbol đã có trong signal engine, và registry/state đã tách theo symbol. [VERIFIED: codebase Read /d/Aureus/services/aureus-signal/engine/live_engine.py] [VERIFIED: codebase Read /d/Aureus/services/aureus-signal/engine/strategy_executor.py]

Điểm nghẽn chính là cả 2 service vẫn dùng vòng lặp consumer tập trung, xử lý entry theo batch stream rồi lồng loop theo entry; nghĩa là chưa có worker lifecycle riêng, backlog/SLO/circuit-breaker cũng chưa tách rõ theo symbol cho toàn pipeline signal+strategy. [VERIFIED: codebase Read /d/Aureus/services/aureus-signal/engine/live_engine.py] [VERIFIED: codebase Read /d/Aureus/services/aureus-signal/engine/strategy_executor.py]

Vì vậy, plan phase 45 nên chuyển sang kiến trúc `router + per-symbol worker queue` ở cả aggregator và executor, giữ FIFO strict trong queue từng symbol, drop out-of-order tại ingress theo `last_executed_candle_t`, buộc snapshot-cùng-candle bằng payload contract hiện có, và thêm rollback tự động theo SLO per-symbol bằng feature flags runtime. [VERIFIED: codebase Read /d/Aureus/services/aureus-signal/engine/live_engine.py] [VERIFIED: codebase Read /d/Aureus/services/aureus-signal/engine/orders.py]

**Primary recommendation:** Dùng kiến trúc 2 tầng `stream-router -> per-symbol FIFO worker` cho cả `run_signal_engine()` và `run_strategy_executor()`, rollout Shadow→Canary→Full với auto-fallback từng symbol theo SLO.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| asyncio (Python stdlib) | Python 3.10 runtime | Worker concurrency per symbol + queue/task lifecycle | Đang là primitive async gốc của engine, tránh thêm runtime mới. [VERIFIED: codebase Read /d/Aureus/services/aureus-signal/engine/live_engine.py] |
| redis-py asyncio | redis==7.2.0 | Redis Streams consumer-group, ACK, pub/sub | Toàn pipeline hiện tại phụ thuộc Redis Streams API (`xreadgroup`, `xack`, `xadd`). [VERIFIED: codebase Read /d/Aureus/services/aureus-signal/requirements.txt] [VERIFIED: codebase Read /d/Aureus/services/aureus-signal/engine/live_engine.py] |
| asyncpg | asyncpg==0.31.0 | Persist candle/snapshot, warmup/recalc | Đã dùng xuyên suốt signal service với pool async. [VERIFIED: codebase Read /d/Aureus/services/aureus-signal/requirements.txt] [VERIFIED: codebase Read /d/Aureus/services/aureus-signal/engine/live_engine.py] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pandas | pandas==3.0.1 | DataFrame cho signal/window calculations | Dùng trong `WindowManager` và strategy eval input. [VERIFIED: codebase Read /d/Aureus/services/aureus-signal/requirements.txt] [VERIFIED: codebase Read /d/Aureus/services/aureus-signal/engine/manager.py] |
| CircuitBreaker nội bộ | in-repo | Chặn provider lỗi | Dùng làm mẫu để mở rộng circuit-breaker per-symbol ở phase 45. [VERIFIED: codebase Grep circuit_breaker] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Redis Streams + asyncio worker | Kafka/NATS consumer groups | Quá rộng scope phase, tăng migration risk và rollback complexity. [ASSUMED] |
| Per-symbol worker queue nội bộ | Multiprocess per symbol | Nặng vận hành và khó chia sẻ state in-memory hiện tại. [ASSUMED] |

**Installation:**
```bash
pip3 install -r /d/Aureus/services/aureus-signal/requirements.txt
```

**Version verification:**
- Versions dùng để plan lấy từ lock/pin của project (`requirements.txt`), không dùng suy đoán từ training data. [VERIFIED: codebase Read /d/Aureus/services/aureus-signal/requirements.txt]

## Architecture Patterns

### Recommended Project Structure
```text
services/aureus-signal/engine/
├── live_engine.py          # stream router + signal per-symbol worker
├── strategy_executor.py    # stream router + strategy per-symbol worker
├── orders.py               # trace_id/dedupe + trigger handling
├── manager.py              # window/state per symbol
└── symbol_runtime.py       # (new) worker runtime state/SLO/circuit-breaker per symbol
```

### Pattern 1: Stream Router + Per-Symbol FIFO Worker
**What:** Main loop chỉ đọc stream và route message vào queue của symbol; worker mỗi symbol xử lý tuần tự queue đó.
**When to use:** Khi cần song song giữa symbols nhưng strict order trong từng symbol.
**Example:**
```python
# Source: /d/Aureus/services/aureus-signal/engine/live_engine.py
streams_subscription = {f"aureus:stream:{s}:candle": ">" for s in symbols_list}
messages = await r.xreadgroup(group_name, consumer_name, streams_subscription, count=500, block=5000)
# Phase 45: thay xử lý trực tiếp bằng enqueue theo symbol.
```

### Pattern 2: Strict FIFO + Out-of-order Drop at Ingress
**What:** Nếu candle `ts_unix <= last_executed_candle_t` thì drop + ack ngay.
**When to use:** Bắt buộc D-05/D-06 đúng tuyệt đối.
**Example:**
```python
# Source: /d/Aureus/services/aureus-signal/engine/live_engine.py
last_executed_t = int(state.tracking_vars.get('last_executed_candle_t', 0) or 0)
if ts_unix <= last_executed_t:
    await r.xack(stream_key, group_name, entry_id)
    continue
```

### Pattern 3: Strict snapshot cùng candle cho strategy
**What:** Emit payload từ aggregator chứa `t` + `signals_snapshot` + `current_signal` để executor đánh giá cùng candle.
**When to use:** D-07 yêu cầu consistency candle-level.
**Example:**
```python
# Source: /d/Aureus/services/aureus-signal/engine/live_engine.py
signal_payload = {"t": ts_unix, "signals_snapshot": signals_snapshot, "current_signal": state.current_signal or {}}
await r.xadd(f"aureus:stream:{symbol}:signals", {"payload": json.dumps(signal_payload, default=str)})
```

### Anti-Patterns to Avoid
- **Global lock cho mọi symbol:** làm mất song song thực sự; phải giữ lock/queue theo từng symbol. [VERIFIED: codebase Read /d/Aureus/services/aureus-signal/tests/test_multi_symbol.py]
- **Reorder window để cứu out-of-order candle:** trái với D-06 và làm sai deterministic trace. [VERIFIED: codebase Read /d/Aureus/.planning/phases/45-h-tr-x-ly-song-song-signal-strategy-cho-nhi-u-symbol-m-t-/45-CONTEXT.md]
- **ACK trước khi enqueue thành công:** có thể mất message không replay được. [ASSUMED]

## Don’t Hand-Roll

| Problem | Don’t Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Queue đa ưu tiên | Tự build broker mới | `asyncio.Queue/PriorityQueue` + Redis Streams | Stack hiện tại đã async-native, ít thay đổi nhất. [VERIFIED: codebase Read /d/Aureus/services/aureus-signal/engine/live_engine.py] |
| Dedupe trigger | Hash thủ công rải rác | `trace_id` + `aureus:orders:history:{symbol}` + recent trigger key | Đã có cơ chế idempotency hoạt động thực tế. [VERIFIED: codebase Read /d/Aureus/services/aureus-signal/engine/orders.py] |
| Circuit breaker | Logic retry tùy hứng từng call-site | Tái dùng `common/circuit_breaker.py`, instance per symbol | Tránh behavior không nhất quán giữa symbols. [VERIFIED: codebase Grep circuit_breaker] |

**Key insight:** Không cần đổi broker hoặc đổi framework; chỉ cần tách lifecycle worker/slo theo symbol trên nền Redis Streams + asyncio hiện hữu.

## Common Pitfalls

### Pitfall 1: “Parallel nhưng vẫn nghẽn do loop tập trung”
**What goes wrong:** Có nhiều symbol nhưng CPU-bound/IO-bound đoạn xử lý vẫn nằm trong một loop lớn.
**Why it happens:** Router và worker chưa tách.
**How to avoid:** Bắt buộc tách `ingress read` và `per-symbol consume` thành task riêng.
**Warning signs:** Lag tăng đồng loạt mọi symbol khi 1 symbol bị backfill/recalc nặng.

### Pitfall 2: Snapshot lệch candle giữa signal và strategy
**What goes wrong:** Strategy dùng dữ liệu candle N nhưng snapshot thuộc N-1/N+1.
**Why it happens:** Payload không kiểm tra `t` nhất quán hoặc queue reorder sai.
**How to avoid:** Assert `payload.t == state.last_candle.t` trước evaluate/process trigger.
**Warning signs:** Trace có cùng symbol nhưng `origin_timestamp` và `open_time` lệch không giải thích được.

### Pitfall 3: Rollback global thay vì per-symbol
**What goes wrong:** 1 symbol lỗi kéo toàn service về tuần tự.
**Why it happens:** SLO/circuit-breaker đặt global flag.
**How to avoid:** Flag + breaker + backlog threshold keyed by symbol.
**Warning signs:** alert một symbol nhưng throughput toàn hệ giảm mạnh.

## Code Examples

### Điểm chèn 1: Signal ingress drop out-of-order + enqueue worker
```python
# Source: /d/Aureus/services/aureus-signal/engine/live_engine.py
if ts_unix <= last_executed_t:
    await r.xack(stream_key, group_name, entry_id)
    continue
# Phase 45: enqueue vào per_symbol_queue[symbol] thay vì xử lý ngay tại đây.
```

### Điểm chèn 2: Trace + dedupe strict per symbol+candle
```python
# Source: /d/Aureus/services/aureus-signal/engine/orders.py
trace_id = f"{symbol}:{strat_id}:{origin_t}"
history_key = f"aureus:orders:history:{symbol}"
if await self.r.sismember(history_key, trace_id):
    continue
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single consumer loop xử lý trực tiếp từng entry | Router + per-key worker queues (actor style) | [ASSUMED] | Tăng isolation và predictability cho multi-tenant stream processing |

**Deprecated/outdated:**
- “Global sequential loop cho multi-symbol live trading” dễ gây noisy-neighbor và khó rollback theo tenant/symbol. [ASSUMED]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | ACK-after-enqueue là best practice bắt buộc cho Redis Streams pipeline này | Architecture Patterns | Có thể tăng duplicate nếu thiết kế retry khác hiện tại |
| A2 | Actor-style per-key worker là state-of-the-art chung cho workload tương tự | State of the Art | Kế hoạch tối ưu có thể chưa sát workload thực tế của team |

## Open Questions (RESOLVED)

1. **SLO cụ thể cho auto-rollback per-symbol nên đặt bao nhiêu?**
   - What we know: User chốt rollback theo lag/backlog/error-rate liên tiếp (D-12).
   - **Resolution:** Chốt ngưỡng mặc định cho phase 45: `lag_p95_ms > 2000`, `queue_depth > 200`, hoặc `error_rate > 5%` liên tiếp 3 phút thì fallback symbol đó về tuần tự; thoát fallback khi cả 3 chỉ số dưới 50% ngưỡng trong 5 phút liên tiếp.
   - Rationale: Ưu tiên correctness, đủ nhạy để chặn suy thoái kéo dài nhưng có hysteresis để tránh flapping.

2. **Backlog threshold nên đo theo queue length hay processing lag time?**
   - What we know: Cần threshold per-symbol (D-10).
   - **Resolution:** Dùng kết hợp cả hai: `queue_depth` và `lag_p95_ms`; trigger rollback khi bất kỳ chỉ số nào vượt ngưỡng liên tiếp theo cửa sổ 3 phút, đồng thời luôn log cả hai để vận hành phân biệt nguyên nhân nghẽn.
   - Rationale: Một metric đơn lẻ dễ bỏ sót nghẽn lệch pha (queue cao nhưng lag chưa kịp tăng, hoặc lag tăng do downstream dù queue chưa lớn).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | aureus-signal runtime | ✓ | 3.10.11 | — |
| pip3 | dependency install | ✓ | 26.0.1 | — |
| pytest | validation | ✓ | 9.0.2 | `python3 -m pytest` |
| Redis CLI | local Redis diagnostics | ✗ | — | Dùng app logs + service health endpoint |
| PostgreSQL CLI (psql) | local DB diagnostics | ✗ | — | Dùng app-level DB checks / docker exec |
| Docker CLI | compose-based runtime checks | ✗ | — | Chạy qua host shell ngoài sandbox |
| Node.js/npm | gsd tooling | ✓ | Node v22.22.0 / npm 11.12.0 | — |

**Missing dependencies with no fallback:**
- Không có blocker tuyệt đối trong scope code planning; thiếu Redis/Postgres/Docker CLI chỉ ảnh hưởng bước verify thủ công tại môi trường hiện tại.

**Missing dependencies with fallback:**
- Redis/Postgres/Docker CLI có fallback bằng telemetry/log + integration tests ở CI/host.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 |
| Config file | none — dùng discovery mặc định |
| Quick run command | `python3 -m pytest /d/Aureus/services/aureus-signal/tests/test_multi_symbol.py -q` |
| Full suite command | `python3 -m pytest /d/Aureus/services/aureus-signal/tests -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PH45-01 | per-symbol worker song song signal+strategy | integration | `python3 -m pytest /d/Aureus/services/aureus-signal/tests/test_multi_symbol.py -q` | ✅ |
| PH45-02 | FIFO strict theo candle trong symbol | unit/integration | `python3 -m pytest /d/Aureus/services/aureus-signal/tests/test_multi_symbol.py -q` | ✅ (cần mở rộng) |
| PH45-03 | drop out-of-order candle | unit | `python3 -m pytest /d/Aureus/services/aureus-signal/tests/test_live_engine_gates.py -q` | ✅ (cần case mới) |
| PH45-04 | strict snapshot cùng candle | integration | `python3 -m pytest /d/Aureus/services/aureus-signal/tests/test_strategy_trigger_lifecycle.py -q` | ✅ (cần case mới) |
| PH45-05 | trace_id strict symbol+candle dedupe | unit | `python3 -m pytest /d/Aureus/services/aureus-signal/unittest/test_orders_events.py -q` | ✅ |
| PH45-06 | circuit-breaker per-symbol + backlog threshold | unit/integration | `python3 -m pytest /d/Aureus/services/aureus-signal/tests/test_circuit_breaker.py -q` | ✅ (cần adapter per-symbol) |
| PH45-07 | rollout Shadow→Canary→Full + auto rollback theo SLO | integration/manual | `python3 -m pytest /d/Aureus/services/aureus-signal/tests/test_live_engine_shadow_mode.py -q` | ✅ (cần mở rộng) |

### Sampling Rate
- **Per task commit:** `python3 -m pytest /d/Aureus/services/aureus-signal/tests/test_multi_symbol.py -q`
- **Per wave merge:** `python3 -m pytest /d/Aureus/services/aureus-signal/tests -q`
- **Phase gate:** Full suite + canary telemetry check per-symbol pass trước `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `services/aureus-signal/tests/test_per_symbol_worker_runtime.py` — lifecycle worker queue + backlog + breaker
- [ ] `services/aureus-signal/tests/test_out_of_order_drop_policy.py` — verify drop+ack+metric
- [ ] `services/aureus-signal/tests/test_symbol_slo_rollback.py` — SLO breach liên tiếp -> fallback tuần tự symbol đó

## Security Domain

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | N/A (internal service stream) |
| V3 Session Management | no | N/A |
| V4 Access Control | yes | Redis key namespace theo symbol + strict routing theo stream key |
| V5 Input Validation | yes | Parse+type-cast dữ liệu candle, reject malformed payload |
| V6 Cryptography | no | Không thêm crypto mới trong phase này |

### Known Threat Patterns for Python async + Redis Streams stack
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Duplicate/replayed stream entries | Tampering | `trace_id` dedupe + `aureus:orders:history:{symbol}` + trigger key dedupe |
| Out-of-order candle injection | Tampering | Guard `ts_unix <= last_executed_candle_t` then drop+ack |
| Noisy-neighbor symbol starving others | DoS | per-symbol queue + per-symbol circuit-breaker + backlog threshold |

## Sources

### Primary (HIGH confidence)
- `/d/Aureus/.planning/phases/45-h-tr-x-ly-song-song-signal-strategy-cho-nhi-u-symbol-m-t-/45-CONTEXT.md` - locked decisions D-01..D-12
- `/d/Aureus/services/aureus-signal/engine/live_engine.py` - signal loop, lock, stream routing, out-of-order guard, signal payload
- `/d/Aureus/services/aureus-signal/engine/strategy_executor.py` - strategy consumer loop, symbol registry, processing shape
- `/d/Aureus/services/aureus-signal/engine/orders.py` - trace_id, dedupe history key, trigger dedupe key
- `/d/Aureus/services/aureus-signal/engine/manager.py` - per-symbol window/state metadata behavior
- `/d/Aureus/services/aureus-signal/common/circuit_breaker.py` + `tests/test_circuit_breaker.py` - existing breaker primitive
- `/d/Aureus/services/aureus-signal/requirements.txt` - pinned runtime stack versions
- `/d/Aureus/.planning/config.json` - `workflow.nyquist_validation=true`
- `/d/Aureus/CLAUDE.md` - project constraints and GitNexus process requirements

### Secondary (MEDIUM confidence)
- Không dùng nguồn web ngoài trong phiên này.

### Tertiary (LOW confidence)
- Không có claim LOW từ nguồn web đơn lẻ.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - lấy trực tiếp từ requirements và code đang chạy.
- Architecture: HIGH - dựa trên flow runtime hiện có + locked decisions rõ ràng.
- Pitfalls: MEDIUM - một phần là inference vận hành từ kiến trúc hiện trạng.

**Research date:** 2026-04-18
**Valid until:** 2026-05-18

## RESEARCH COMPLETE