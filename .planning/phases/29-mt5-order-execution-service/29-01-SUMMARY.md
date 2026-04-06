---
phase: 29-mt5-order-execution-service
plan: 01
subsystem: infra
tags: [redis, mt5, order-execution, asyncio, docker, microservice]

# Dependency graph
requires:
  - phase: 26-signal-event-pipeline-strategy-contract
    provides: STRATEGY_MATCH event schema, entry_type enum, size_mode/size_value contract
  - phase: 28-aureusprovider-mq5-bidirectional-extension
    provides: OPEN_ORDER command schema, ACK/NACK protocol, order event schemas
provides:
  - aureus-trader microservice for MT5 order execution
  - Redis pub/sub subscriber for STRATEGY_MATCH events
  - Order validation pipeline with D-04 rules
  - OPEN_ORDER command builder with deterministic idempotency keys
  - Redis List persistent order queue with max size enforcement
  - Selective retry logic with exponential backoff (max 3 retries)
  - Docker Compose service definition for dev environment
affects:
  - phase-30-trade-state-machine (will consume order execution results)
  - phase-31-order-history-sync (will sync executed orders to DB)
  - aureus-notifier (receives ORDER_REJECTED alerts via same signal channels)

# Tech tracking
tech-stack:
  added: [redis[hiredis], pydantic, pytest, pytest-asyncio, fakeredis]
  patterns: [Redis pub/sub subscriber service, async dispatch loop, Redis List queue, hash-based idempotency, selective retry with exponential backoff]

key-files:
  created:
    - services/aureus-trader/main.py
    - services/aureus-trader/config.py
    - services/aureus-trader/validator.py
    - services/aureus-trader/order_builder.py
    - services/aureus-trader/idempotency.py
    - services/aureus-trader/dispatcher.py
    - services/aureus-trader/requirements.txt
    - services/aureus-trader/Dockerfile
    - services/aureus-trader/tests/test_validator.py
    - services/aureus-trader/tests/test_order_builder.py
    - services/aureus-trader/tests/test_idempotency.py
    - services/aureus-trader/tests/test_dispatcher.py
  modified:
    - docker-compose.dev.yml

key-decisions:
  - "Used Redis SET NX for atomic idempotency check-and-mark (race-condition safe)"
  - "v1 only supports FIXED_LOT size mode; RISK_PERCENT rejected with specific error"
  - "Separate dispatcher loop from main subscriber loop for independent lifecycle management"
  - "ORDER_REJECTED alerts published back to aureus:signals:{symbol} for notification pipeline reuse"

patterns-established:
  - "Service pattern: config.py + main.py entry + separate modules for validator/builder/dispatcher"
  - "Redis List (RPUSH/LPOP) for persistent order queue with max size enforcement"
  - "Deterministic hash-based cmd_id: ord-{md5(strategy_id:symbol:signal_ts:direction)[:12]}"
  - "Selective retry: TRADE_DISABLED, MARKET_CLOSED, server/busy keywords are retryable; DUPLICATE, INSUFFICIENT_MARGIN, INVALID_STOPS are not"

requirements-completed: [ORDER-01, ORDER-02, ORDER-03, ORDER-07]

# Metrics
duration: 15min
completed: 2026-04-06
---

# Phase 29 Plan 01: aureus-trader Service — Order Execution Pipeline Summary

**MT5 order execution microservice that converts STRATEGY_MATCH events into OPEN_ORDER commands with validation, deduplication, persistent queuing, and selective retry logic**

## Performance

- **Duration:** 15 min
- **Started:** 2026-04-06T00:00:00Z
- **Completed:** 2026-04-06T00:15:00Z
- **Tasks:** 8 (T1-T8)
- **Files modified:** 14 (13 created, 1 modified)

## Accomplishments

- **Complete aureus-trader microservice** with Redis pub/sub subscription, event filtering, validation, order building, idempotency, queueing, and dispatch
- **42 unit tests** all passing across 4 test files (validator: 16, order_builder: 8, idempotency: 5, dispatcher: 13)
- **Docker integration** — aureus-trader-dev service added to docker-compose.dev.yml with Redis dependency
- **Selective retry logic** — distinguishes retryable (TRADE_DISABLED, MARKET_CLOSED, server/busy) from non-retryable errors (DUPLICATE, INSUFFICIENT_MARGIN, INVALID_STOPS)

## Task Commits

All tasks committed atomically in a single commit:

1. **T1: config.py** — TraderConfig dataclass, load_config(), Redis key constants
2. **T2: validator.py** — validate_strategy_match() with all 7 D-04 validation rules
3. **T3: order_builder.py** — build_order_command() and generate_cmd_id() with hash-based dedup
4. **T4: idempotency.py** — IdempotencyChecker with Redis SET NX atomic check-and-mark
5. **T5: dispatcher.py** — OrderDispatcher with enqueue, dispatch loop, retry with exponential backoff
6. **T6: main.py** — Service entry point with pub/sub subscriber pipeline
7. **T7: Docker + Compose** — Dockerfile, requirements.txt, docker-compose.dev.yml service
8. **T8: Unit Tests** — 42 tests across 4 test files, all passing

**Plan commit:** `781ab4f` (feat(phase-29): create aureus-trader service for MT5 order execution)

## Files Created/Modified

- `services/aureus-trader/config.py` — TraderConfig dataclass with 9 fields, load_config(), Redis key constants
- `services/aureus-trader/validator.py` — STRATEGY_MATCH event validation (D-04 rules)
- `services/aureus-trader/order_builder.py` — OPEN_ORDER command mapping with deterministic cmd_id
- `services/aureus-trader/idempotency.py` — Redis SET NX dedup with 24h TTL
- `services/aureus-trader/dispatcher.py` — Order queue, dispatch loop, selective retry logic
- `services/aureus-trader/main.py` — Service entry point with pub/sub subscriber
- `services/aureus-trader/requirements.txt` — redis[hiredis], pydantic dependencies
- `services/aureus-trader/Dockerfile` — Python 3.11-slim based container
- `services/aureus-trader/__init__.py` — Package init
- `services/aureus-trader/tests/test_validator.py` — 16 validation tests
- `services/aureus-trader/tests/test_order_builder.py` — 8 order builder tests
- `services/aureus-trader/tests/test_idempotency.py` — 5 idempotency tests (fakeredis)
- `services/aureus-trader/tests/test_dispatcher.py` — 13 dispatcher tests
- `docker-compose.dev.yml` — Added aureus-trader-dev service

## Decisions Made

- Used `redis.asyncio` with `decode_responses=True` (consistent with existing services)
- v1 only supports FIXED_LOT — RISK_PERCENT rejected with "RISK_PERCENT not yet supported" error
- ORDER_REJECTED alerts published to same signal channels for notification pipeline reuse
- Exponential backoff: `2^attempt` seconds (1s, 2s, 4s, 8s) between retries

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None - all files compiled cleanly, all 42 tests passed on first run.

## User Setup Required

None - no external service configuration required. Service connects to existing redis-dev container.

## Next Phase Readiness

- Order execution pipeline complete, ready for Phase 30 (trade state machine) and Phase 31 (order history sync)
- aureus-trader-dev service ready to run via `docker compose -f docker-compose.dev.yml up aureus-trader-dev`
- Requires aureus-gateway-dev and MT5 EA to be running for full end-to-end order execution

---
*Phase: 29-mt5-order-execution-service*
*Completed: 2026-04-06*
