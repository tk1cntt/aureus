# Phase 35: MT5 Order Status Reporter — Summary (Plan 01)

**Status:** Completed
**Commits:** TBD

## What was built

- **MQL5 EA** (`AureusProvider.mq5`): Added `BuildPositionsJSON()` to poll all open positions with ticket, symbol, direction, volume, prices, profit, swap, SL, TP, pips, open_time
- **MQL5 EA**: Added `ExecutePositionsRequest()` handler and `REQUEST_POSITIONS` routing in `ProcessIncomingCommands()`
- **Gateway** (`main.py`): Added `PositionInfo` and `PositionReportEvent` Pydantic models, registered in `ORDER_EVENT_TYPES`
- **Gateway**: Added `TradeInfo` and `TradeHistoryEvent` models for trade history support
- **Notifier**: Created `order_reporter.py` with `OrderStatusReporter` class — 60s polling cycle, sends formatted reports to Telegram
- **Notifier**: Integrated reporter into `main.py` as async task, configurable via `TELEGRAM_ORDER_BOT_TOKEN`
- **Docker**: Added `TELEGRAM_ORDER_BOT_TOKEN` env var to `docker-compose.dev.yml`

## Telegram report format

```
📊 MT5 Order Report
🟢 Open Positions:
XAUUSD: -2.5$ (-20 pips) - 0.01

💰 Total P/L: +12.8$

❌ Recently Closed (1m):
EURUSD: +5.2$ (+18 pips) - 0.02
```

## Test results

- 19 tests pass (9 gateway + 10 notifier)
