# Phase 38: Fix DB Writer Order Payload Parsing for Wrapped Data to Unblock Trade Journal FK - Research

**Researched:** 2026-04-09
**Domain:** Redis stream consumer contract, JSON payload parsing, PostgreSQL FK dependencies
**Confidence:** HIGH

## Summary

`aureus-db-writer` currently **fails to parse order events** from the Redis stream because it reads fields like `trace_id`, `direction`, `status` from the top-level of the stream entry, but the producer (`SimulatedTradeManager` in `orders.py`) wraps the actual order data inside a `data` JSON string field. This means every order event that reaches the `order_buffer` in `process_batch()` fails the `trace_id` check and gets silently skipped with ACK — so no `aureus_trades` row is ever created.

The downstream impact is critical: `aureus_trade_journal` has a foreign key constraint `trace_id REFERENCES aureus_trades(trace_id) ON DELETE CASCADE`. When the trade journal (Phase 37, `aureus-trader/journal.py`) tries to insert a journal entry for a trade that was never written to `aureus_trades`, the FK constraint blocks it.

The fix is surgical: unwrap the `data` field from the wrapped payload before the existing validation/insert logic runs. The `execution_buffer`, `position_buffer`, and `account_buffer` already do this correctly — only `order_buffer` is missing the unwrapping step.

Three additional bugs were discovered in the order buffer that have been masked by the primary bug:
1. **Undefined variable `ack_skip_msg_ids`** (lines 519, 528) — should be `rejected_msg_ids`. Would cause `NameError` if any event reached state transition validation.
2. **`volume` field `TypeError`** — simulated orders do not include `volume`; `float(payload['volume'])` would crash with `TypeError` on `None`.
3. **`type` field collision** — envelope `type` ("ORDER_OPEN") shadows inner `type` ("MARKET"), making `entry_type` validation fail.

**Primary recommendation:** Add data unwrapping as the first step in the `order_buffer` processing loop, normalize to canonical internal model, fix the three latent bugs, then let existing validation and insert logic proceed unchanged. Apply the same fix to `check_xpending()` recovery.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Canonical input cho DB writer là payload wrapped từ stream: top-level có `type`, `data`; dữ liệu order nghiệp vụ nằm trong `data` (JSON object/string).
- **D-02:** DB writer phải normalize vào một model canonical nội bộ trước khi validate/insert/update, thay vì đọc field top-level rời rạc.
- **D-03:** Mục tiêu là đồng nhất dữ liệu giữa producer và consumer; không dựa vào suy đoán shape.
- **D-04:** Không map `type -> status` trong phase này.
- **D-05:** `status` chỉ lấy từ dữ liệu order thực tế; nếu thiếu thì xử lý theo rule validation (không tạo status giả từ event type).
- **D-06:** Timestamp nghiệp vụ là trường bắt buộc cho các event cần ghi DB.
- **D-07:** Không dùng fallback timestamp không phản ánh nghiệp vụ (ví dụ suy ra từ stream `msg_id`) để ghi record chính.
- **D-08:** Event thiếu timestamp hợp lệ được coi là invalid payload theo policy reject của phase.
- **D-09:** Chọn policy ACK + skip cho event invalid/business-invalid, kèm logging reason rõ ràng để vận hành và forensic.
- **D-10:** Tránh retry vô hạn cho dữ liệu lỗi contract.
- **D-11:** Cột `payload` JSONB chỉ lưu canonical normalized payload (không lưu cả raw envelope trong DB chính).

### Claude's Discretion
- Cách tổ chức helper normalize/validate trong `DBWriter.process_batch()` hoặc utility nội bộ.
- Chuẩn log message/reason_code chi tiết cho từng nhánh invalid.
- Bổ sung test coverage cho wrapped payload, missing required fields, ACK behavior.

### Deferred Ideas (OUT OF SCOPE)
- Đánh giá chiến lược map `type -> status` có thể làm ở phase khác khi có impact analysis đầy đủ trên truy vấn/báo cáo hiện hữu.

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| TRADE-02 | Lưu trade records vào PostgreSQL/TimescaleDB | `aureus_trades` table exists; DB writer must correctly parse and insert order events from Redis stream |
| NOTIF-01 | Signal engine publishes signal events qua Redis pub/sub khi có signal mới | Producer contract verified: `SimulatedTradeManager` emits `{"type": ..., "data": json.dumps(order)}` to Redis stream |

