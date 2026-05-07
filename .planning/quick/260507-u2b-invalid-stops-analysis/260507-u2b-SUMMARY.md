---
quick_id: 260507-u2b
status: completed
completed_at: 2026-05-07
mode: quick-validate
---

# Quick Task 260507-u2b Summary

## Task

Phân tích nguyên nhân lỗi MT5 `INVALID_STOPS` / retcode `10016` khi `AureusProvider_v2` nhận 2 lệnh `BTCUSD` MARKET SELL.

## Input Log

```text
[AureusSocket] RX (804 bytes): {"symbol": "BTCUSD", "direction": "SELL", "tp": {"type": "RR_RATIO", "value": 1.5}, "cmd_id": "ord-c1be6c3bee6a", "risk_amount": 50.0, "comment": "CISD_CONSENSUS_BEAR", "sl": {"type": "PIVOT_POINT", "offset_pips": 1}, "price": 80090.94, "trace_id": "BTCUSD:642:1778175420", "size_mode": "RISK_FIXED_AMOUNT", "order_type": "MARKET", "tp_rr_ratio": 1.5, "volume": 0, "magic": 642000, "type": "OPEN_ORDER"}
{"symbol": "BTCUSD", "direction": "SELL", "tp": {"type": "RR_RATIO", "value": 1.5}, "cmd_id": "ord-b3d8a02b8257", "risk_amount": 50.0, "comment": "CHOCH_CISD_BEAR", "sl": {"type": "PIVOT_POINT", "offset_pips": 1}, "price": 80090.94, "trace_id": "BTCUSD:608:1778175120", "size_mode": "RISK_FIXED_AMOUNT", "order_type": "MARKET", "tp_rr_ratio": 1.5, "volume": 0, "magic": 608000, "type": "OPEN_ORDER"}
[AureusProvider] ORDER_FAILED pushed: cmd_id=ord-c1be6c3bee6a reason=INVALID_STOPS retcode=10016 entry_price=80115.66000 ask=80127.66000 bid=80115.66000
[AureusProvider] ORDER_FAILED pushed: cmd_id=ord-b3d8a02b8257 reason=INVALID_STOPS retcode=10016 entry_price=80115.66000 ask=80127.66000 bid=80115.66000
```

## Root Cause

Root cause: gateway sent strategy SL/TP config objects to MT5 instead of absolute numeric SL/TP prices.

Bad command fields:

```json
"sl": {"type": "PIVOT_POINT", "offset_pips": 1}
"tp": {"type": "RR_RATIO", "value": 1.5}
```

`AureusProvider_v2.mq5` expects numeric fields:

```mql5
double sl = ParseJSONDouble(raw, "sl");
double tp = ParseJSONDouble(raw, "tp");
```

`ParseJSONDouble()` only parses numeric literal fields. For object-valued `sl`/`tp`, first non-space char after colon is `{`, so parser returns `0.0`.

Provider then recalculates for SELL MARKET:

```mql5
entry_price = bid;
sl = sl + total_adjustment;
tp = entry_price - (sl - entry_price) * tpRRRatio;
```

With parsed `sl = 0.0`, output becomes roughly:

- `entry_price = bid = 80115.66`
- `sl ≈ spread + buffer`, still near `12.xx`, not above current BTCUSD price
- `tp = 80115.66 - (12.xx - 80115.66) * 1.5`, huge invalid TP above market

For SELL, MT5 requires:

- SL above Ask/Bid by broker minimum distance.
- TP below Bid by broker minimum distance.

This command creates opposite/invalid stop geometry, so `OrderCheck()` returns `10016 TRADE_RETCODE_INVALID_STOPS`.

## Why Upstream Should Have Sent Numbers

Normal current path computes absolute SL/TP before publish:

- `services/aureus-signal/engine/strategy_executor.py`
  - `prepare_and_publish_strategy_match()` calls `_calculate_sl_tp()`.
  - Writes `res['sl_absolute']` and `res['tp_absolute']`.
- `services/aureus-signal/engine/signal_event_publisher.py`
  - Publishes `data.sl = strategy_result.get("sl_absolute") or strategy_result.get("sl")`.
- `services/aureus-trader/order_builder.py`
  - Builds OPEN_ORDER with `sl = data.get("sl_absolute") or data.get("sl")` and `tp = data.get("tp_absolute") or data.get("tp")`.

So a healthy command should look like:

```json
"sl": 80590.94,
"tp": 79377.85
```

Not object config.

## Most Likely Source

Most likely source: event bypassed or missed `prepare_and_publish_strategy_match()` absolute SL/TP enrichment, so raw strategy config reached trader/order builder.

Evidence:

- Log payload contains raw config objects exactly like strategy config shape.
- It still contains `tp_rr_ratio`, `risk_amount`, `size_mode`, `price`, so order builder forwarded fields into MT5.
- If `sl_absolute`/`tp_absolute` had been present and non-zero, publisher/order_builder would have sent numeric `sl`/`tp`.

## Fix Recommendation

No MQL5 fix should parse SL/TP objects. MT5 provider should remain strict numeric-command consumer.

Best fix area if this recurs:

1. Add trader-side guard in `build_order_command()` or validator: reject non-numeric `sl`/`tp` before sending to MT5.
2. Add signal publisher/test guard ensuring `STRATEGY_MATCH.data.sl/tp` are absolute numeric values for executable orders.
3. Trace why these two BTCUSD strategy matches lacked `sl_absolute`/`tp_absolute` enrichment.

This quick task is report-only because requested action was root-cause analysis, and available evidence identifies malformed payload as immediate cause.

## Verification

Focused tests for normal absolute SL/TP path and pivot SL calculation still pass:

```text
wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus && PYTHONWARNINGS=ignore ./.venv/bin/python -m pytest services/aureus-trader/tests/test_order_builder.py::TestBuildOrderCommand::test_forward_conditional_execution_fields_when_present services/aureus-signal/tests/test_pivot_sl.py -q"
........................                                                 [100%]
24 passed in 9.92s
```

## Result

Failure was not broker random issue. It was deterministic bad payload shape: object `sl`/`tp` reached MQL5 numeric parser, converted to zero, then provider recalculation generated invalid SELL stops. MT5 correctly rejected with retcode `10016`.
