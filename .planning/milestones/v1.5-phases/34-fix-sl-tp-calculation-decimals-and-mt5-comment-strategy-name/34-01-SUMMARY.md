# Phase 34: Fix SL TP calculation decimals and MT5 comment strategy name — Summary

**Status:** Completed

## What was built

- **Dynamic point size helper** `get_point_size(symbol)` in `orders.py` — maps symbol patterns to correct multipliers (XAU→0.01, JPY→0.001, BTC→0.01, SPX→0.1, default→0.00001)
- **Refactored `_calculate_sl_tp`** in both `orders.py` and `simulated_orders.py` to use `get_point_size(state_obj.symbol)` instead of hardcoded `/10000.0` and `/100.0`
- **MT5 order comment fix** in `order_builder.py` — prioritizes `strategy_name` over `strategy_id` for the comment field

## Files modified

- `services/aureus-signal/engine/orders.py` — added `get_point_size()`, refactored `_calculate_sl_tp`
- `services/aureus-signal/engine/simulated_orders.py` — imported and applied `get_point_size()`
- `services/aureus-trader/order_builder.py` — comment field uses `strategy_name` first

## Test results

- SL/TP calculations now use correct decimal precision per symbol type
- MT5 comment displays strategy name correctly
