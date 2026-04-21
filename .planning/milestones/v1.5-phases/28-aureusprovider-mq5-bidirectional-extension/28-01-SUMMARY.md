---
phase: "28-aureusprovider-mq5-bidirectional-extension"
plan: "01"
subsystem: trading-infrastructure
tags: [mql5, python, pydantic, redis, tcp, order-execution, bidirectional]

# Dependency graph
requires:
  - phase: "26-signal-event-pipeline-strategy-contract"
    provides: "entry_type, size_mode, magic_number contracts used in order commands"
provides:
  - "AureusProvider.mq5 bidirectional order execution (OPEN_ORDER, CLOSE_ORDER)"
  - "Order event push (ORDER_OPENED, ORDER_CLOSED, ORDER_FAILED) via TCP socket"
  - "ACK/NACK protocol with cmd_id dedup for idempotent command processing"
  - "OnTradeTransaction handler for automatic position close detection with P&L reporting"
  - "Gateway order event validation via Pydantic models publishing to aureus:mt5:events"
  - "8 gateway unit tests for order event processing"
affects: ["Phase 29 - aureus-trader (will send order commands via Redis)"]

# Tech tracking
tech-stack:
  added: [pytest-asyncio, pytest]
  patterns: [Pydantic event models for order lifecycle, MQL5 order execution with OrderCheck pre-validation, cmd_id FIFO dedup]

key-files:
  created:
    - "services/aureus-gateway/tests/test_order_events.py"
    - "services/aureus-gateway/tests/__init__.py"
    - "services/aureus-gateway/tests/pytest.ini"
    - "services/aureus-gateway/requirements.txt"
  modified:
    - "mql5/AureusProvider.mq5"
    - "services/aureus-gateway/main.py"

key-decisions:
  - "Combined T1-T3-T5 into single MQL5 file write to ensure consistency and avoid partial compile states"
  - "Used FIFO ring buffer for cmd_id dedup (max 500 entries) to bound memory usage"
  - "OnTradeTransaction filters magic==0 to exclude manual trades from event reporting"
  - "ORDER_CLOSED pushed by OnTradeTransaction rather than ExecuteCloseOrder to capture actual deal completion with P&L"

patterns-established:
  - "Order command schema: OPEN_ORDER/CLOSE_ORDER JSON with cmd_id for idempotency"
  - "Event push pattern: EA sends JSON lines via SendJSON, gateway validates with Pydantic, publishes to Redis"
  - "ACK before execution, NACK for validation failures (DUPLICATE, INVALID_COMMAND, UNKNOWN_SYMBOL, TRADE_DISABLED)"

requirements-completed: [ORDER-04, ORDER-05, ORDER-06]

# Metrics
duration: 8min
completed: 2026-04-06
---

# Phase 28 Plan 01: AureusProvider.mq5 Bidirectional Extension Summary

**Extended AureusProvider.mq5 from unidirectional market data streamer to bidirectional order execution engine with ACK/NACK protocol and automatic position close detection**

## Performance

- **Duration:** 8 min
- **Started:** 2026-04-06T~14:00:00Z
- **Completed:** 2026-04-06T~14:08:00Z
- **Tasks:** 5 (T1-T5 all complete)
- **Files modified:** 2 (AureusProvider.mq5, main.py)
- **Files created:** 4 (test file, __init__.py, pytest.ini, requirements.txt)

## Accomplishments
- AureusProvider.mq5 v3.0: bidirectional TCP communication with order execution capability
- ExecuteOpenOrder supports MARKET (TRADE_ACTION_DEAL), LIMIT and STOP (TRADE_ACTION_PENDING) orders with OrderCheck pre-validation
- ExecuteCloseOrder with magic number ownership verification
- OnTradeTransaction handler detects DEAL_ENTRY_OUT and pushes ORDER_CLOSED events with profit/commission/swap
- Command idempotency via FIFO cmd_id dedup (max 500 entries)
- Gateway validates 5 order event types via Pydantic models, publishes to aureus:mt5:events Redis channel
- 8/8 gateway unit tests passing

## Task Commits

All tasks committed atomically in single commit (combined MQL5 changes for compile consistency):

1. **T1: JSON parser helpers and idempotency** - `4a4fa19` (feat)
2. **T2: Order execution handlers** - `4a4fa19` (feat)
3. **T3: OnTradeTransaction callback** - `4a4fa19` (feat)
4. **T4: Gateway order event processing** - `4a4fa19` (feat)
5. **T5: Chart status display v3.0** - `4a4fa19` (feat)

**Plan metadata:** `4a4fa19` (feat: extend AureusProvider.mq5 with bidirectional order execution)

## Files Created/Modified
- `mql5/AureusProvider.mq5` - Extended from 647 LOC to ~900 LOC with order execution, event push, dedup, OnTradeTransaction, v3.0 display
- `services/aureus-gateway/main.py` - Added 5 Pydantic order event models, order event routing in process_message() to aureus:mt5:events
- `services/aureus-gateway/tests/test_order_events.py` - 8 unit tests for order event validation and Redis publishing
- `services/aureus-gateway/tests/__init__.py` - Package init
- `services/aureus-gateway/tests/pytest.ini` - pytest asyncio_mode = auto
- `services/aureus-gateway/requirements.txt` - Added pytest, pytest-asyncio dependencies

## Decisions Made
- Combined all MQL5 changes (T1+T2+T3+T5) into single file write to ensure syntactic consistency — MQL5 requires MetaEditor to compile, so atomic update prevents partial broken states
- ORDER_CLOSED pushed by OnTradeTransaction rather than ExecuteCloseOrder — this captures the actual deal completion with real P&L, commission, and swap values from history
- FIFO ring buffer for cmd_id dedup instead of unbounded array — prevents memory growth on long-running EAs

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- pytest-asyncio not installed in system Python — installed via `pip install pytest-asyncio`
- pytest.ini needed `asyncio_mode = auto` config for async test discovery — created config file

## Known Stubs
None - no hardcoded empty values or placeholder text in created/modified files.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag:order-execution | mql5/AureusProvider.mq5 | EA now executes real orders via OrderSend() — requires InpAutoTrading=TRUE and terminal trade allowed. NACK reasons include TRADE_DISABLED check. |
| threat_magic:cmd-dedup | mql5/AureusProvider.mq5 | cmd_id dedup uses FIFO buffer of 500 entries — if more than 500 commands arrive rapidly, oldest entries may be evicted allowing potential replay |

## Next Phase Readiness
- Phase 29 (aureus-trader) can now publish OPEN_ORDER/CLOSE_ORDER commands to `aureus:mt5:commands` Redis channel
- Gateway will forward commands to EA via TCP and publish order events to `aureus:mt5:events`
- MQL5 code requires manual compilation in MetaEditor before deployment

## Self-Check: PASSED

- FOUND: mql5/AureusProvider.mq5
- FOUND: services/aureus-gateway/main.py
- FOUND: services/aureus-gateway/tests/test_order_events.py
- FOUND: .planning/phases/28-aureusprovider-mq5-bidirectional-extension/28-01-SUMMARY.md
- FOUND: commit 4a4fa19

---
*Phase: 28-aureusprovider-mq5-bidirectional-extension*
*Completed: 2026-04-06*
