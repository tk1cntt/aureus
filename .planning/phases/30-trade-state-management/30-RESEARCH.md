# Phase 30: Trade State Management - Research

**Researched:** 2026-04-06
**Domain:** TimescaleDB hypertables, Redis Streams consumer patterns, asyncpg JSONB, state machine design
**Confidence:** HIGH

## Summary

This phase implements persistent trade lifecycle management on top of existing infrastructure: the `aureus-db-writer` service (asyncpg + Redis Streams consumer), `aureus-trader` dispatcher (ACK/NACK order protocol), and `aureus-signal` engine (SimulatedTradeManager writing to `aureus:stream:{symbol}:orders`).

The core work is: (1) creating the `aureus_trades` hypertable in the existing schema, (2) adding an `order_buffer` to the DB writer that consumes `aureus:stream:*:orders` with upsert semantics, and (3) implementing state transition validation in the trader dispatcher. All three decisions (D1-D4) from CONTEXT.md are locked and well-aligned with existing patterns.

Key technical finding: The existing Redis stream message format uses `{"type": "...", "data": json.dumps(order_dict)}` — a nested JSON string that requires `json.loads()` on the `data` field before DB insertion. This matches the pattern already used for `execution_buffer`, `position_buffer`, and `account_buffer` in the DB writer.

**Primary recommendation:** Follow the existing buffer pattern exactly — add `order_buffer` list, wild-card stream discovery for `aureus:stream:*:orders`, parse the nested JSON `data` field, upsert with `ON CONFLICT (trace_id) DO UPDATE` using JSONB `||` merge.

## User Constraints (from CONTEXT.md)

### Locked Decisions

**D1: Trade Table Schema — Hypertable with JSONB Payload**
- Create `aureus_trades` hypertable in `schema.sql` with columns: id, trace_id, ticket, symbol, magic_number, strategy_id, strategy_name, direction, entry_type, status, entry_price, exit_price, sl, tp, volume, commission, swap, profit, created_at, updated_at, filled_at, closed_at, payload (JSONB)
- Hypertable conversion: `SELECT create_hypertable('aureus_trades', 'created_at', if_not_exists => TRUE)`
- Indexes on: symbol, status, magic_number, ticket, strategy_id
- `trace_id` links to `cmd_id` from Phase 29 (idempotency key)
- `ON CONFLICT (trace_id) DO UPDATE` for idempotent writes
- Payload merge: `payload = aureus_trades.payload || EXCLUDED.payload`

**D2: Order State Machine — 5-Status Lifecycle**
- 5-state machine: `PENDING → SENT → FILLED → CLOSED` with terminal states `FAILED`, `CANCELLED`
- Stateless validation function in `dispatcher.py` — no separate state machine class
- Reuse `ALLOWED_TRANSITIONS` dict pattern from nautilus bridge
- Terminal states (FAILED, CANCELLED) do not allow further transitions

**D3: Magic Number Filter — WHERE Clause on DB Queries**
- Implement at DB query layer, not EA or trader
- EA pushes ALL order events (including manual) with `magic_number` field
- Filter: `magic_number IN (SELECT magic_number FROM aureus_strategy_templates)` for bot trades
- Filter: `magic_number NOT IN (...) AND magic_number IS NOT NULL` for manual trades

**D4: DB Writer Integration — New `order` Buffer Type**
- Extend `aureus-db-writer/main.py` with `order_buffer` consuming `aureus:stream:{symbol}:orders`
- Stream pattern: subscribe `aureus:stream:*:orders` (wildcard for all symbols)
- `ON CONFLICT (trace_id) DO UPDATE` with JSONB merge `payload = aureus_trades.payload || EXCLUDED.payload`
- Reuse existing buffer pattern (tick, candle, execution buffers)

### the agent's Discretion
- Compression and retention policy intervals for the hypertable
- Connection pool sizing for concurrent writes
- Exact state transition implementation details in dispatcher.py
- Index strategy for Phase 32 performance queries