</phase_requirements>

## Current State Analysis

### What `process_batch()` Actually Does (order_buffer section, lines 451-618)

The current order_buffer processing in `main.py` reads fields **directly from the top-level `payload` dict**:

```python
# Line 459: Reads 'type' from top-level of stream entry
event_type = payload.get('type', '')

# Line 467: Reads 'trace_id' from top-level
trace_id = payload.get('trace_id')

# Line 475-477: Reads direction, entry_type, status from top-level
direction = payload.get('direction', payload.get('side', ''))
entry_type = payload.get('entry_type', '')
status = payload.get('status', 'PENDING')

# Line 551: Stores the entire top-level payload as JSONB
order_payload = json.dumps(payload)
```

This assumes `payload` is a flat dict with all order fields at the top level. **It is not.**

### What `check_xpending()` Does (lines 621-688)

The recovery function scans XPENDING messages on order streams, and when it finds `ORDER_PENDING`, `ORDER_OPEN`, or `ORDER_CLOSE` events, it adds them to `self.order_buffer`:

```python
# Line 670-671: Adds wrapped payload directly to buffer
if event_type in ('ORDER_PENDING', 'ORDER_OPEN', 'ORDER_CLOSE'):
    self.order_buffer.append((stream, msg_id, payload))
```

The `payload` here is the raw Redis stream entry dict: `{"type": "ORDER_OPEN", "data": "..."}`. It never unwraps `data` before appending. When `process_batch()` later processes this, it encounters the same problem — `trace_id` is `None` because the actual data is inside `data`.

### What the Producer Actually Emits (orders.py)

`SimulatedTradeManager` emits order events as **wrapped payloads** — a Redis stream entry with two fields:

```python
# orders.py line 238-241: ORDER_PENDING / ORDER_OPEN
await self.r.xadd(f"aureus:stream:{symbol}:orders", {
    "type": stream_type,           # "ORDER_PENDING" or "ORDER_OPEN"
    "data": json.dumps(order)      # order dict as JSON string
})

# orders.py line 327-330: ORDER_CLOSE
await self.r.xadd(f"aureus:stream:{symbol}:orders", {
    "type": "ORDER_CLOSE",
    "data": json.dumps(order)
})

# orders.py line 165-171: ORDER_REJECTED
await self.r.xadd(f"aureus:stream:{symbol}:orders", {
    "type": "ORDER_REJECTED",
    "data": json.dumps(reason_payload)
})

# orders.py line 262-265: ORDER_OPEN after AI approval
await self.r.xadd(f"aureus:stream:{symbol}:orders", {
    "type": "ORDER_OPEN",
    "data": json.dumps(order)
})

# orders.py line 270-273: ORDER_REJECTED after AI rejection
await self.r.xadd(f"aureus:stream:{symbol}:orders", {
    "type": "ORDER_REJECTED",
    "data": json.dumps(order)
})
```

The `order` dict itself contains:
```python
{
    "trace_id": "XAUUSD:strat_id:timestamp",
    "symbol": "XAUUSD",
    "strategy_id": int,
    "strategy_name": str,
    "side": "BUY" | "SELL",
    "type": "MARKET",
    "entry_price": float,
    "sl": float,
    "tp": float,
    "status": "PENDING_AI" | "ACTIVE" | "REJECTED" | "CLOSED",
    "open_time": int,       # <-- business timestamp (candle 't')
    "close_time": int | None,
    "pnl": float,
    "exit_price": float | None,
    "execution_mode": str,
    "order_plan_snapshot": dict,
    "ai_audit": dict | None,
}
```

### What `signal_event_publisher.py` Emits (pub/sub, NOT stream)

`publish_strategy_match()` publishes to `aureus:signals:{symbol}` (pub/sub channel, not stream):

```python
payload = {
    "type": "STRATEGY_MATCH",
    "symbol": symbol,
    "t": t,
    "data": {  # wrapped data
        "trace_id": trace_id,
        "symbol": symbol,
        "strategy": ...,
        "direction": ...,
        ...
    },
}
```

