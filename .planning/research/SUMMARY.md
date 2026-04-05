# Research Summary: Signal Delivery & Trade Management

## Stack Additions

| Addition | Purpose |
|----------|---------|
| `python-telegram-bot` v21.x | Async Telegram Bot API cho aureus-notifier |
| Native MQL5 Socket + OrderSend API | Bidirectional order execution — no external DLL |
| Extend existing asyncpg + Redis + FastAPI | Reuse stack, no new engines |

**What NOT to add:** MetaTrader5 Python lib (wrong architecture), ZeroMQ (already rejected), separate DB engine, heavy analytics libs.

## Feature Table Stakes

| Area | Must-Have Count | Key Items |
|------|----------------|-----------|
| Telegram Notification | 6 | Signal alerts, strategy match alerts, configurable filter, rate limiting |
| MT5 Order Execution | 7 | Market + pending orders, order state machine, history sync (push + poll) |
| Strategy Contract | 4 | Entry type, SL/TP, lot size, magic number |
| Performance Dashboard | 8 | Win rate, profit factor, drawdown, equity curve, trade list, filters |

## Architecture Integration

- **2 new services:** `aureus-notifier` (Telegram), `aureus-trader` (MT5 orders)
- **1 extended component:** `AureusProvider.mq5` (bidirectional: add order receive + event push)
- **1 extended service:** `aureus-dashboard` (add trade performance pages + API)
- **Communication:** Redis pub/sub (internal) + TCP socket (MT5)
- **Build order:** Strategy contract → Signal events → Notifier → EA extension → Trader → History sync → DB schema → Dashboard

## Watch Out For

| Risk | Severity | Prevention |
|------|----------|------------|
| MT5 state drift | HIGH | Reconciliation loop + magic number filtering |
| Duplicate orders | HIGH | Idempotency key + order state machine |
| TCP connection drop | HIGH | Heartbeat + order queue persistence + ACK protocol |
| Telegram rate limiting | MEDIUM | Message queue + rate limiter (25 msg/s) |
| Strategy breaking change | MEDIUM | Optional fields with defaults |
| Order latency/slippage | MEDIUM | Direct TCP + latency monitoring |