### Deferred Ideas (OUT OF SCOPE)
- Separate state machine class/library
- Magic number filtering at EA or trader level
- Alternative storage (non-TimescaleDB)

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| TRADE-01 | Order state machine tracking (pending → sent → filled → closed) | State machine pattern verified in reconciliation.py; 5-state design locked in D2 |
| TRADE-02 | Trade records in TimescaleDB | Schema pattern locked in D1; DB writer buffer pattern verified in main.py lines 100-480 |
| TRADE-05 | Magic number filter phân biệt bot vs manual trades | Filter at DB query layer (D3); `aureus_strategy_templates.magic_number` exists in schema.sql |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| asyncpg | 0.31.0 (verified) | Async PostgreSQL driver | Already in use by aureus-db-writer; fastest async Python PG driver; native JSONB support |
| timescaledb | Built into aureus-timescaledb container | Time-series hypertables | Already deployed; `create_hypertable()` used for candles, snapshots, execution events |
| redis.asyncio | Already in use | Redis Streams consumer | DB writer already uses `redis.asyncio`; stream consumer groups established pattern |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| PostgreSQL JSONB operators | Native (`\|\|` merge, `#>` extraction) | Incremental payload updates | Every order state transition upsert |
| TimescaleDB compression policy | `add_compression_policy()` | Auto-compress old chunks | After hypertable creation |
| TimescaleDB retention policy | `add_retention_policy()` | Auto-drop old trade data | If storage cost is concern |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Dict-based state validation | `transitions` library or `statemachine` | Overkill for 5 states; adds dependency; existing pattern works |
| JSONB `payload \|\| EXCLUDED.payload` | `jsonb_set()` or full replacement | `\|\|` is simplest for append-only event merging; `jsonb_set` needs explicit key paths |
| `ON CONFLICT (trace_id)` | Separate events table + view | Simpler single-table; Phase 32 queries benefit from denormalized structure |

**Installation:** No new packages needed. All dependencies (asyncpg 0.31.0, redis.asyncio, timescaledb) are already in use.

**Version verification:**
```bash
pip show asyncpg  # Version: 0.31.0 [VERIFIED]
```

## Architecture Patterns

### Recommended Project Structure

No new directories needed. All changes are within existing files:

```
services/aureus-db-writer/
├── schema.sql          # APPEND: aureus_trades table + hypertable + policies
└── main.py             # EXTEND: order_buffer, stream discovery, process_batch handler

services/aureus-trader/
└── dispatcher.py       # EXTEND: state transition validation in dispatch_order()
```

### Pattern 1: Buffer-based Stream Consumer (Existing)

**What:** DB writer discovers streams by pattern, reads via consumer groups, buffers messages, and flushes in batches to PostgreSQL.

**When to use:** This is the established pattern for all data types (ticks, candles, execution events, positions, accounts). Orders follow identically.

**Example — stream discovery (extend `discover_streams`):**
```python
# In DBWriter.discover_streams() — ADD to patterns list:
patterns = [
    "aureus:stream:*:tick",
    "aureus:stream:*:candle",
    "aureus:stream:*:swing_point",
    "aureus:stream:*:execution",
    "aureus:stream:*:positions",
    "aureus:stream:*:account",
    "aureus:stream:*:orders",       # <-- NEW for Phase 30
]
```

**Example — buffer routing (extend `run()` loop):**
```python
# In DBWriter.run() — ADD to stream routing:
elif ":orders" in stream_name:
    self.order_buffer.append((stream_name, msg_id, payload))
```

Source: [VERIFIED — `services/aureus-db-writer/main.py` lines 107-116 (patterns), lines 456-466 (routing)]

### Pattern 2: Nested JSON Stream Message Format

**What:** Order stream messages use `{"type": "...", "data": json.dumps(order_dict)}` — the `data` field is a JSON-encoded string, not a native object.

**When to use:** Every DB writer buffer handler that reads from order streams must `json.loads()` the `data` field first.

**Example — parsing order stream messages:**
```python
# In process_batch() order handler:
for stream, msg_id, payload in orders_to_insert:
    try:
        raw_data = payload.get('data')
        event_data = json.loads(raw_data) if isinstance(raw_data, str) else (raw_data or {})

        # Extract fields from event_data (not payload)
        trace_id = event_data.get('trace_id')
        symbol = event_data.get('symbol', 'UNKNOWN')
        status = event_data.get('status', 'PENDING')
        # ...
    except Exception as e:
        logger.error(f"Order parse error: {e}")
```

Source: [VERIFIED — `services/aureus-signal/engine/orders.py` lines 165-167, 189-191, 197-199, 254-256 (xadd calls)]

### Pattern 3: State Transition Validation (Dict-based)

**What:** Simple dict mapping current state → allowed next states, with terminal states having empty sets.

**When to use:** In `dispatcher.py` to validate state transitions before emitting events.