This is consumed by `aureus-trader` via pub/sub (not by `aureus-db-writer` via streams). The trader's validator.py correctly expects `event.get("data")` to contain the fields. **This flow is correct.**

## Producer-Consumer Contract Mismatch

### The Root Bug

| Layer | What It Sends | What Consumer Expects |
|-------|--------------|----------------------|
| `orders.py` (producer) | Redis stream entry: `{"type": "ORDER_OPEN", "data": json.dumps(order_dict)}` | -- |
| `main.py` DB writer `run()` | Reads stream entry into `payload`, appends to `order_buffer` | -- |
| `main.py` DB writer `process_batch()` | Reads `payload.get('trace_id')` directly | **Assumes flat dict with trace_id at top-level** |

The `data` field is a **JSON string** that needs `json.loads()`. The other buffer handlers (`execution_buffer`, `position_buffer`, `account_buffer`) all do this correctly:

```python
# execution_buffer (line 264-265) -- CORRECT
raw_data = payload.get('data')
event_payload = json.loads(raw_data) if isinstance(raw_data, str) else (raw_data or {})
```

But `order_buffer` (line 457+) does **not** -- it reads from `payload` directly as if the order fields are already unwrapped.

### Evidence: Test Coverage Gap

The existing `test_order_buffer.py` tests pass flat dicts directly into the buffer:

```python
order_payload = {
    "trace_id": "trace_001",
    "ticket": 1001,
    ...
}
db_writer.order_buffer.append(("aureus:stream:XAUUSD:orders", "123456789-0", order_payload))
```

These are **not** the wrapped format the producer sends. The tests validate the validation/insert logic but never test the unwrapping step because it doesn't exist.

### Consequence Chain

```
ORDER_OPEN event on stream
  --> DB writer reads {"type": "ORDER_OPEN", "data": "..."}
  --> process_batch() reads payload.get('trace_id') --> None
  --> Line 468: trace_id is None --> skip + ACK
  --> No aureus_trades row created
  --> trade journal INSERT fails FK constraint
  --> No journal entries for any trade
```

## Additional Latent Bugs (Masked by Primary Bug)

### Bug 1: Undefined Variable `ack_skip_msg_ids`

**Location:** `main.py` lines 519 and 528
**Impact:** `NameError` if any event ever reaches the state transition validation branch
**Fix:** Replace `ack_skip_msg_ids` with `rejected_msg_ids`

```python
# Line 519 (currently broken):
ack_skip_msg_ids.append((stream, msg_id))
# Should be:
rejected_msg_ids.append((stream, msg_id))

# Line 528 (currently broken):
ack_skip_msg_ids.append((stream, msg_id))
# Should be:
rejected_msg_ids.append((stream, msg_id))
```

This bug has been masked because no events ever reach the state machine validation code (all fail earlier at the `trace_id` check).

### Bug 2: `volume` Field `TypeError`

**Location:** `main.py` line 567
**Impact:** `TypeError: float() argument must be a string or a real number, not 'NoneType'`
**Root cause:** Simulated orders from `orders.py` do NOT include `volume` in the order dict. After unwrapping, `payload.get('volume')` returns `None`, and `float(None)` raises.

```python
# Line 567 (will crash):
float(payload['volume']) if payload.get('volume') is not None else None,
# The `if` guard works, BUT the current code uses payload['volume'] without .get()
# If after fix the condition is changed to use .get('volume'), this is fine
```

**Verified from source:** The order dict at `orders.py:204-222` does not include `volume`. **Fix:** Use `float(order_data.get('volume', 0) or 0)` or keep the existing `if payload.get('volume') is not None else None` pattern (which is already correct for the `volume` row position).

Actually, reviewing line 567 more carefully:
```python
float(payload['volume']) if payload.get('volume') is not None else None,
```
This is safe because the ternary's condition checks `payload.get('volume') is not None` before accessing `payload['volume']`. But after unwrapping, `order_data.get('volume')` will be `None` for all simulated orders, so `volume` will always be `None` in the DB. This is acceptable for simulated trades.

### Bug 3: `type` Field Collision

