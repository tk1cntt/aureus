# Phase 29 — MT5 Order Execution Service: SUMMARY

**Phase:** 29
**Plan:** 01
**Status:** ✅ COMPLETED
**Date:** 2026-04-06

---

## What Was Built

Created `aureus-trader` microservice that receives STRATEGY_MATCH events from Redis, validates and builds order commands, queues them persistently, and dispatches to MT5 via `aureus:mt5:commands` channel.

### Service Architecture

```
services/aureus-trader/
├── main.py                    # Entry point — Redis subscriber + event loop
├── config.py                  # TraderConfig dataclass + Redis key constants
├── validator.py               # Pydantic models + STRATEGY_MATCH validation
├── order_builder.py           # Converts validated events to OPEN_ORDER commands
├── idempotency.py             # Redis-based dedup with 24h TTL
├── dispatcher.py              # Queue dispatcher with selective retry logic
├── requirements.txt           # redis, pydantic, python-dotenv
├── Dockerfile                 # Python 3.11-slim image
├── __init__.py
└── tests/
    ├── test_validator.py      # 17 tests — event validation
    ├── test_order_builder.py  # 8 tests — order command generation
    ├── test_idempotency.py    # 5 tests — dedup tracking
    └── test_dispatcher.py     # 12 tests — retry logic + queue dispatch
```

### Test Results

**42/42 tests passed** (100% pass rate)

| Module | Tests | Status |
|--------|-------|--------|
| test_validator.py | 17 | ✅ All passed |
| test_order_builder.py | 8 | ✅ All passed |
| test_idempotency.py | 5 | ✅ All passed |
| test_dispatcher.py | 12 | ✅ All passed |

### Requirements Delivered

| Requirement | Status | Implementation |
|-------------|--------|----------------|
| ORDER-01: Subscribe to Redis | ✅ | main.py subscribes to `aureus:signals:{symbol}` |
| ORDER-02: Market orders | ✅ | order_builder.py builds MARKET commands |
| ORDER-03: Pending orders | ✅ | order_builder.py builds LIMIT/STOP commands |
| ORDER-07: Idempotency key | ✅ | idempotency.py with Redis SETEX dedup |

---

## Key Implementation Details

### Order Pipeline

```
STRATEGY_MATCH event → validator.py → order_builder.py → idempotency.py → dispatcher.py → Redis aureus:mt5:commands
```

1. **Subscribe**: main.py listens to `aureus:signals:{symbol}` for all 8 symbols
2. **Filter**: Only process STRATEGY_MATCH events (ignore SIGNAL_EVENT)
3. **Validate**: validator.py checks entry_type, direction, size_mode, sl/tp, magic_number
4. **Build**: order_builder.py converts to OPEN_ORDER JSON with cmd_id
5. **Dedup**: idempotency.py checks Redis `aureus:trader:dedup:{cmd_id}` (24h TTL)
6. **Queue**: dispatcher.py pushes to Redis List `aureus:trader:order_queue`
7. **Dispatch**: Publish to `aureus:mt5:commands` for EA consumption
8. **Wait for ACK**: Listen on `aureus:mt5:events` for ACK/NACK/ORDER_OPENED/ORDER_FAILED
9. **Retry**: If NACK with retryable error (server error, trade disabled, timeout) → retry up to 3x with exponential backoff

### Validation Rules

| Field | Rule |
|-------|------|
| entry_type | Must be MARKET, LIMIT, or STOP |
| direction | Must be BUY or SELL |
| size_mode | Must be FIXED_UNITS or FIXED_LOT (reject RISK_PERCENT) |
| size_value | Must be > 0 |
| sl | Must be present and > 0 |
| tp | Must be present and > 0 |
| magic_number | Must be present and > 0 |
| LIMIT/STOP | entry_price must be present |

### Retry Logic

| Error | Retryable? | Action |
|-------|------------|--------|
| Server error | ✅ Yes | Retry with backoff |
| Market closed | ✅ Yes | Retry with backoff |
| Trade disabled | ✅ Yes | Retry with backoff |
| Invalid stops | ❌ No | Log and drop |
| Unknown symbol | ❌ No | Log and drop |
| Duplicate order | ❌ No | Log and drop |
| Insufficient margin | ❌ No | Log and drop |

### Idempotency

- Redis key: `aureus:trader:dedup:{cmd_id}`
- TTL: 24 hours (86400 seconds)
- Uses SETEX NX — only sets if key doesn't exist (atomic)
- Returns True if new, False if duplicate

---

## Docker Integration

### Service Definition (docker-compose.dev.yml)
```yaml
aureus-trader-dev:
  build: ./services/aureus-trader
  container_name: aureus-trader-dev
  environment:
    - REDIS_HOST=aureus_redis_dev
    - REDIS_PORT=6379
    - SYMBOLS=XAUUSD,BTCUSD,ETHUSD,USTEC,USDJPY,EURUSD,GBPUSD,AUDUSD
    - LOG_LEVEL=INFO
    - MAX_QUEUE_SIZE=100
    - ACK_TIMEOUT=5.0
    - RESULT_TIMEOUT=30.0
    - MAX_RETRIES=3
    - DEDUP_TTL=86400
  networks:
    - aureus_dev_net
  depends_on:
    - aureus_redis_dev
  restart: unless-stopped
```

---

## Git Commits

| Commit | Message |
|--------|---------|
| 781ab4f | feat(phase-29): create aureus-trader service for MT5 order execution |
| 3aa2a19 | docs(phase-29): complete 29-01-plan summary and state update |

---

## Verification Checklist

- [x] Service subscribes to `aureus:signals:{symbol}` channels
- [x] Filters STRATEGY_MATCH events only
- [x] Validates all order fields with Pydantic
- [x] Builds MARKET, LIMIT, STOP order commands
- [x] Generates deterministic cmd_id
- [x] Dedup prevents duplicate execution
- [x] Order queue persists in Redis List
- [x] Publishes to `aureus:mt5:commands`
- [x] Listens for ACK/NACK on `aureus:mt5:events`
- [x] Selective retry for retryable errors only
- [x] Exponential backoff (2s, 4s, 8s) max 3 retries
- [x] 42/42 unit tests pass

---

*Phase 29 completed: 2026-04-06*
*Tests: 42/42 passed*
*Files: 13 created + docker-compose.dev.yml modified*
