# Phase 29: MT5 Order Execution Service - Context

**Gathered:** 2026-04-06
**Status:** Ready for planning

<domain>
## Phase Boundary

Xây dựng service `aureus-trader` nhận strategy match events từ Redis → validate → convert thành order commands → gửi xuống MT5 qua Gateway (Redis pub/sub `aureus:mt5:commands`) → theo dõi ACK/NACK + ORDER_OPENED/FAILED responses. Scope giới hạn ở order creation & idempotency — trade state machine và history sync thuộc Phase 30/31.

</domain>

<decisions>
## Implementation Decisions

### D-01: Order Queue & Disconnect Resilience — Redis List persistent queue

**Decision:** Sử dụng **Redis List** (`aureus:trader:order_queue`) làm persistent order queue. Khi MT5 disconnect (không có ACK trong 5s), orders được giữ trong queue và auto-resend sau khi reconnect.

**Architecture:**
```
Strategy Match Event (Redis pub/sub)
    ↓
aureus-trader (validate, convert, idempotency check)
    ↓
Redis List: aureus:trader:order_queue (RPUSH)
    ↓
Order Dispatcher (LPOP + process)
    ↓
Redis PUBLISH aureus:mt5:commands
    ↓
Gateway → EA → ACK/NACK → ORDER_OPENED/FAILED
```

**Queue behavior:**
- **RPUSH** khi có order mới → đảm bảo FIFO ordering
- **Dispatcher loop** LPOP từ queue → PUBLISH lên `aureus:mt5:commands` → chờ ACK
- **Nếu ACK received** → order chuyển sang "waiting_result" (in-memory tracking)
- **Nếu không ACK trong 5s** → RPUSH lại queue (back of queue) + log warning
- **Khi MT5 reconnect** → dispatcher tự resume processing queue
- **Queue max size** = 100 orders. Nếu vượt → reject order mới + alert

**Tại sao Redis List thay vì in-memory:**
- Redis List persist qua service restart (aureus-trader crash → queue không mất)
- Consistent với pattern hiện tại (aureus-notifier dùng asyncio.Queue nhưng đó fire-and-forget, order cần durability)
- `aureus:trader:order_queue` key visibility tốt cho monitoring/debug
- Simple RPUSH/LPOP — không cần consumer groups phức tạp

**Tại sao không dùng Redis Stream:**
- Stream + consumer groups overkill cho single-consumer scenario
- Order queue chỉ có 1 consumer (aureus-trader dispatcher)
- List đơn giản hơn, đủ reliable cho use case này

---

### D-02: Idempotency Key Design — Hash-based deterministic key + Redis SET TTL

**Decision:** Server-side idempotency key = **deterministic hash** từ `(strategy_id, symbol, signal_timestamp, direction)`. Storage: **Redis SET** `aureus:trader:processed_orders` với per-key TTL 24h.

**Key format:**
```
cmd_id = f"ord-{md5(f'{strategy_id}:{symbol}:{signal_ts}:{direction}')[:12]}"
```

**Dedup flow:**
1. Strategy match event arrives
2. Generate `cmd_id` từ hash
3. Check Redis: `SISMEMBER aureus:trader:processed_orders {cmd_id}`
4. Nếu exists → skip (duplicate, log info)
5. Nếu not exists → `SADD aureus:trader:processed_orders {cmd_id}` + set per-key expiry
6. Proceed to order queue

**Per-key expiry implementation:**
- Sử dụng Redis key pattern: `aureus:trader:dedup:{cmd_id}` với `SET ... EX 86400`
- Check: `EXISTS aureus:trader:dedup:{cmd_id}`
- Simple, leverages Redis native TTL

**Tại sao hash-based thay vì UUID:**
- Deterministic: cùng strategy match event → cùng cmd_id → tự nhiên idempotent
- UUID random → cần thêm logic check "đã xử lý event này chưa" trước khi generate
- Hash cho phép exactly-once semantics: nếu aureus-trader restart giữa chừng, cùng event replay → cùng cmd_id → dedup tại Redis

**Tại sao 24h TTL:**
- Strategy match signal có ý nghĩa trong ngày trading hiện tại
- Cùng signal ngày hôm sau (nếu có) sẽ có `signal_ts` khác → cmd_id khác
- 24h đủ cover weekend gap (market đóng Friday → mở Monday)

**Complement với Phase 28 EA-side dedup:**
- EA giữ `processed_cmd_ids[]` array (500 entries, FIFO) — defense-in-depth
- Server dedup (Redis TTL) là primary gate, EA dedup là secondary safety net

---

### D-03: Retry & Error Recovery — Selective retry, max 3 attempts, exponential backoff

**Decision:** Retry CHỈ cho retryable errors. Non-retryable errors → reject ngay. Max 3 retries với exponential backoff (2s, 4s, 8s).

**Retryable errors (sẽ retry):**
- `NACK` reason `TRADE_DISABLED` → AutoTrading có thể bật lại
- `ORDER_FAILED` reason `MARKET_CLOSED` → market có thể mở lại
- **Timeout** (không nhận ACK trong 5s) → connection issue
- `ORDER_FAILED` reason chứa "server" hoặc "busy" → transient

