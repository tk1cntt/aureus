# Stack Research: Signal Delivery & Trade Management

## New Dependencies Required

### Python Services

| Library | Version | Purpose | Rationale |
|---------|---------|---------|-----------|
| `python-telegram-bot` | v21.x | Telegram Bot API | Fully async (asyncio-native), built-in job queue, rate limiting support |
| `aiohttp` | v3.x | Async HTTP client | For webhook mode or auxiliary HTTP calls |
| `asyncpg` | v0.29+ | Already in stack | TimescaleDB/PostgreSQL async driver — reuse for trade DB |
| `redis` | v5.x | Already in stack | Event pub/sub for signal→notifier pipeline |
| `pydantic` | v2.x | Data validation | Order request/response schema validation |

### MQL5 (MT5 EA)

| Component | Purpose | Notes |
|-----------|---------|-------|
| Native Socket API | Bidirectional TCP | `SocketCreate`, `SocketConnect`, `SocketSend`, `SocketRead`, `SocketIsReadable` — built-in, no DLL needed |
| `OrderSend()` / `OrderSendAsync()` | Trade execution | Native MQL5 function for market/pending orders |
| `HistorySelect()` / `HistoryOrdersTotal()` | Trade history | For push-based history reporting |

### Dashboard (React/TypeScript)

| Library | Purpose | Notes |
|---------|---------|-------|
| `recharts` | Already in stack | Reuse for performance charts (equity curve, drawdown) |
| Existing FastAPI backend | API layer | Extend with trade performance endpoints |

## What NOT to Add

- **MetaTrader5 Python library**: Requires MT5 terminal on same machine as Python service — doesn't fit Docker architecture
- **ZeroMQ for MT5**: Already analyzed (see `mql5/ANALYSIS_ZMQ_VS_TCP.md`) — native TCP chosen for simplicity
- **Separate database**: Reuse existing TimescaleDB/PostgreSQL — no need for new DB engine
- **External trade analytics libraries** (VectorBT, Backtesting.py): Overkill for dashboard metrics — custom calculation with numpy/pandas is simpler and more maintainable

## Integration Points

- Redis pub/sub: signal engine → notifier (existing pattern from `aureus-signal`)
- TCP socket: aureus-trader → AureusProvider.mq5 (extend existing gateway TCP)
- PostgreSQL/TimescaleDB: trade state persistence (extend existing DB)
- FastAPI: dashboard API (extend existing `aureus-dashboard/api`)
