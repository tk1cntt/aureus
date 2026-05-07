---
quick_id: 260507-vmj
status: completed
completed_at: 2026-05-07
mode: quick-validate
report_only: true
---

# Quick Task 260507-vmj Summary

## Task

Phân tích chi tiết lỗi monitor log trader:

```text
RECONCILE_NEEDED for order ord-4fd96f27887e (BTCUSD) class=ACK_LOST_DUPLICATE_RECOVERY
```

Không sửa code.

## Affected Order

| Field | Value |
|---|---|
| `cmd_id` | `ord-4fd96f27887e` |
| Symbol | `BTCUSD` |
| Direction | `SELL` |
| Strategy/comment | `CHOCH_CISD_BEAR` |
| Lane | `BTCUSD:608000:SELL` |
| Error class | `ACK_LOST_DUPLICATE_RECOVERY` |

## Timeline From Trader Logs

Observed from `docker logs --since 30m aureus-trader-dev`.

```text
15:21:01.264 Order queued: ord-4fd96f27887e BTCUSD SELL CHOCH_CISD_BEAR
15:21:01.346 Published order ord-4fd96f27887e lane=BTCUSD:608000:SELL attempt=1/4 enqueue_age_ms=82.74
15:21:06.348 ACK timeout for ord-4fd96f27887e, attempt 1 lane=BTCUSD:608000:SELL pending=['ord-1fb019a3d319'] published_age_ms=5003.27
15:21:07.353 Published order ord-4fd96f27887e lane=BTCUSD:608000:SELL attempt=2/4 enqueue_age_ms=6090.04
15:21:12.354 ACK timeout for ord-4fd96f27887e, attempt 2 lane=BTCUSD:608000:SELL pending=['ord-1fb019a3d319'] published_age_ms=5001.65
15:21:12.963 Unmatched event type=ACK cmd_id=ord-4fd96f27887e symbol=GLOBAL pending_keys=[] matched=6 unmatched=1
15:21:14.118 Unmatched event type=ORDER_OPENED cmd_id=ord-4fd96f27887e symbol=BTCUSD pending_keys=[] matched=6 unmatched=2
15:21:14.120 Unmatched event type=NACK cmd_id=ord-4fd96f27887e symbol=GLOBAL pending_keys=[] matched=6 unmatched=3
15:21:14.355 Published order ord-4fd96f27887e lane=BTCUSD:608000:SELL attempt=3/4 enqueue_age_ms=13092.15
15:21:14.462 Matched event type=NACK cmd_id=ord-4fd96f27887e symbol=GLOBAL pending_before=1 matched=7 unmatched=3
15:21:14.462 RECONCILE_NEEDED for order ord-4fd96f27887e (BTCUSD) class=ACK_LOST_DUPLICATE_RECOVERY
```

## Dispatcher Code Path

Relevant file: `services/aureus-trader/dispatcher.py`.

### ACK wait

`dispatch_order()` publishes command then waits for ACK/NACK:

```python
ack_result = await self._wait_for_response(cmd_id, self.config.ack_timeout)
```

`_wait_for_response()` stores one future per `cmd_id`:

```python
self._pending_responses[cmd_id] = future
```

On timeout, it removes the pending future:

```python
self._pending_responses.pop(cmd_id, None)
return None
```

### Retry after ACK timeout

When no ACK arrives within 5s:

```python
state["state"] = "ACK_TIMEOUT_NO_PROVIDER_RESPONSE"
state["retry_after_ack_timeout"] = True
await asyncio.sleep(2**attempt)
continue
```

### Duplicate recovery branch

If later retry receives `NACK DUPLICATE` after previous ACK timeout:

```python
if ack_result.get("reason") == "DUPLICATE" and state.get("retry_after_ack_timeout"):
    state["state"] = "ACK_LOST_DUPLICATE_RECOVERY"
    state.pop("retry_after_ack_timeout", None)
    await self._handle_reconcile_needed(order, "ACK_LOST_DUPLICATE_RECOVERY")
```

This exactly matches final observed state.

## Provider Code Path

Relevant file: `mql5/AureusProvider_v2.mq5`.

`ExecuteOpenOrder()` checks duplicate before ACK:

```mql5
if(IsDuplicateCmd(cmdId))
  {
   SendNACK(cmdId, "DUPLICATE");
   return;
  }
```

Provider sends ACK, then records cmd id:

```mql5
SendACK(cmdId);
RecordCmdId(cmdId);
```

Meaning: if first command reached provider and got recorded, later retry with same `cmd_id` will return `NACK DUPLICATE`.

## Root Cause

Primary root cause: response-lifecycle race around ACK timeout.

Sequence:

