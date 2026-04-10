# Phase 35: MT5 Order Status Reporter — Summary (Plan 02, Pips accuracy fix)

**Status:** Completed
**Commits:** TBD

## What was built

- **MQL5 EA** (`AureusProvider.mq5`): Updated `BuildTradeHistoryJSON` to calculate pips directly from MT5 using `SymbolInfoInteger(SYMBOL_DIGITS)` instead of Python heuristics
- **Gateway** (`main.py`): Added `digits` and `pips` optional fields to `TradeInfo` model
- **Notifier** (`order_reporter.py`): Updated to use EA-provided `pips` field directly, removed price-based heuristic (>50 guess)
- **Notifier tests**: Updated mock payloads and assertions for new pips field

## What changed

Pips calculation moved from Python heuristic to MT5 authoritative source:
```mql5
long digits = SymbolInfoInteger(sym, SYMBOL_DIGITS);
double mult = (digits == 3 || digits == 5) ? MathPow(10, digits - 1) : MathPow(10, digits);
double pips = (closePrice - openPrice) * mult;
if(dealType == DEAL_TYPE_BUY) pips = -pips;
```

## Test results

- All notifier and gateway tests pass with new pips field
- Telegram reports show accurate pips for all asset types (forex, gold, indices, crypto)