**Example:**
```python
# At module level in dispatcher.py:
TRADE_ALLOWED_TRANSITIONS = {
    "PENDING": {"SENT", "FAILED"},
    "SENT": {"FILLED", "FAILED", "CANCELLED"},
    "FILLED": {"CLOSED", "FAILED"},
    "CLOSED": set(),
    "FAILED": set(),
    "CANCELLED": set(),
}

def can_transition(current_status: str, new_status: str) -> bool:
    """Check if a state transition is valid."""
    if not current_status:
        return True  # Initial state — any status allowed
    allowed = TRADE_ALLOWED_TRANSITIONS.get(current_status, set())
    return new_status in allowed
```

Source: [VERIFIED — `services/aureus-nautilus-bridge/reconciliation.py` `ALLOWED_TRANSITIONS` dict pattern]

### Pattern 4: Upsert with JSONB Merge

**What:** `ON CONFLICT (trace_id) DO UPDATE` with `payload = payload || EXCLUDED.payload` for incremental event history.

**When to use:** Every order event (PENDING, SENT, FILLED, CLOSED) upserts the same row, merging new fields into the JSONB payload.

**Example:**
```sql
INSERT INTO aureus_trades (
    trace_id, ticket, symbol, magic_number, strategy_id, strategy_name,
    direction, entry_type, status, entry_price, sl, tp, volume,
    filled_at, closed_at, payload
) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16::jsonb)
ON CONFLICT (trace_id) DO UPDATE SET
    ticket = COALESCE(EXCLUDED.ticket, aureus_trades.ticket),
    status = EXCLUDED.status,
    entry_price = COALESCE(EXCLUDED.entry_price, aureus_trades.entry_price),
    exit_price = COALESCE(EXCLUDED.exit_price, aureus_trades.exit_price),
    profit = COALESCE(EXCLUDED.profit, aureus_trades.profit),
    filled_at = COALESCE(EXCLUDED.filled_at, aureus_trades.filled_at),
    closed_at = COALESCE(EXCLUDED.closed_at, aureus_trades.closed_at),
    updated_at = NOW(),
    payload = aureus_trades.payload || EXCLUDED.payload
```

Source: [CITED — docs.timescale.com + VERIFIED existing `aureus_execution_events` pattern in schema.sql]

### Anti-Patterns to Avoid

- **Don't use separate events table:** The locked decision (D1) is a single hypertable. Don't create `aureus_trade_events` — Phase 32 queries need denormalized access.
- **Don't overwrite payload on upsert:** Use `payload || EXCLUDED.payload` to preserve event history. Plain `EXCLUDED.payload` loses previous events.
- **Don't validate state in DB writer:** State validation belongs in `dispatcher.py` (D2). DB writer should be a dumb consumer — insert whatever it receives.
- **Don't use `json.dumps()` for asyncpg JSONB params:** Pass the string directly or use `set_type_codec`. See "asyncpg JSONB handling" below.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| State machine library | Custom state machine class | Dict-based `ALLOWED_TRANSITIONS` | 5 states is trivial; library adds dependency and complexity |
| JSON merge logic | Manual field-by-field merge in Python | PostgreSQL `jsonb \|\| jsonb` operator | DB-side merge is atomic, handles nested keys, avoids race conditions |
| Stream discovery | Hard-coded stream list | Pattern-based SCAN (existing `discover_streams()`) | New symbols appear dynamically; pattern matching is already implemented |
| Connection pooling | Single connection per batch | asyncpg `create_pool()` (existing) | Pool handles concurrent access, connection lifecycle, and failover |
| Idempotent writes | Check-then-insert | `ON CONFLICT ... DO UPDATE` | Atomic, handles concurrent writers, no race conditions |

**Key insight:** The existing DB writer already handles 6 buffer types with identical patterns. Adding a 7th (`order_buffer`) is mechanical — copy the `execution_buffer` pattern and adapt field mapping.

## Runtime State Inventory

> Not applicable — this is a greenfield phase (new table, new buffer), not a rename/refactor/migration.

## Common Pitfalls

### Pitfall 1: Nested JSON String in Stream Messages
**What goes wrong:** The DB writer tries to read `payload.get('trace_id')` directly, but the order data is nested inside `payload.get('data')` as a JSON-encoded string.
**Why it happens:** Order streams use `{"type": "...", "data": json.dumps(order_dict)}` while tick streams use flat `{"symbol": "...", "bid": ..., "ask": ...}`.
**How to avoid:** Always `json.loads(payload['data'])` first for order messages — same pattern as `execution_buffer`, `position_buffer`, `account_buffer`.
**Warning signs:** `trace_id is None` errors in process_batch log output.