1. Trader publishes `ord-4fd96f27887e` attempt 1.
2. Provider likely receives attempt 1 and later sends ACK/ORDER_OPENED.
3. Trader does not match ACK within `ack_timeout=5s` because pending future times out and is removed.
4. Trader retries same `cmd_id` attempt 2.
5. Late ACK and ORDER_OPENED arrive after future removal, so dispatcher logs them as `Unmatched event` and does not journal them through dispatch success path.
6. Provider sees retried same `cmd_id` as duplicate and sends `NACK DUPLICATE`.
7. Attempt 3 has active pending future, matches `NACK DUPLICATE`.
8. Dispatcher recognizes duplicate after ACK timeout and emits `RECONCILE_NEEDED`.

## Why ORDER_OPENED Can Be Unmatched

Dispatcher currently treats `_pending_responses` as a single transient wait slot per `cmd_id`.

During ACK wait timeout:

```python
self._pending_responses.pop(cmd_id, None)
```

Any ACK/ORDER_OPENED arriving after that point has no future to resolve and becomes unmatched:

```python
else:
    logger.warning("Unmatched event ...")
```

For `ord-4fd96f27887e`, `ORDER_OPENED` arrived at `15:21:14.118`, but pending keys were empty, so dispatcher could not convert it into final success.

## User Impact

Risk: medium-high.

Confirmed:

- MT5/provider likely opened order for `ord-4fd96f27887e` because `ORDER_OPENED` event existed.
- Dispatcher did not process it as success because it was unmatched.
- Dispatcher emitted `RECONCILE_NEEDED` instead.

Potential impact:

- Journal/DB may miss `on_order_opened()` for this order because event was unmatched in dispatcher success path.
- Telegram/order state can be ambiguous until reconcile occurs.
- Duplicate retry path can produce confusing sequence: late `ORDER_OPENED` plus later `NACK DUPLICATE`.

Not concluded from this report:

- Whether DB row exists for `ord-4fd96f27887e`. Need DB query by `cmd_id`/trace if fixing/confirming runtime state.

## INVALID_STOPS Check

Two separate things appeared after previous fix:

### Object-shaped SL guard works

Logs show trader rejected malformed strategy events before dispatch:

```text
15:25:12.357 Error processing event: sl must be numeric before MT5 dispatch
15:25:12.358 Error processing event: sl must be numeric before MT5 dispatch
15:25:12.360 Error processing event: sl must be numeric before MT5 dispatch
15:27:06.680 Error processing event: sl must be numeric before MT5 dispatch
15:27:06.689 Error processing event: sl must be numeric before MT5 dispatch
```

That means object-shaped `sl` no longer reaches MT5.

### INVALID_STOPS still occurred once for a different order

Same 30m log window contains:

```text
15:27:06.740 Order rejected: ord-9d53998fd420 (ORDER_FAILED: INVALID_STOPS)
```

This is not the `ACK_LOST_DUPLICATE_RECOVERY` order. It likely uses numeric stops but invalid MT5 geometry/distance after current market checks. Separate issue from object payload parsing.

## Conclusion

`ACK_LOST_DUPLICATE_RECOVERY` is not caused by invalid SL/TP object parsing.

It is dispatcher/provider timing ambiguity:

- ACK timeout too short or provider/order path slower than 5s.
- Late ACK/ORDER_OPENED become unmatched because future is removed on timeout.
- Retrying same `cmd_id` reaches provider idempotency and returns `NACK DUPLICATE`.
- Dispatcher correctly flags reconcile needed, but it loses chance to treat late `ORDER_OPENED` as success.

## Recommended Next Fix

Create separate fix task for dispatcher late-event recovery:

1. Keep per-`cmd_id` state after ACK timeout for a grace window.
2. If late `ORDER_OPENED`/`ORDER_PENDING_PLACED`/`ORDER_FILLED` arrives for a known timed-out `cmd_id`, process it as final success instead of unmatched.
3. If late `ACK` arrives, mark state `LATE_ACK` and continue waiting for final result if dispatch coroutine still alive or route to state machine.
4. If `NACK DUPLICATE` after ACK timeout and no final success known, query/reconcile MT5/DB by `cmd_id`, `symbol`, `magic`, `direction` before declaring failure.
5. Add regression tests for:
   - ACK arrives after timeout but before retry final result.
   - ORDER_OPENED arrives after pending future removed.
   - NACK DUPLICATE after timeout triggers reconcile only if no late success exists.

## Files Inspected

- `services/aureus-trader/dispatcher.py`
- `services/aureus-trader/main.py`
- `mql5/AureusProvider_v2.mq5`
- `services/aureus-trader/order_builder.py`
- Docker logs from `aureus-trader-dev`