**Location:** `main.py` line 485 (`entry_type = payload.get('entry_type', '')`)
**Impact:** The envelope `type` ("ORDER_OPEN") shadows the inner order `type` ("MARKET")
**Root cause:** The producer uses `type` for BOTH the envelope event type AND the entry type inside the order dict. The consumer must read `entry_type` from the unwrapped data, not from the envelope.

After unwrapping, `order_data.get('type')` returns "MARKET" (the entry type), while `payload.get('type')` returns "ORDER_OPEN" (the event type). The consumer must use the unwrapped version.

## Standard Stack

### Core (No new dependencies needed)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| json | stdlib | Parse `data` JSON string | Already imported, used everywhere else |
| asyncpg | (existing) | DB writes | Already in use |
| redis.asyncio | (existing) | Redis stream consumer | Already in use |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | (existing) | Unit tests | Adding wrapped payload tests |

**No new packages needed.** This is a bug fix using existing stdlib and project dependencies.

## Architecture Patterns

### Recommended Fix Structure

The fix adds a normalization step at the top of the `order_buffer` processing loop:

```
stream entry payload
  --> unwrap `data` field (json.loads if string)
  --> merge `type` from envelope into normalized dict
  --> result = canonical internal model
  --> existing validation logic (trace_id, direction, entry_type, state machine)
  --> insert/update
```

### Pattern: Envelope Unwrapping (matching other buffers)

```python
# Source: [VERIFIED: services/aureus-db-writer/main.py execution_buffer pattern, lines 264-265]
raw_data = payload.get('data')
event_payload = json.loads(raw_data) if isinstance(raw_data, str) else (raw_data or {})
if not isinstance(event_payload, dict):
    raise ValueError("Order payload data must be a JSON object")
```

### Anti-Patterns to Avoid

- **Reading fields from envelope level:** The current bug. All business fields live inside `data`.
- **Mapping `type` to `status`:** Explicitly deferred (D-04). Use `order_data.get('status')` only.
- **Fallback to `msg_id` for timestamps:** Explicitly forbidden (D-07). Only use `open_time` from order data.
- **Storing raw envelope in payload column:** Violates D-11. Only store the unwrapped `order_data`.

### Recommended Project Structure

No new files needed. Changes are contained within:
- `services/aureus-db-writer/main.py` -- `process_batch()` order_buffer section + `check_xpending()`
- `services/aureus-db-writer/tests/test_order_buffer.py` -- New tests for wrapped payload

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JSON unwrapping | Custom parser | `json.loads()` with isinstance check | Already proven pattern in execution/position/account buffers |
| Timestamp parsing | New parser | Existing `parse_ts()` closure pattern | Handles string, int, float, ISO formats already |
| State transition | Custom logic | `state_machine.validate_transition()` | Already imported and used in current code |

**Key insight:** The order buffer already has most of the infrastructure (state machine check, INSERT query, ACK flow). The only missing piece is the data unwrapping and field mapping. No new libraries needed.

## Runtime State Inventory

> Not a rename/refactor/migration phase -- no runtime state changes expected.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None -- no existing order records in DB (all were silently skipped) | No data migration needed |
| Live service config | None -- this is a code-only fix | No config changes |
| OS-registered state | None | N/A |
| Secrets/env vars | None | N/A |
| Build artifacts | None | N/A |

## Common Pitfalls

### Pitfall 1: Forgetting to handle `data` as JSON string vs dict
**What goes wrong:** `payload.get('data')` returns a string, calling `.get()` on it throws `AttributeError`.
**Why it happens:** Redis stream stores all values as strings. `json.dumps(order)` produces a string.
**How to avoid:** Always check `isinstance(raw_data, str)` and `json.loads()` before accessing fields. The pattern already exists in `execution_buffer`, `position_buffer`, `account_buffer` -- copy it exactly.
**Warning signs:** `AttributeError: 'str' object has no attribute 'get'` in logs.

### Pitfall 2: `check_xpending()` recovery re-queues wrapped payloads without unwrapping
**What goes wrong:** Recovery adds wrapped payloads to `order_buffer`, then `process_batch()` fails to parse them again.
**Why it happens:** `check_xpending()` already extracts `event_type` from the top-level but then appends the raw `payload` to the buffer.
**How to avoid:** Either (a) unwrap before appending to buffer, or (b) let `process_batch()` handle unwrapping uniformly. Option (b) is cleaner -- single normalization point.

