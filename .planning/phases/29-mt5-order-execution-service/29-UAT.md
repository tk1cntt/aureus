---
status: partial
phase: 29-mt5-order-execution-service
source: [29-SUMMARY.md, 29-01-SUMMARY.md]
started: "2026-04-06T20:01:18+07:00"
updated: "2026-04-06T20:10:00+07:00"
---

## Current Test

[testing complete]

## Tests

### 1. Cold Start Smoke Test
expected: Kill any running service. Start aureus-trader-dev via docker compose. Container boots without errors, connects to redis-dev, subscribes to aureus:signals:{symbol} channels for all 8 symbols without crash or timeout.
result: blocked
blocked_by: server
reason: Docker not installed on this machine

### 2. Event Subscription
expected: aureus-trader subscribes to aureus:signals:{symbol} channels for XAUUSD, BTCUSD, ETHUSD, USTEC, USDJPY, EURUSD, GBPUSD, AUDUSD. Logs confirm subscription to all 8 channels.
result: blocked
blocked_by: server
reason: Docker/Redis not available — requires running infrastructure

### 3. Event Filtering
expected: When STRATEGY_MATCH events are published to signal channels, the service processes them. When SIGNAL_EVENT events are published, they are ignored without errors.
result: blocked
blocked_by: server
reason: Docker/Redis not available — requires running infrastructure

### 4. Order Validation
expected: Invalid events are rejected with specific Pydantic validation errors — missing entry_type, invalid direction, RISK_PERCENT size_mode, missing sl/tp, missing magic_number all produce clear rejection messages.
result: blocked
blocked_by: server
reason: Docker/Redis not available — requires running infrastructure

### 5. Order Command Building
expected: Valid STRATEGY_MATCH events are converted to OPEN_ORDER JSON commands with correct cmd_id format (ord-{md5 hash}), proper order type (MARKET/LIMIT/STOP), and all fields mapped from strategy contract.
result: blocked
blocked_by: server
reason: Docker/Redis not available — requires running infrastructure

### 6. Idempotency Dedup
expected: Publishing the same STRATEGY_MATCH event twice within 24 hours results in only one OPEN_ORDER command dispatched. Second event is silently dropped with dedup key aureus:trader:dedup:{cmd_id}.
result: blocked
blocked_by: server
reason: Docker/Redis not available — requires running infrastructure

### 7. Order Queue & Dispatch
expected: Orders are pushed to Redis List aureus:trader:order_queue and published to aureus:mt5:commands for EA consumption. Queue respects max size limit of 100.
result: blocked
blocked_by: server
reason: Docker/Redis not available — requires running infrastructure

### 8. ACK/NACK & Selective Retry
expected: Service listens on aureus:mt5:events for ACK/NACK responses. NACK errors like TRADE_DISABLED or MARKET_CLOSED trigger retry with exponential backoff (1s, 2s, 4s, max 3 retries). Non-retryable errors (DUPLICATE, INVALID_STOPS, INSUFFICIENT_MARGIN) are logged and dropped without retry.
result: blocked
blocked_by: server
reason: Docker/Redis not available — requires running infrastructure

### 9. Unit Tests Pass (42/42)
expected: Run pytest on all 4 test modules. All 42 tests pass with 0 failures — test_validator (17), test_order_builder (8), test_idempotency (5), test_dispatcher (12).
result: pass

## Summary

total: 9
passed: 1
issues: 0
pending: 0
skipped: 0
blocked: 8

## Bug Fix Applied During UAT

### generate_cmd_id — same hash for different inputs
- **File:** `services/aureus-trader/order_builder.py` lines 16-21
- **Root cause:** `signal_ts` only pulled from `data` sub-dict (`data.get("signal_ts")`). Flat event dicts (no `data` key) produced empty key_str `:::`  identical md5 for different events.
- **Fix:** Extended field resolution to check top-level `event` first, then fall back to `data` sub-dict: `event.get("t") or event.get("signal_ts") or data.get("signal_ts") or data.get("t")`. Same for `strategy_id` and `side`.
- **Verification:** 2nd pytest run → 42/42 passed (previously 41 passed, 1 failed)

## Gaps

[none]

## Infrastructure Required for Full Integration Testing

| Test | Requires |
|------|----------|
| 1. Cold Start | Docker, docker-compose.dev.yml |
| 2. Event Subscription | redis-dev container running |
| 3. Event Filtering | redis-dev + Redis pub/sub |
| 4. Order Validation | running aureus-trader service |
| 5. Order Command Building | running aureus-trader service |
| 6. Idempotency | redis-dev with SET EX NX |
| 7. Queue & Dispatch | redis-dev + aureus-gateway |
| 8. ACK/NACK Retry | aureus-gateway + MT5 EA running |
