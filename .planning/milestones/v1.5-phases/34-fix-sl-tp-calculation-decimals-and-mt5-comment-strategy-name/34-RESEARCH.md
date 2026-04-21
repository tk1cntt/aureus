# Phase 34 Research

## 1. Goal
Fix SL/TP decimal calculation bug and MT5 strategy name comment bug.

## 2. Findings

### MT5 Comment Strategy Name Bug
**Context:** The comment sent to MT5 currently uses the `strategy_id` instead of the `strategy` name string.
**Trace:**
- In `aureus-signal/engine/orders.py`, the `order` JSON object generated puts the strategy name in the `"strategy_name"` key and the strategy id in `"strategy_id"`.
- This `order` is sent via stream to `aureus-trader/trader.py`.
- `aureus-trader/order_builder.py` parses the `data` (which is the order) and maps `"comment": str(data.get("strategy", data.get("strategy_id", "")))[:31]`. it tries to pull from `"strategy"`.
- Since `"strategy"` doesn't exist, it falls back to `"strategy_id"`.
**Fix:** Update `order_builder.py` to check `"strategy_name"` first.

### SL / TP Calculation Bug
**Context:** When a strategy specifies a SL of `500` (points), it needs to be dynamically converted based on the symbol's decimal precision.
**Trace:**
- In `aureus-signal/engine/orders.py` and `simulated_orders.py` (which contains `_calculate_sl_tp`), the code hardcodes:
  ```python
  if 'JPY' in trigger['strategy'] or state_obj.symbol.endswith('JPY'):
      pips = raw_value / 100.0
  else:
      pips = raw_value / 10000.0
  ```
- This is incorrect. For standard forex, it's 0.00001 (100000 denominator for 5-digit points) or 0.0001 for pips. But strategy '500' is generally points. If 500 is used, XAUUSD should be divided by 100.0 (multiplier 0.01) instead of 10000.0. JPY is 0.001.
**Fix:** Implement a standalone function `get_point_size(symbol: str) -> float` in `orders.py` (and any identical places like `simulated_orders.py`) to correctly scale the `raw_value` based on symbol group (e.g. JPY, XAU/XAG, BTC/Crypto vs generic FOREX).

## RESEARCH COMPLETE