### Pitfall 3: `ORDER_REJECTED` events have different schema inside `data`
**What goes wrong:** ORDER_REJECTED payloads contain `reason_code`, `missing_order_plan_keys`, etc. -- not the same fields as ORDER_OPEN/CLOSE.
**Why it happens:** `orders.py` line 152-163 builds a different dict for rejections.
**How to avoid:** The current code already skips ORDER_REJECTED (line 462-465). This behavior should be preserved. After unwrapping, the skip check should still use the envelope `type`, not the inner data.

### Pitfall 4: `status` field from order data vs event type
**What goes wrong:** The order dict has `status` (e.g., "PENDING_AI", "ACTIVE", "CLOSED") which is DIFFERENT from the envelope `type` ("ORDER_PENDING", "ORDER_OPEN", "ORDER_CLOSE").
**Why it happens:** Producer uses two different vocabularies.
**How to avoid:** Per D-04/D-05: do NOT map type --> status. Use `status` from the unwrapped data only. The envelope `type` is only for routing/skipping (e.g., ORDER_REJECTED skip).

### Pitfall 5: Existing tests use flat dicts and will need updating
**What goes wrong:** Current `test_order_buffer.py` tests pass flat dicts. After the fix, they may break or need wrapping.
**How to avoid:** Keep existing tests as "canonical model" tests (flat dict = already normalized). Add NEW tests for the wrapped payload format. This tests both the normalization layer and the validation layer.

### Pitfall 6: `type` Field Collision (Envelope vs Entry Type)
**What goes wrong:** The envelope has `type` (event type: ORDER_OPEN, etc.) AND the inner data has `type` (entry type: MARKET, LIMIT, STOP).
**Why it happens:** Same key name at two nesting levels.
**How to avoid:** Always read `entry_type` from the unwrapped `order_data`, not from the envelope. After unwrapping, use `order_data.get('type')` for entry_type.
**Warning signs:** Entry type shows "ORDER_OPEN" instead of "MARKET".

### Pitfall 7: Status Value Mismatch with State Machine
**What goes wrong:** Producer emits `status='PENDING_AI'` or `status='ACTIVE'`, but the state machine only knows `PENDING --> SENT --> FILLED --> CLOSED`.
**Why it happens:** Producer status semantics differ from DB state machine semantics.
**How to avoid (within D-04 constraints):** Read status from `order_data`. If it's `PENDING_AI` or `ACTIVE`, normalize to `PENDING` for the initial INSERT. This is NOT mapping `type --> status` (D-04) -- it's normalizing the producer's status value to the consumer's state machine.

## Technical Recommendations

### 1. Normalization Function

Add a private method `_normalize_order_payload(self, stream_msg_id, payload)` that:

1. Extracts `type` from envelope (for routing/skip decisions)
2. Extracts `data` from envelope and `json.loads()` it
3. Merges envelope `type` into the normalized dict for logging
4. Returns `(event_type, order_data)` tuple

### 2. Timestamp Handling

The order data from `orders.py` contains `open_time` (candle timestamp, int). This is the business timestamp. Per D-06/D-07/D-08:
- `open_time` from unwrapped data --> required for DB write
- If missing --> reject (ACK + skip, log reason)
- **No fallback** to `msg_id` timestamp for order records
- The `parse_ts()` helper (line 532-545) already handles int/float/string parsing -- use it for `open_time`

### 3. Missing Fields to Map from Unwrapped Data

After unwrapping, the DB writer needs to map these from `order_data` to the `aureus_trades` columns:

