# Features Research: Signal Delivery & Trade Management

## Feature Categories

### 1. Telegram Notification (`aureus-notifier`)

| Feature | Category | Complexity | Dependencies |
|---------|----------|------------|-------------|
| Send signal alerts to Telegram | Table Stakes | Low | Signal engine events |
| Configurable signal filter (which signals to send) | Table Stakes | Low | Config file/DB |
| Strategy match alerts with entry details | Table Stakes | Medium | Strategy evaluation output |
| Message formatting (symbol, direction, SL/TP, confidence) | Table Stakes | Low | Signal schema |
| Rate limiting (Telegram 30 msg/s limit) | Table Stakes | Low | Built-in queue |
| Error recovery (auto-reconnect on Telegram API failure) | Table Stakes | Medium | Retry logic |
| Multiple chat/channel support | Differentiator | Low | Config |
| Signal history in Telegram (inline buttons for detail) | Anti-Feature | High | Unnecessary complexity |

### 2. MT5 Order Execution (`aureus-trader`)

| Feature | Category | Complexity | Dependencies |
|---------|----------|------------|-------------|
| Receive strategy match → create order request | Table Stakes | Medium | Strategy contract |
| Send market order to MT5 | Table Stakes | Medium | EA bidirectional comm |
| Send pending order (limit/stop) to MT5 | Table Stakes | Medium | EA bidirectional comm |
| Order acknowledgement from MT5 (ticket number) | Table Stakes | Medium | EA response protocol |
| Order state tracking (pending → active → closed) | Table Stakes | High | DB + MT5 events |
| MT5 history sync (push events) | Table Stakes | High | EA event reporting |
| MT5 history reconciliation (poll fallback) | Table Stakes | High | Periodic sync loop |
| Order modification (update SL/TP) | Differentiator | Medium | Future enhancement |
| Partial close support | Anti-Feature | High | Rarely needed for v1 |

### 3. Strategy Contract Enhancement

| Feature | Category | Complexity | Dependencies |
|---------|----------|------------|-------------|
| Entry type specification (market/limit/stop) | Table Stakes | Medium | Strategy evaluation |
| SL/TP values in strategy output | Table Stakes | Medium | Strategy evaluation |
| Lot size / risk calculation | Table Stakes | Medium | Account info |
| Magic number per strategy | Table Stakes | Low | Config |

### 4. Performance Dashboard

| Feature | Category | Complexity | Dependencies |
|---------|----------|------------|-------------|
| Trade list with entry/exit details | Table Stakes | Medium | Trade DB |
| Win rate calculation | Table Stakes | Low | Trade history |
| Profit factor | Table Stakes | Low | Trade history |
| Max drawdown | Table Stakes | Medium | Equity curve |
| Sharpe ratio | Differentiator | Medium | Return series |
| Average R:R (Risk-Reward) | Table Stakes | Low | Trade SL/TP data |
| Equity curve chart | Table Stakes | Medium | Time series |
| Filter by symbol/strategy/timeframe | Table Stakes | Medium | UI + API |
| Daily/weekly/monthly P&L breakdown | Differentiator | Medium | Aggregation |
| Export to CSV | Differentiator | Low | API endpoint |

## Expected Behavior Summary

**Signal Flow:** Signal engine emits event → Redis pub/sub → `aureus-notifier` picks up → formats message → sends to Telegram.

**Trade Flow:** Strategy match → `aureus-trader` creates order → sends via TCP to MT5 EA → EA executes `OrderSend()` → returns ticket → `aureus-trader` tracks state → MT5 pushes close event → `aureus-trader` updates DB → dashboard shows results.

**Reconciliation Flow:** Every 30-60s, `aureus-trader` polls MT5 history → compares with DB → fills any gaps (missed events during disconnect).
