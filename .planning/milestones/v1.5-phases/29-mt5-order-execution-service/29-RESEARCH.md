# Phase 29: MT5 Order Execution Service — Research

## 1. Service Architecture

### Pattern: Mirror aureus-notifier
aureus-trader mirrors aureus-notifier architecture (single `main.py` entry + modules):

```
services/aureus-trader/
├── main.py              # Entry point — Redis subscriber + dispatcher orchestration
├── config.py            # Configuration from env vars + Redis
├── validator.py         # Order validation logic (size_mode, entry_type, direction)
├── order_builder.py     # STRATEGY_MATCH event → OPEN_ORDER command conversion
├── idempotency.py       # Hash-based dedup with Redis TTL (D-02)
├── dispatcher.py        # Redis List queue + dispatch loop with ACK tracking (D-01, D-03)
├── requirements.txt     # redis[hiredis], pydantic
├── Dockerfile           # python:3.11-slim, identical to aureus-notifier
└── tests/
    ├── test_validator.py
    ├── test_order_builder.py
    ├── test_idempotency.py
    └── test_dispatcher.py
```

### Async Pattern
- `redis.asyncio` with `decode_responses=True` (consistent with gateway+notifier)
- `asyncio.create_task()` for parallel loops: subscriber loop, dispatcher loop, event listener loop
- Graceful shutdown on SIGTERM/SIGINT

### Docker Integration
- Service `aureus-trader-dev` in `docker-compose.dev.yml`
- Depends on `redis-dev` (same as aureus-notifier)
- Env vars: `REDIS_HOST`, `REDIS_PORT`, `SYMBOLS`, `LOG_LEVEL`
- No exposed ports needed (internal Redis only)

## 2. Data Flow

```
aureus:signals:{symbol}  (pub/sub, subscribe)
        ↓
   [Subscriber Loop] — filter type=STRATEGY_MATCH
        ↓
   [Validator] — check entry_type, direction, size_mode, SL/TP absolutes, magic
        ↓
   [Idempotency Check] — Redis key aureus:trader:dedup:{cmd_id} EXISTS?
        ↓ (new only)
   [Order Builder] — convert to OPEN_ORDER command (Phase 28 D-01 format)
        ↓
   [Redis List Queue] — RPUSH aureus:trader:order_queue
        ↓
   [Dispatcher Loop] — LPOP → PUBLISH aureus:mt5:commands
        ↓
   [Event Listener] — subscribe aureus:mt5:events, match ACK/NACK/ORDER_OPENED/FAILED by cmd_id
        ↓
   [Retry/Alert] — selective retry (D-03), ORDER_REJECTED alert on failure
```

## 3. Key Integration Points

### Input Channel
- Subscribe `aureus:signals:{symbol}` for each configured symbol
- Filter `type == "STRATEGY_MATCH"` events only
- Already used by aureus-notifier — same channel, different consumer

### Output Channel
- PUBLISH to `aureus:mt5:commands` — consumed by gateway `run_command_subscriber()`
- Gateway forwards to EA via TCP socket

### Feedback Channel
- Subscribe `aureus:mt5:events` — receives ACK, NACK, ORDER_OPENED, ORDER_FAILED from gateway
- Match events by `cmd_id` field to track order lifecycle

### Alert Channel
- PUBLISH `ORDER_REJECTED` event back to `aureus:signals:{symbol}` for aureus-notifier to forward to Telegram

## 4. Validation Architecture

### Input Validation (before queue)
| Field | Validation | Action on Fail |
|-------|-----------|----------------|
| `entry_type` | Must be MARKET, LIMIT, or STOP | Reject + log |
| `direction` | Must be BUY or SELL | Reject + log |
| `size_mode` | Must be FIXED_LOT (v1) | Reject + log warning |
| `size_value` | > 0 | Reject + log |
| `sl_absolute` | Not None | Reject + log |
| `tp_absolute` | Not None | Reject + log |
| `magic_number` | > 0 | Reject + log |
| `entry_price` | > 0 if LIMIT/STOP | Reject + log |

### Output Validation
- OPEN_ORDER command matches Phase 28 D-01 schema exactly
- All required fields present: type, symbol, cmd_id, direction, order_type, volume, price, sl, tp, magic, comment

## 5. Existing Code Patterns

### From aureus-notifier
- **Subscriber pattern**: `pubsub.subscribe()` → `async for message in pubsub.listen()` → parse JSON → process
- **Config pattern**: env vars for REDIS_HOST, REDIS_PORT, SYMBOLS, LOG_LEVEL
- **Dockerfile**: `python:3.11-slim` → pip install → CMD python main.py
- **Docker compose**: service entry with redis-dev dependency, environment vars, restart policy

### From aureus-gateway
- **Pydantic models**: `OrderOpenedEvent`, `OrderClosedEvent`, `OrderFailedEvent`, `AckEvent`, `NackEvent`
- **Event channel**: `aureus:mt5:events` — all order events published here
- **Command channel**: `aureus:mt5:commands` — commands forwarded to EA

## 6. Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| Duplicate orders | HIGH | Hash-based idempotency key (D-02) + Redis TTL + EA-side dedup |
| MT5 disconnect | MEDIUM | Redis List queue persists orders; auto-resume on reconnect |
| Order timeout | MEDIUM | 5s ACK timeout + 30s result timeout + selective retry (D-03) |
| Queue overflow | LOW | Max 100 orders in queue; reject new orders + alert |
| RISK_PERCENT sizing | LOW | v1 only supports FIXED_LOT; explicit reject with warning |

## RESEARCH COMPLETE

Research covers service architecture, data flow, integration points, validation, and existing code patterns. Ready for planning.