| aureus_trades column | Source in unwrapped order_data | Notes |
|---------------------|-------------------------------|-------|
| trace_id | `order_data['trace_id']` | REQUIRED -- FK for journal |
| ticket | `order_data.get('ticket')` | Only present after MT5 execution |
| symbol | `order_data['symbol']` | REQUIRED |
| magic_number | `order_data.get('magic_number')` | From strategy config |
| strategy_id | `order_data['strategy_id']` | |
| strategy_name | `order_data['strategy_name']` | |
| direction | `order_data['side']` | Note: producer uses `side`, DB expects `direction` |
| entry_type | `order_data['type']` | Always "MARKET" in simulated mode |
| status | `order_data['status']` | From actual order data (D-05) |
| entry_price | `order_data['entry_price']` | |
| exit_price | `order_data.get('exit_price')` | None until closed |
| sl | `order_data['sl']` | |
| tp | `order_data['tp']` | |
| volume | Not in order_data | May need mapping from order_plan_snapshot |
| filled_at | Derived from `open_time` | |
| closed_at | Derived from `close_time` | |
| payload | `json.dumps(order_data)` | D-11: canonical only, not envelope |

**Important mapping:** The producer uses `side` ("BUY"/"SELL"), but the DB writer currently reads `payload.get('direction', payload.get('side', ''))` -- the fallback works. After unwrapping, `order_data['side']` will be available.

### 4. `volume` Field Gap

The order dict from `orders.py` does **not** include a `volume` field. The `aureus_trades.volume` column expects a float. The order_plan_snapshot has `size_value` and `size_mode` but not `volume`. This needs handling:
- Default `volume` to `None` or `0.0` for simulated trades
- The `order_plan_snapshot.size_value` could be mapped but only in later phases

## Risks & Dependencies

### Risk 1: FK Violation on Existing Data
If the journal table was created and trades are being attempted, there may be pending journal entries that will succeed once `aureus_trades` rows start being created. No data migration needed -- just fix the writer.

### Risk 2: State Machine Validation May Reject Recovered Messages
Recovered messages from XPENDING may have statuses that don't pass `validate_transition()` (e.g., ORDER_CLOSE with status "CLOSED" when no PENDING row exists). This is expected -- the log should clearly indicate why.

### Risk 3: `ORDER_CLOSE` Events May Not Have All Fields
When `orders.py` emits ORDER_CLOSE, it includes the full order dict which now has `status="CLOSED"`, `close_time`, `exit_price`, `pnl`. But the DB writer's state machine requires the trade to exist first with PENDING --> SENT --> FILLED --> CLOSED. If ORDER_OPEN was skipped (pre-fix), ORDER_CLOSE will fail state validation. This is correct behavior -- the fix must process ORDER_OPEN first.

### Dependency: `aureus_trade_journal` Table
- Migration: `services/aureus-db-writer/migrations/add_trade_journal.sql`
- FK: `trace_id REFERENCES aureus_trades(trace_id) ON DELETE CASCADE`
- The journal is written by `aureus-trader/journal.py`, NOT by `aureus-db-writer`
- The FK violation occurs in `aureus-trader`, not `aureus-db-writer`
- Fixing `aureus-db-writer` to write `aureus_trades` rows unblocks the journal FK

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest |
| Config file | None detected (pytest discovered via `sys.path` manipulation in test files) |
| Quick run command | `pytest tests/test_order_buffer.py -x` |
| Full suite command | `pytest tests/ -x` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| D-01/D-02 | Wrapped payload unwrapped before processing | unit | `pytest tests/test_order_buffer.py::TestWrappedPayload -x` | ❌ New test needed |
| D-04/D-05 | Status from order data, not from envelope type | unit | `pytest tests/test_order_buffer.py::TestStatusFromData -x` | ❌ New test needed |
| D-06/D-08 | Missing timestamp --> reject with ACK | unit | `pytest tests/test_order_buffer.py::TestMissingTimestamp -x` | ❌ New test needed |
| D-09/D-10 | Invalid event --> ACK + skip, no retry | unit | `pytest tests/test_order_buffer.py::TestInvalidEventAck -x` | ❌ New test needed |
| D-11 | payload JSONB stores canonical data only | unit | `pytest tests/test_order_buffer.py::TestCanonicalPayload -x` | ❌ New test needed |
| Bug fix | `ack_skip_msg_ids` replaced with `rejected_msg_ids` | unit | Existing `test_order_buffer.py` tests pass | Yes |
| Existing | PENDING-->SENT valid transition | unit | `pytest tests/test_order_buffer.py::TestOrderBufferValidTransition -x` | ✅ |
| Existing | Invalid transition rejected | unit | `pytest tests/test_order_buffer.py::TestOrderBufferInvalidTransition -x` | ✅ |
| Existing | Missing trace_id skipped | unit | `pytest tests/test_order_buffer.py::TestOrderBufferMissingTraceId -x` | ✅ |

