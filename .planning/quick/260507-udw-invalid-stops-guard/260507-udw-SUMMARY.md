---
quick_id: 260507-udw
status: completed
completed_at: 2026-05-07
mode: quick-validate
---

# Quick Task 260507-udw Summary

## Task

Fix theo suggest từ `260507-u2b`: chặn `sl`/`tp` không phải numeric trước khi dispatch sang MT5 để tránh `INVALID_STOPS` do MQL5 parse object thành `0.0`.

## Root Cause From Prior Report

`260507-u2b` xác định MT5 nhận payload sai shape:

```json
"sl": {"type": "PIVOT_POINT", "offset_pips": 1}
"tp": {"type": "RR_RATIO", "value": 1.5}
```

`AureusProvider_v2.mq5` expects numeric `sl`/`tp`. Object fields parse to `0.0`, then SELL stop recalculation produces invalid MT5 stops.

## Changes

- `services/aureus-trader/order_builder.py`
  - Added `_require_numeric_stop(value, field_name)`.
  - `build_order_command()` now validates selected `sl` and `tp` are numeric `Real` and not `bool`.
  - Invalid object/list/string/null stops raise clear `ValueError` before MT5 dispatch.
  - Numeric path unchanged.

- `services/aureus-trader/tests/test_order_builder.py`
  - Added regression test rejecting object `sl` before MT5 dispatch.
  - Added regression test rejecting object `tp` before MT5 dispatch.
  - Added regression test proving numeric absolute SL/TP still pass through.

## GitNexus Impact

Command:

```text
npx gitnexus impact build_order_command --repo Aureus --direction upstream
```

Result:

```text
risk: CRITICAL
impactedCount: 2
direct: run_trader
processes affected:
- Run_trader → _lane_key
- Run_trader → Get_context
- Run_trader → _extract_mt5_execution_payload
- Run_trader → _send_alert
- Run_trader → _wait_for_response
module: Aureus-trader
```

Risk accepted because change is a narrow fail-fast guard at MT5 command boundary. Direct runtime caller must not send malformed stop payloads.

## Verification

Order builder regression suite:

```text
wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus && PYTHONWARNINGS=ignore ./.venv/bin/python -m pytest services/aureus-trader/tests/test_order_builder.py -q"
.................                                                        [100%]
17 passed in 0.38s
```

Dispatcher payload contract still passes:

```text
wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus && PYTHONWARNINGS=ignore ./.venv/bin/python -m pytest services/aureus-trader/tests/test_dispatcher.py::TestOrderDispatcherPayloadContract -q"
.                                                                        [100%]
1 passed in 0.21s
```

Static diff check:

```text
git diff --check -- services/aureus-trader/order_builder.py services/aureus-trader/tests/test_order_builder.py
```

Result: no output, exit 0.

GitNexus detect-changes unavailable:

```text
npx gitnexus detect-changes --repo Aureus
error: unknown command 'detect-changes'
```

## Result

Bad object-shaped `sl`/`tp` now fails in trader before MT5 dispatch. Provider no longer receives malformed stop payload that would parse to zero and produce `INVALID_STOPS`.