### Pitfall 2: asyncpg JSONB Parameter Casting
**What goes wrong:** Passing a Python `dict` to a `$N::jsonb` parameter without encoding causes `asyncpg.exceptions.DataError`.
**Why it happens:** asyncpg maps `jsonb` to Python `str` by default, not `dict`.
**How to avoid:** Either (a) `json.dumps(dict)` before passing, or (b) register a codec with `conn.set_type_codec('jsonb', encoder=json.dumps, decoder=json.loads, schema='pg_catalog')`. The existing DB writer uses approach (a) — `json.dumps(event_payload)` in all buffer handlers. [VERIFIED — main.py lines 298, 357, 408]
**Warning signs:** `asyncpg.exceptions.DataError: invalid input for query argument $16: {...}`

### Pitfall 3: State Transition Race Conditions
**What goes wrong:** Two events for the same `trace_id` arrive nearly simultaneously — e.g., FILLED and FAILED — and both try to upsert.
**Why it happens:** Redis Streams delivers messages in order, but DB writer batches may process them out of order if multiple consumers exist.
**How to avoid:** Current consumer group setup (`CONSUMER_GROUP = "aureus-db-writers"`) with single consumer name means single-threaded processing per stream. The `ON CONFLICT` upsert handles the DB side. For safety, add `WHERE aureus_trades.status NOT IN ('CLOSED', 'FAILED', 'CANCELLED')` to the UPDATE clause to prevent overwriting terminal states. [ASSUMED — single consumer per group in current deployment]
**Warning signs:** Terminal state (CLOSED) gets overwritten by earlier event (SENT).

### Pitfall 4: TimescaleDB Chunk Size for Low-Volume Trades
**What goes wrong:** If trade volume is low, chunks may be very small (< 1000 rows), reducing compression efficiency.
**Why it happens:** Default chunk interval is 7 days. If only a few trades per day per symbol, chunks will be tiny.
**How to avoid:** Set `chunk_time_interval` to a longer period (e.g., 30 days) for the trades hypertable, or accept lower compression ratios for low-volume data.
**Warning signs:** Compression ratio < 2x on trades table.

### Pitfall 5: Missing `magic_number` in Stream Messages
**What goes wrong:** Current SimulatedTradeManager order objects don't include `magic_number` — it comes from Phase 26 STRATEGY_MATCH payload.
**Why it happens:** The existing `orders.py` builds order dicts without `magic_number` field. Phase 29's real order pipeline may or may not include it.
**How to avoid:** Ensure Phase 29's order command includes `magic_number` in the stream message. If missing, insert `NULL` and rely on later reconciliation. [ASSUMED — Phase 29 order pipeline may not yet include magic_number]
**Warning signs:** `magic_number` column is NULL for most rows, breaking TRADE-05 filters.

## Code Examples