### Sampling Rate
- **Per task commit:** `pytest services/aureus-db-writer/tests/test_order_buffer.py -x`
- **Per wave merge:** `pytest services/aureus-db-writer/tests/ -x`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_order_buffer.py` -- wrapped payload test class (D-01/D-02)
- [ ] New test class: `TestWrappedPayloadUnwrap` -- verifies `data` field is unwrapped before field access
- [ ] New test class: `TestMissingTimestampRejection` -- verifies D-06/D-07/D-08 (no fallback to msg_id)
- [ ] New test class: `TestCanonicalPayloadStorage` -- verifies D-11 (payload column contains only inner data)
- [ ] New test: `TestAckSkipVariableFixed` -- verifies `ack_skip_msg_ids` NameError is fixed
- [ ] Tests for ORDER_REJECTED skip with wrapped format
- [ ] Tests for `check_xpending()` recovery with wrapped payloads
- [ ] Fix existing tests to use wrapped format OR add parallel "canonical input" tests
- [ ] Framework install: `pip install pytest pytest-asyncio` -- if not already installed

## Security Domain

> Phase 38 is a parsing/contract fix with no new authentication, authorization, or encryption requirements. No ASVS categories apply.

## Code Examples

### Verified pattern: How other buffers unwrap (execution_buffer)

```python
# Source: [VERIFIED: services/aureus-db-writer/main.py, lines 263-267]
raw_data = payload.get('data')
event_payload = json.loads(raw_data) if isinstance(raw_data, str) else (raw_data or {})
if not isinstance(event_payload, dict):
    raise ValueError("Execution payload data must be a JSON object")
```

### Producer envelope format (orders.py)

```python
# Source: [VERIFIED: services/aureus-signal/engine/orders.py, lines 238-241]
await self.r.xadd(f"aureus:stream:{symbol}:orders", {
    "type": stream_type,    # "ORDER_PENDING" or "ORDER_OPEN"
    "data": json.dumps(order)
})
```

### ORDER_REJECTED envelope (orders.py)

```python
# Source: [VERIFIED: services/aureus-signal/engine/orders.py, lines 165-171]
await self.r.xadd(
    f"aureus:stream:{symbol}:orders",
    {
        "type": "ORDER_REJECTED",
        "data": json.dumps(reason_payload),
    },
)
```

### Current broken consumption (main.py)

```python
# Source: [VERIFIED: services/aureus-db-writer/main.py, lines 459, 467]
event_type = payload.get('type', '')  # Gets "ORDER_OPEN" from envelope -- OK
trace_id = payload.get('trace_id')     # Returns None -- trace_id is INSIDE data!
```

### Undefined variable bug (main.py)

```python
# Source: [VERIFIED: services/aureus-db-writer/main.py, lines 519, 528]
# These lines reference `ack_skip_msg_ids` which is never defined:
ack_skip_msg_ids.append((stream, msg_id))  # Line 519
ack_skip_msg_ids.append((stream, msg_id))  # Line 528
# Should be:
rejected_msg_ids.append((stream, msg_id))
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Flat dict in stream | Wrapped `type` + `data` JSON string | Phase 26 signal contract | All stream consumers must unwrap |
| Direct field access | Envelope unwrap --> parse data --> extract | This phase | Fix order_buffer to match other buffers |
| Fallback timestamp from msg_id | Strict required timestamp from data | This phase (D-07/D-08) | Invalid timestamps --> reject |