**Non-retryable errors (reject ngay, KHÔNG retry):**
- `NACK` reason `DUPLICATE` → EA đã xử lý, không cần retry
- `NACK` reason `INVALID_COMMAND` → bug, cần fix code
- `NACK` reason `UNKNOWN_SYMBOL` → config error
- `ORDER_FAILED` reason `INSUFFICIENT_MARGIN` → account issue, cần user intervention
- `ORDER_FAILED` reason `INVALID_STOPS` → SL/TP calculation error

**Retry mechanism:**
```python
async def dispatch_order(order: Order):
    for attempt in range(MAX_RETRIES + 1):  # 0, 1, 2, 3
        publish_command(order)
        result = await wait_for_response(order.cmd_id, timeout=5s)
        
        if result.type == "ACK":
            # Wait for ORDER_OPENED/FAILED (max 30s)
            final = await wait_for_result(order.cmd_id, timeout=30s)
            if final.type == "ORDER_OPENED":
                return success
            elif is_retryable(final):
                await asyncio.sleep(2 ** attempt)  # 1, 2, 4, 8
                continue
            else:
                return reject(final)
        elif result.type == "NACK" and is_retryable(result):
            await asyncio.sleep(2 ** attempt)
            continue
        else:
            return reject(result)
    
    return reject("MAX_RETRIES_EXCEEDED")
```

**Tại sao 3 retries:**
- Retryable errors thường transient (1-2 lần đủ recover)
- 3 retries + backoff = max ~15s total wait → không quá lâu
- Sau 3 retries mà vẫn fail → issue cần human attention

**Alert on persistent failure:**
- Sau max retries → publish alert lên `aureus:signals:{symbol}` dạng `ORDER_REJECTED` event
- aureus-notifier có thể forward alert này lên Telegram (reuse existing notification pipeline)

---

### D-04: Strategy Match → Order Mapping — Direct field mapping + volume conversion

**Decision:** aureus-trader convert strategy match event thành OPEN_ORDER command bằng **direct field mapping**. Volume conversion cho RISK_PERCENT thực hiện qua MT5 account equity query (deferred, v1 chỉ support FIXED_LOT).

**Strategy match event shape** (from Phase 26, published on `aureus:signals:{symbol}`):
```json
{
  "type": "STRATEGY_MATCH",
  "symbol": "XAUUSD",
  "t": 1712376000000,
  "data": {
    "strategy_id": "CHOCH_UP",
    "direction": "BUY",
    "entry_type": "MARKET",
    "entry_price": 0,
    "size_mode": "FIXED_LOT",
    "size_value": 0.1,
    "sl_mode": "FIXED_PIPS",
    "sl_value": 300,
    "tp_mode": "FIXED_PIPS",
    "tp_value": 500,
    "magic_number": 10001
  }
}
```

**Mapping → OPEN_ORDER command** (Phase 28 D-01 format):
```python
def build_order_command(match_event: dict) -> dict:
    data = match_event["data"]
    return {
        "type": "OPEN_ORDER",
        "symbol": match_event["symbol"],
        "cmd_id": generate_idempotency_key(data),  # D-02
        "direction": data["direction"],        # BUY/SELL
        "order_type": data["entry_type"],      # MARKET/LIMIT/STOP
        "volume": data["size_value"],          # lot size (FIXED_LOT only v1)
        "price": data.get("entry_price", 0),   # 0 for MARKET
        "sl": data["sl_absolute"],             # absolute price (already computed by orders.py)
        "tp": data["tp_absolute"],             # absolute price
        "magic": data["magic_number"],         # static per strategy
        "comment": data["strategy_id"]         # strategy identifier
    }
```

**Validation rules trước khi queue:**
1. `entry_type` phải là `MARKET`, `LIMIT`, hoặc `STOP`
2. `direction` phải là `BUY` hoặc `SELL`
3. `size_value` > 0 và `size_mode` == `FIXED_LOT` (v1)
4. `sl_absolute` và `tp_absolute` đã được compute bởi `orders.py` (not None)
5. `magic_number` > 0
6. Nếu `entry_type` là `LIMIT`/`STOP` → `entry_price` > 0

**RISK_PERCENT conversion — deferred to v1.1:**
- Phase 26 D2: "Execution adapter chịu trách nhiệm convert RISK_PERCENT → lot cụ thể (cần account equity)"
- v1 chỉ hỗ trợ `FIXED_LOT` — strategy explicitly set lot size
- `RISK_PERCENT` requires MT5 account equity query → phức tạp hơn, defer
- Khi nhận `size_mode=RISK_PERCENT` → reject order + log warning "RISK_PERCENT not yet supported"

**SL/TP source clarification:**
- `orders.py` `_calculate_sl_tp()` đã compute absolute SL/TP prices từ `sl_mode`/`sl_value`/`tp_mode`/`tp_value`
- Strategy match event chứa cả raw config VÀ computed absolutes
- aureus-trader chỉ cần `sl_absolute`/`tp_absolute` — không cần re-calculate