### 1. DB Writer — Order Buffer Processing
```python
# In DBWriter.__init__ — ADD:
self.order_buffer = []

# In DBWriter.discover_streams() — ADD to patterns:
patterns = [
    # ... existing patterns ...
    "aureus:stream:*:orders",
]

# In DBWriter.run() — ADD to routing:
elif ":orders" in stream_name:
    self.order_buffer.append((stream_name, msg_id, payload))

# In DBWriter.process_batch() — ADD after account_buffer handler:
if self.order_buffer:
    orders_to_insert = self.order_buffer[:]
    self.order_buffer.clear()
    data_rows, msg_ids, stream_keys = [], [], []

    for stream, msg_id, payload in orders_to_insert:
        try:
            raw_data = payload.get('data')
            event_data = json.loads(raw_data) if isinstance(raw_data, str) else (raw_data or {})
            if not isinstance(event_data, dict):
                raise ValueError("Order payload data must be a JSON object")

            trace_id = event_data.get('trace_id')
            if not trace_id:
                # Fallback: use msg_id-based timestamp as trace
                trace_id = f"order:{msg_id}"
                logger.warning(f"Order missing trace_id, using {trace_id}")

            # Extract timestamp from msg_id (Redis stream ID format: timestamp-seq)
            ts_ms = int(msg_id.split('-')[0])
            event_ts = datetime.fromtimestamp(ts_ms / 1000.0)

            row = (
                trace_id,
                event_data.get('ticket'),                   # BIGINT, NULL until filled
                event_data.get('symbol', 'UNKNOWN'),
                event_data.get('magic_number'),             # BIGINT, may be NULL
                event_data.get('strategy_id'),
                event_data.get('strategy_name'),
                event_data.get('side', event_data.get('direction', 'UNKNOWN')),
                event_data.get('type', event_data.get('entry_type', 'MARKET')),
                event_data.get('status', 'PENDING'),
                float(event_data.get('entry_price', 0.0)) if event_data.get('entry_price') else None,
                float(event_data.get('exit_price', 0.0)) if event_data.get('exit_price') else None,
                float(event_data.get('sl', 0.0)) if event_data.get('sl') else None,
                float(event_data.get('tp', 0.0)) if event_data.get('tp') else None,
                float(event_data.get('volume', 0.0)) if event_data.get('volume') else None,
                float(event_data.get('commission', 0.0)) if event_data.get('commission') else None,
                float(event_data.get('swap', 0.0)) if event_data.get('swap') else None,
                float(event_data.get('pnl', event_data.get('profit', 0.0))) if event_data.get('pnl') or event_data.get('profit') else None,
                event_ts if event_data.get('status') in ('FILLED', 'ACTIVE') else None,  # filled_at
                event_ts if event_data.get('status') == 'CLOSED' else None,              # closed_at
                json.dumps(event_data),                    # payload as JSONB
            )
            data_rows.append(row)
            msg_ids.append(msg_id)
            stream_keys.append(stream)
        except Exception as e:
            logger.error(f"[GLOBAL] [process_batch] Error: Order parse error: {e}")

    if data_rows:
        query = """
            INSERT INTO aureus_trades (
                trace_id, ticket, symbol, magic_number, strategy_id, strategy_name,
                direction, entry_type, status, entry_price, exit_price,
                sl, tp, volume, commission, swap, profit,
                filled_at, closed_at, payload
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20::jsonb)
            ON CONFLICT (trace_id) DO UPDATE SET
                ticket = COALESCE(EXCLUDED.ticket, aureus_trades.ticket),
                status = EXCLUDED.status,
                entry_price = COALESCE(EXCLUDED.entry_price, aureus_trades.entry_price),
                exit_price = COALESCE(EXCLUDED.exit_price, aureus_trades.exit_price),
                profit = COALESCE(EXCLUDED.profit, aureus_trades.profit),
                filled_at = COALESCE(EXCLUDED.filled_at, aureus_trades.filled_at),
                closed_at = COALESCE(EXCLUDED.closed_at, aureus_trades.closed_at),
                updated_at = NOW(),
                payload = aureus_trades.payload || EXCLUDED.payload
            WHERE aureus_trades.status NOT IN ('CLOSED', 'FAILED', 'CANCELLED')
               OR EXCLUDED.status IN ('CLOSED', 'FAILED', 'CANCELLED')
        """
        await conn.executemany(query, data_rows)

        # ACK messages
        acks = {}
        for s, m in zip(stream_keys, msg_ids):
            if s not in acks:
                acks[s] = []
            acks[s].append(m)
        pipe = self.redis.pipeline()
        for s, ids in acks.items():
            pipe.xack(s, CONSUMER_GROUP, *ids)
        await pipe.execute()
        logger.info(f"[GLOBAL] [process_batch] 7... Inserted/Updated {len(data_rows)} trades")
```

