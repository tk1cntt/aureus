# Phase 28: AureusProvider.mq5 Bidirectional Extension - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-06
**Phase:** 28-aureusprovider-mq5-bidirectional-extension
**Areas discussed:** Order Command Protocol, OrderSend() Execution, Order Event Responses, ACK/NACK Protocol

---

## Order Command Protocol

| Option | Description | Selected |
|--------|-------------|----------|
| JSON over existing TCP | Reuse TCP socket, newline-delimited JSON | ✓ |
| Separate TCP port for orders | New port for order commands only | |
| Binary protocol | Compact binary format for speed | |

**User's choice:** JSON over existing TCP (agent recommended)
**Notes:** User asked for best suggestion across all 4 areas. Agent recommended reusing existing TCP socket with JSON protocol for consistency with `REQUEST_BACKFILL` pattern already in EA.

---

## OrderSend() Execution

| Option | Description | Selected |
|--------|-------------|----------|
| Fail-fast, no retry | Execute once, push result immediately | ✓ |
| Retry with backoff | Retry OrderSend() 3x with delays | |
| Queue + batch | Queue orders and execute in batch | |

**User's choice:** Fail-fast, no retry at EA level (agent recommended)
**Notes:** Only exception: trade context busy gets 3 retries at 100ms intervals (MT5 serializes trade requests). All other errors → immediate ORDER_FAILED event. Retry logic belongs to server-side (Phase 29).

---

## Order Event Responses

| Option | Description | Selected |
|--------|-------------|----------|
| Same TCP socket | Push events back through existing connection | ✓ |
| Separate event channel | New TCP connection for events only | |
| Redis direct from EA | EA writes directly to Redis (needs library) | |

**User's choice:** Same TCP socket (agent recommended)
**Notes:** 3 event types: ORDER_OPENED, ORDER_CLOSED, ORDER_FAILED. ORDER_CLOSED detected via `OnTradeTransaction()` callback (MT5 native). Magic number filter ensures only bot orders reported.

---

## ACK/NACK Protocol

| Option | Description | Selected |
|--------|-------------|----------|
| 2-phase (ACK + async result) | Immediate ACK/NACK, then async ORDER event | ✓ |
| Sync-only | Wait for OrderSend() result, then respond | |
| Fire-and-forget | No ACK, only ORDER events | |

**User's choice:** 2-phase response pattern (agent recommended)
**Notes:** Phase 1: immediate ACK/NACK (<100ms) confirms command received and validated. Phase 2: async ORDER_OPENED/FAILED event after OrderSend() execution. Server-side timeout handling (Phase 29).

---

## Agent's Discretion

- Queue buffer size for trade context busy retry (recommend 5-10)
- Max slippage default value (20 points, configurable via input param)
- cmd_id dedup array size (500 entries, FIFO cleanup)

## Deferred Ideas

- Partial close support (ORDER-F02) — defer to future requirements
- Order modification (ORDER-F01) — defer to future requirements
- Trailing stop — not in requirements
- Multi-EA instance routing — not in scope for single terminal setup
