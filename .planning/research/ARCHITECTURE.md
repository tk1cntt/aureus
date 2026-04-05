# Architecture Research: Signal Delivery & Trade Management

## Existing Architecture (What We Have)

```
MT5 ──TCP──→ aureus-gateway ──Redis──→ aureus-signal ──Redis──→ (consumers)
                                           │
                                    strategy evaluation
                                           │
                                    decision trace → DB
```

## Proposed Architecture (What We're Adding)

```
                                    aureus-signal
                                    │           │
                              signal events   strategy matches
                                    │           │
                              Redis pub/sub  Redis pub/sub
                                    │           │
                            aureus-notifier  aureus-trader
                                    │           │
                              Telegram API   TCP socket
                                    │           │
                              User phone     AureusProvider.mq5 (extended)
                                                │
                                          MT5 Terminal
                                           OrderSend()
                                                │
                                          Order events
                                                │
                                          TCP push back
                                                │
                                          aureus-trader
                                                │
                                          PostgreSQL/TimescaleDB
                                                │
                                          aureus-dashboard (extended)
```

## New Components

### 1. `aureus-notifier` (New Service)
- **Language:** Python (async)
- **Input:** Redis pub/sub channels (`signal:events`, `strategy:matches`)
- **Output:** Telegram Bot API
- **Config:** JSON/YAML signal filter rules
- **Docker:** New container, lightweight

### 2. `aureus-trader` (New Service)
- **Language:** Python (async)
- **Input:** Redis pub/sub channel (`strategy:matches`)
- **Output:** TCP socket to MT5 EA, PostgreSQL
- **Responsibilities:**
  - Order creation and dispatch
  - Order state machine (pending → sent → filled → closed)
  - History sync (push receiver + poll reconciler)
  - Trade performance calculation
- **Docker:** New container

### 3. `AureusProvider.mq5` (Extended)
- **Current:** Market data streaming (ticks + candles) → gateway
- **New:** Receive order commands ← aureus-trader
  - `OPEN_ORDER`: market/pending order with SL/TP
  - `MODIFY_ORDER`: update SL/TP (future)
  - `CLOSE_ORDER`: close position (future)
- **New:** Push order events → aureus-trader
  - `ORDER_OPENED`: ticket, price, time
  - `ORDER_CLOSED`: ticket, close price, profit, time
  - `ORDER_MODIFIED`: ticket, new SL/TP
  - `ORDER_FAILED`: ticket, error code

### 4. Strategy Contract Enhancement
- **Current:** Strategy returns `{action, confidence, signals}`
- **New:** Strategy returns `{action, confidence, signals, entry_type, sl, tp, lot_size}`
- **Backward compatible:** New fields optional, default to market order if absent

### 5. Dashboard Extension
- **New API endpoints:** `/api/trades`, `/api/performance`, `/api/equity-curve`
- **New pages:** Trade history, Performance metrics
- **Reuse:** Existing FastAPI + React + recharts infrastructure

## Integration Points

| From | To | Method | Data |
|------|----|--------|------|
| aureus-signal | aureus-notifier | Redis pub/sub | Signal events |
| aureus-signal | aureus-trader | Redis pub/sub | Strategy matches |
| aureus-trader | AureusProvider.mq5 | TCP socket | Order commands (JSON) |
| AureusProvider.mq5 | aureus-trader | TCP socket | Order events (JSON) |
| aureus-trader | PostgreSQL | asyncpg | Trade records |
| aureus-dashboard API | PostgreSQL | asyncpg | Trade queries |

## Suggested Build Order

1. **Strategy contract enhancement** — foundation for everything else
2. **Signal pub/sub events** — emit events from signal engine
3. **aureus-notifier** — quickest win, validates pub/sub pipeline
4. **AureusProvider.mq5 extension** — bidirectional order protocol
5. **aureus-trader core** — order dispatch + state machine
6. **MT5 history sync** — push + poll reconciliation
7. **Trade DB schema** — persistent storage
8. **Dashboard API + UI** — performance metrics and trade history

## Data Flow Changes

- Signal engine needs to **publish events** to Redis (currently only writes to DB/Redis state)
- Gateway needs a **reverse channel** to forward order commands to MT5 EA (currently one-way)
- Strategy evaluation needs to **output trade parameters** (currently only action/confidence)