### 2. Schema — aureus_trades Table + Compression + Retention
```sql
-- Trade Records Table (Phase 30)
CREATE TABLE IF NOT EXISTS aureus_trades (
    id                  BIGSERIAL PRIMARY KEY,
    trace_id            TEXT NOT NULL UNIQUE,             -- Idempotency key (cmd_id from trader)
    ticket              BIGINT,                           -- MT5 order ticket (NULL until filled)
    symbol              TEXT NOT NULL,
    magic_number        BIGINT,                           -- Bot vs manual trade filter
    strategy_id         BIGINT,
    strategy_name       TEXT,
    direction           TEXT NOT NULL,                    -- BUY / SELL
    entry_type          TEXT NOT NULL,                    -- MARKET / LIMIT / STOP
    status              TEXT NOT NULL DEFAULT 'PENDING',  -- 5-state machine
    entry_price         DOUBLE PRECISION,
    exit_price          DOUBLE PRECISION,
    sl                  DOUBLE PRECISION,
    tp                  DOUBLE PRECISION,
    volume              DOUBLE PRECISION,
    commission          DOUBLE PRECISION DEFAULT 0,
    swap                DOUBLE PRECISION DEFAULT 0,
    profit              DOUBLE PRECISION DEFAULT 0,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    filled_at           TIMESTAMPTZ,
    closed_at           TIMESTAMPTZ,
    payload             JSONB                             -- Full event data for debugging
);

-- Convert to Hypertable
SELECT create_hypertable('aureus_trades', 'created_at', if_not_exists => TRUE);

-- Indexes for Phase 32 performance queries
CREATE INDEX IF NOT EXISTS idx_trades_symbol ON aureus_trades(symbol);
CREATE INDEX IF NOT EXISTS idx_trades_status ON aureus_trades(status);
CREATE INDEX IF NOT EXISTS idx_trades_magic ON aureus_trades(magic_number);
CREATE INDEX IF NOT EXISTS idx_trades_ticket ON aureus_trades(ticket);
CREATE INDEX IF NOT EXISTS idx_trades_strategy ON aureus_trades(strategy_id);

-- Composite indexes for Phase 32 common queries
CREATE INDEX IF NOT EXISTS idx_trades_symbol_status ON aureus_trades(symbol, status);
CREATE INDEX IF NOT EXISTS idx_trades_created_at_desc ON aureus_trades(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_trades_strategy_created ON aureus_trades(strategy_id, created_at DESC);

-- Compression policy: compress chunks older than 30 days
ALTER TABLE aureus_trades SET (timescaledb.compress = true);
SELECT add_compression_policy('aureus_trades',
    compress_after => INTERVAL '30 days',
    schedule_interval => INTERVAL '12h',
    if_not_exists => TRUE
);

-- Retention policy: drop chunks older than 2 years (adjust as needed)
SELECT add_retention_policy('aureus_trades',
    drop_after => INTERVAL '2 years',
    if_not_exists => TRUE
);
```

### 3. Dispatcher — State Transition Validation
```python
# In dispatcher.py — ADD at module level:
TRADE_ALLOWED_TRANSITIONS = {
    "PENDING": {"SENT", "FAILED"},
    "SENT": {"FILLED", "FAILED", "CANCELLED"},
    "FILLED": {"CLOSED", "FAILED"},
    "CLOSED": set(),
    "FAILED": set(),
    "CANCELLED": set(),
}

def is_valid_trade_transition(current_status: str, new_status: str) -> bool:
    """Check if a trade state transition is valid."""
    if not current_status:
        return True  # Initial state — any status allowed
    allowed = TRADE_ALLOWED_TRANSITIONS.get(current_status, set())
    return new_status in allowed

# In dispatch_order() — ADD state tracking:
# After ACK received: validate PENDING → SENT transition
# After ORDER_OPENED: validate SENT → FILLED transition
# After ORDER_FAILED: validate SENT → FAILED or PENDING → FAILED
```

## asyncpg JSONB Handling [VERIFIED]