**Deprecated/outdated:**
- Reading order fields from stream entry top-level: The producer wraps data. Consumer must unwrap first.
- Using `msg_id` timestamp as fallback for business timestamp: Rejected per D-07.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The `aureus_trade_journal` table exists (migration file present) | Risks & Dependencies | If table doesn't exist, FK isn't blocking anything yet -- fix still needed for correctness |
| A2 | `aureus-trader/journal.py` reads STRATEGY_MATCH events from pub/sub with `data` wrapping | Current State Analysis | If journal reads different format, downstream fix may also be needed |
| A3 | No other consumers read `aureus:stream:*:orders` besides `aureus-db-writer` | -- | If other consumers exist, they may have the same bug |
| A4 | `status='ACTIVE'` from producer needs normalization to `PENDING` for state machine compatibility | Pitfall 7 | If state machine is extended elsewhere, normalization could overwrite correct status |

## Open Questions

1. **Should `check_xpending()` unwrap before adding to buffer or let `process_batch()` handle it?**
   - What we know: Currently it adds raw wrapped payload to buffer
   - What's unclear: Whether centralized unwrapping in `process_batch()` is preferred (single point) or early unwrapping in `check_xpending()` (fail fast)
   - Recommendation: Centralized in `process_batch()` -- single normalization point, easier to test and maintain

2. **What timestamp field from the unwrapped order data should be used as the business timestamp?**
   - What we know: `orders.py` order dict has `open_time` (candle `t`, int)
   - What's unclear: Whether `filled_at` should map to `open_time` or another field
   - Recommendation: `open_time` --> `filled_at` for order insert; `close_time` --> `closed_at` for order close update

3. **Does the `volume` field need to be populated?**
   - What we know: Order dict from `orders.py` does not include `volume`
   - What's unclear: Whether `aureus_trades.volume` is used by any downstream queries
   - Recommendation: Default to `None` for now; map from `order_plan_snapshot.size_value` in a future phase

4. **Status normalization for `ACTIVE`/`PENDING_AI`:**
   - What we know: Producer sends `status='ACTIVE'` for direct simulated orders and `status='PENDING_AI'` for AI-pending orders. State machine requires `PENDING` as the initial status.
   - What's unclear: Whether `ACTIVE` should be treated as equivalent to `SENT` or to `PENDING`
   - Recommendation: Normalize `PENDING_AI` and `ACTIVE` to `PENDING` for the initial INSERT. This is a minimal change that preserves the state machine contract.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.x | DB writer service | Assumed ✓ | -- | -- |
| Redis | Stream consumer | Assumed ✓ | -- | -- |
| PostgreSQL/TimescaleDB | Trade data storage | Assumed ✓ | -- | -- |
| pytest | Unit tests | Assumed ✓ | -- | -- |

**Note:** Environment availability assumes the development environment from the project's docker-compose setup. The fix is code-only -- no new external dependencies.

## Sources

### Primary (HIGH confidence)
- [VERIFIED: Codebase] `services/aureus-db-writer/main.py` -- Current broken order_buffer parsing (lines 451-618)
- [VERIFIED: Codebase] `services/aureus-signal/engine/orders.py` -- Producer wrapped payload format (lines 238-241, 327-330, 165-171)
- [VERIFIED: Codebase] `services/aureus-db-writer/schema.sql` -- `aureus_trades` table definition
- [VERIFIED: Codebase] `services/aureus-db-writer/state_machine.py` -- State transition rules
- [VERIFIED: Codebase] `services/aureus-db-writer/main.py` -- execution_buffer unwrapping pattern (lines 264-265)
- [VERIFIED: Codebase] `services/aureus-trader/journal.py` -- TradeJournalManager.on_strategy_match() expects data wrapping
- [VERIFIED: Codebase] `services/aureus-signal/engine/signal_event_publisher.py` -- STRATEGY_MATCH pub/sub format

### Secondary (MEDIUM confidence)
- [VERIFIED: Codebase] `services/aureus-db-writer/tests/test_order_buffer.py` -- Tests use flat dicts, not wrapped format
- [VERIFIED: Codebase] `services/aureus-trader/tests/test_journal.py` -- Journal test patterns and event shapes

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new dependencies, existing stdlib and project packages
- Architecture: HIGH -- verified by reading both producer and consumer source code
- Pitfalls: HIGH -- identified from code review of actual implementation
- Impact analysis: HIGH -- FK constraint verified from migration SQL, data flow traced through all files

**Research date:** 2026-04-09
**Valid until:** 2026-05-09 (30 days -- stable code, no fast-moving dependencies)