### Agent's Discretion
- **Service cấu trúc nội bộ** — file layout, class structure, async patterns (follow aureus-notifier pattern)
- **Logging verbosity levels** — agent decides what to log at INFO vs DEBUG
- **Docker configuration** — port, env vars, healthcheck setup
- **Subscription channel** — subscribe `aureus:signals:*` (all symbols) hoặc per-symbol based on config

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Prior Phase Contracts
- `.planning/phases/26-signal-event-pipeline-strategy-contract/26-CONTEXT.md` — D1 (entry_type enum), D2 (size_mode/size_value, RISK_PERCENT ownership), D3 (magic_number static mapping), D5 (SL/TP contract)
- `.planning/phases/28-aureusprovider-mq5-bidirectional-extension/28-CONTEXT.md` — D-01 (command protocol JSON), D-02 (OrderSend fail-fast), D-03 (order event schemas), D-04 (ACK/NACK 2-phase response)

### Gateway Integration
- `services/aureus-gateway/main.py` — `run_command_subscriber()` forwards Redis `aureus:mt5:commands` → EA TCP; `process_message()` handles ORDER_OPENED/CLOSED/FAILED events → publishes to `aureus:mt5:events`

### Service Pattern Reference
- `services/aureus-notifier/main.py` — Reference implementation for Redis pub/sub subscriber service pattern (async, Docker, config)
- `services/aureus-notifier/config.py` — Config loading pattern from Redis
- `services/aureus-notifier/rate_limiter.py` — Async queue + dispatch loop pattern

### Codebase Maps
- `.planning/codebase/INTEGRATIONS.md` — Redis channel patterns, key conventions
- `.planning/codebase/ARCHITECTURE.md` — Service-oriented architecture overview

### Requirements
- `.planning/REQUIREMENTS.md` — ORDER-01→03, ORDER-07 requirements definition

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **aureus-notifier pattern**: Redis pub/sub subscriber → filter → dispatch loop. aureus-trader can mirror this architecture (subscriber → validator → order queue → dispatcher)
- **RateLimitedDispatcher** (`aureus-notifier/rate_limiter.py`): Async queue + dispatch loop pattern — reusable concept for order dispatcher
- **Gateway order models** (`aureus-gateway/main.py` L74-119): Pydantic models for ORDER_OPENED, ORDER_CLOSED, ORDER_FAILED, ACK, NACK — already validated server-side
- **Gateway command subscriber** (`aureus-gateway/main.py` L352-386): PUBLISH to `aureus:mt5:commands` → forward to EA via TCP

### Established Patterns
- **Service structure**: Single `main.py` entry, separate modules for config/logic/integration
- **Redis connection**: `redis.asyncio` with `decode_responses=True`
- **Docker compose**: Service definition in `docker-compose.dev.yml` with Redis dependency
- **Env configuration**: `REDIS_HOST`, `REDIS_PORT`, `SYMBOLS`, `LOG_LEVEL` standard env vars

### Integration Points
- **Input**: Subscribe to `aureus:signals:{symbol}` channels (same as aureus-notifier) — filter `type=STRATEGY_MATCH`
- **Output**: PUBLISH to `aureus:mt5:commands` channel (consumed by gateway → EA)
- **Feedback**: Subscribe to `aureus:mt5:events` channel for ACK/NACK/ORDER_OPENED/ORDER_FAILED responses
- **Alert**: Publish ORDER_REJECTED events back to `aureus:signals:{symbol}` for notification pipeline

</code_context>

<specifics>
## Specific Ideas

- User muốn cả 4 areas dùng "suggest tốt nhất" — agent đã pick approach tốt nhất dựa trên codebase context và prior phase decisions
- Redis List cho order queue giữ simplicity trong khi đảm bảo durability (tốt hơn in-memory, đơn giản hơn Stream)
- Hash-based deterministic idempotency key cho exactly-once semantics tự nhiên (cùng event → cùng key)
- Selective retry (retryable vs non-retryable) tránh waste resources trên errors không thể recover
- v1 chỉ support FIXED_LOT để ship nhanh — RISK_PERCENT conversion deferred (cần MT5 account equity)

</specifics>

<deferred>
## Deferred Ideas

- **RISK_PERCENT → lot conversion** — cần MT5 account equity query, defer to future phase
- **Order modification** (ORDER-F01) — update SL/TP after entry, thuộc Future Requirements
- **Partial close** (ORDER-F02) — Phase 28 đã setup volume field, defer implementation
- **Multi-symbol concurrent dispatch** — v1 sequential OK, parallel dispatch nếu throughput cần tăng
- **Dead letter queue** — orders fail hết retries → DLQ cho manual review (v1 dùng Telegram alert thay thế)

None — discussion stayed within phase scope

</deferred>

---

*Phase: 29-mt5-order-execution-service*
*Context gathered: 2026-04-06*