**Source:** [CITED — https://magicstack.github.io/asyncpg/current/usage.html]

asyncpg 0.31.0 maps PostgreSQL `jsonb` to Python `str` by default. Two approaches:

**Approach A (current DB writer pattern):** `json.dumps()` the dict, pass as string, cast in query:
```python
query = "SELECT $1::jsonb"
await conn.fetchval(query, json.dumps({"key": "value"}))
```
This is what the existing `execution_buffer`, `position_buffer`, and `account_buffer` use. [VERIFIED — main.py lines 298, 357, 408]

**Approach B (codec registration):** Register automatic encoding/decoding:
```python
await conn.set_type_codec(
    'jsonb',
    encoder=json.dumps,
    decoder=json.loads,
    schema='pg_catalog'
)
# Now you can pass dicts directly
await conn.fetchval('SELECT $1::jsonb', {"key": "value"})
```

**Recommendation:** Stick with Approach A (current pattern) for consistency. No need to change codec setup for one new buffer type.

**JSONB `||` merge operator:** Works natively in parameterized queries:
```sql
payload = aureus_trades.payload || EXCLUDED.payload
```
Both sides are `jsonb` columns/expressions — no parameter casting needed. [CITED — PostgreSQL jsonb documentation]

## Connection Pool Setup

The existing DB writer uses `asyncpg.create_pool()` without explicit sizing:
```python
self.pg_pool = await asyncpg.create_pool(
    host=POSTGRES_HOST,
    port=POSTGRES_PORT,
    user=POSTGRES_USER,
    password=POSTGRES_PASSWORD,
    database=POSTGRES_DB
)
```

Default asyncpg pool size is 10 connections. For the trade writer workload:
- **Single consumer** processes orders sequentially per batch
- **One connection** from pool is used per `process_batch()` call
- **10 default connections** is more than sufficient

**Recommendation:** Keep default pool size. No changes needed. If future scaling requires multiple DB writer instances, the consumer group pattern already handles distributed consumption.

## TimescaleDB Compression & Retention [VERIFIED]

**Source:** [CITED — https://docs.timescale.com/api/latest/compression/add_compression_policy/, https://docs.timescale.com/api/latest/data-retention/add_retention_policy/]

### Compression Policy
```sql
ALTER TABLE aureus_trades SET (timescaledb.compress = true);
SELECT add_compression_policy('aureus_trades',
    compress_after => INTERVAL '30 days',
    schedule_interval => INTERVAL '12h',
    if_not_exists => TRUE
);
```
- `compress_after => INTERVAL '30 days'`: Compress chunks with data older than 30 days
- `schedule_interval => INTERVAL '12h'`: Check for compressible chunks every 12 hours (default)
- Prerequisite: `ALTER TABLE ... SET (timescaledb.compress = true)` must run first

**Chunk sizing note:** TimescaleDB compresses in batches of 1,000 rows. Chunks with fewer rows get poor compression ratios. For low-volume trading (few trades/day/symbol), consider setting a longer chunk interval:
```sql
-- Optional: Set larger chunk interval for low-volume trades
SELECT set_chunk_time_interval('aureus_trades', INTERVAL '30 days');
```

### Retention Policy
```sql
SELECT add_retention_policy('aureus_trades',
    drop_after => INTERVAL '2 years',
    if_not_exists => TRUE
);
```
- `drop_after => INTERVAL '2 years'`: Drop chunks older than 2 years
- Trade data is valuable for backtesting/analysis, so 2 years is a reasonable default
- Can be adjusted based on actual storage constraints

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Separate order/event tables | Single hypertable with JSONB payload | 2020s (TimescaleDB maturity) | Simpler queries, better time-range performance |
| Check-then-insert for idempotency | `ON CONFLICT ... DO UPDATE` | PostgreSQL 9.5+ (2016) | Atomic, no race conditions |
| State machine libraries | Dict-based transition maps | Pattern choice | Fewer dependencies, easier to audit |
| Manual JSON merge in Python | PostgreSQL `jsonb \|\|` operator | PostgreSQL 9.4+ (2014) | Atomic merge, handles nested keys |
| Hard-coded stream names | Pattern-based stream discovery | Redis 6.0+ SCAN | Dynamic symbol support |

**Deprecated/outdated:**
- **`timescaledb-tune` auto-config:** Not deprecated, but manual compression/retention policies are preferred over relying solely on tune tool for hypertable-specific settings.
- **Trigger-based state transitions:** Don't use DB triggers for state validation — application-level validation (in dispatcher.py) is more testable and debuggable.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Phase 29 order pipeline includes `magic_number` in stream messages | Pitfall 5 | TRADE-05 filters won't work; need to add magic_number to order commands |
| A2 | Single DB writer consumer instance in current deployment | Pitfall 3 | Multiple consumers could process out-of-order; need stronger terminal state protection |
| A3 | `aureus_strategy_templates` table has a `magic_number` column | D3 (CONTEXT.md) | Bot/manual filter query fails; need to verify Phase 26 actually added this column |
| A4 | Redis stream `aureus:stream:{symbol}:orders` uses the same consumer group `aureus-db-writers` | D4 | Stream consumption fails; consumer group must exist |

## Open Questions

1. **Does Phase 29's real order command include `magic_number`?**
   - What we know: Phase 26 added `magic_number` to STRATEGY_MATCH payload and `aureus_strategy_templates`
   - What's unclear: Whether Phase 29's order dispatch pipeline passes `magic_number` through to the stream
   - Recommendation: Plan should include a verification step — grep Phase 29 code for `magic_number` in order commands

2. **What is the exact `aureus_strategy_templates.magic_number` column name and type?**
   - What we know: D3 references `aureus_strategy_templates.magic_number` as source of truth
   - What's unclear: Current schema.sql shows the table but does NOT have a `magic_number` column
   - Recommendation: This may have been added in Phase 26 but not reflected in schema.sql. Plan should verify and add if missing.

3. **Should compression interval be 30 days or longer?**
   - What we know: TimescaleDB recommends chunks with ≥1000 rows for good compression
   - What's unclear: Expected trade volume per day per symbol
   - Recommendation: Start with 30 days, monitor compression ratio, adjust if needed

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| asyncpg | DB writer JSONB handling | ✓ | 0.31.0 | — |
| Redis (with Streams) | Order event consumption | ✓ | In docker-compose | — |
| TimescaleDB | Hypertable for trades | ✓ | In docker-compose | — |
| PostgreSQL JSONB operators | Payload merge | ✓ | Native | — |

All dependencies are available. No missing tools or services.

## Validation Architecture

> nyquist_validation is assumed enabled (key absent from config = enabled).

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (existing) |
| Config file | Check for pytest.ini/pyproject.toml in services/aureus-db-writer |
| Quick run command | `pytest tests/ -x -q` |
| Full suite command | `pytest tests/ -v` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TRADE-01 | Valid state transitions allowed | unit | `pytest tests/test_trade_state_machine.py -x` | ❌ Wave 0 |
| TRADE-01 | Invalid state transitions rejected | unit | `pytest tests/test_trade_state_machine.py::test_invalid_transitions -x` | ❌ Wave 0 |
| TRADE-02 | Order events upserted to aureus_trades | integration | `pytest tests/test_db_writer_orders.py -x` | ❌ Wave 0 |
| TRADE-02 | JSONB payload merge on conflict | integration | `pytest tests/test_db_writer_orders.py::test_payload_merge -x` | ❌ Wave 0 |
| TRADE-02 | Idempotent writes (duplicate trace_id) | integration | `pytest tests/test_db_writer_orders.py::test_idempotent_upsert -x` | ❌ Wave 0 |
| TRADE-05 | Bot trade filter query works | unit | `pytest tests/test_magic_number_filter.py -x` | ❌ Wave 0 |
| TRADE-05 | Manual trade filter query works | unit | `pytest tests/test_magic_number_filter.py::test_manual_filter -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** Quick unit tests for affected module
- **Per wave merge:** Full test suite for DB writer + trader
- **Phase gate:** All TRADE-01/02/05 tests passing

### Wave 0 Gaps
- [ ] `tests/test_trade_state_machine.py` — covers TRADE-01 state transitions
- [ ] `tests/test_db_writer_orders.py` — covers TRADE-02 order buffer, upsert, JSONB merge
- [ ] `tests/test_magic_number_filter.py` — covers TRADE-05 SQL filter queries
- [ ] Test fixtures: shared Redis mock + asyncpg connection pool fixtures
- [ ] DB writer test infrastructure: may need mock Redis + test PostgreSQL container

## Security Domain

> security_enforcement status: not explicitly checked. Including minimal analysis.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V5 Input Validation | yes | JSON schema validation on stream messages before DB insert |
| V6 Cryptography | no | No cryptographic operations in this phase |
| V8 Error Handling | yes | Structured error logging for parse failures, no sensitive data in logs |

### Known Threat Patterns for Trade State Management

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malformed stream messages | Tampering | Try/except with structured logging, skip bad messages |
| State injection (forced terminal state) | Elevation | `WHERE status NOT IN terminal` clause in upsert |
| Payload data exfiltration in logs | Information Disclosure | Mask sensitive fields in log output, log only trace_id + status |

## Sources

### Primary (HIGH confidence)
- [VERIFIED — codebase] `services/aureus-db-writer/main.py` — buffer patterns, connection pool, stream discovery
- [VERIFIED — codebase] `services/aureus-db-writer/schema.sql` — existing hypertable definitions, indexes
- [VERIFIED — codebase] `services/aureus-signal/engine/orders.py` — Redis stream message format (xadd calls)
- [VERIFIED — codebase] `services/aureus-trader/dispatcher.py` — ACK/NACK protocol, dispatch loop
- [VERIFIED — codebase] `services/aureus-nautilus-bridge/reconciliation.py` — ALLOWED_TRANSITIONS dict pattern
- [VERIFIED — pip] asyncpg 0.31.0 — installed version
- [CITED — magicstack.github.io/asyncpg] asyncpg JSONB usage patterns
- [CITED — docs.timescale.com] add_compression_policy, add_retention_policy syntax

### Secondary (MEDIUM confidence)
- [ASSUMED — Phase 26] `aureus_strategy_templates.magic_number` column exists (not verified in current schema.sql)
- [ASSUMED — Phase 29] Order command pipeline includes `magic_number` in stream messages

### Tertiary (LOW confidence)
- Trade volume estimates for chunk sizing recommendations — no production data available

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries verified in codebase
- Architecture: HIGH — patterns verified against existing buffer implementations
- Pitfalls: HIGH-MEDIUM — most verified against code; A1/A2/A3/A4 are assumptions
- TimescaleDB policies: HIGH — verified against official documentation

**Research date:** 2026-04-06
**Valid until:** 2026-05-06 (30 days — stable domain, TimescaleDB/asyncpg APIs don't change frequently)
