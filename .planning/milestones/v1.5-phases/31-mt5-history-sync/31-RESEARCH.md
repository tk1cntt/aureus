# Phase 31: MT5 History Sync - Research

**Researched:** 2026-04-07
**Domain:** MQL5 Trade History API, Redis Streams XPENDING, Reconciliation Patterns
**Confidence:** HIGH

## Summary

This phase extends `aureus-db-writer` with a 2-tier reconciliation system: (1) Redis XPENDING recovery for unacked stream messages, and (2) MT5 trade history polling via a new EA command `REQUEST_TRADE_HISTORY`. The EA already has the infrastructure for bidirectional TCP commands (`ProcessIncomingCommands()` handles `REQUEST_BACKFILL`, `REQUEST_BACKFILL_COUNT`, `OPEN_ORDER`, `CLOSE_ORDER`), command dedup (`IsDuplicateCmd`/`RecordCmdId`), ACK/NACK protocol, and event pushing (`PushOrderOpened`, `PushOrderClosed`, `PushOrderFailed`). The MQL5 trade history API (`HistorySelect` → `HistoryDealsTotal` → loop with `HistoryDealGetTicket` → `HistoryDealSelect` → `HistoryDealGetInteger/GetDouble/GetString`) provides ground-truth deal data including `DEAL_ENTRY_OUT` for closed positions.

The DB writer already has: Redis connection with consumer groups, Postgres pool, `aureus_trades` table with `UNIQUE(trace_id)`, state machine validation, batch processing with ACK, and timestamp parsing from millisecond-epoch strings.

**Primary recommendation:** Implement `REQUEST_TRADE_HISTORY` in EA using `HistorySelect(from, to)` + `HistoryDealsTotal()` + index loop filtering `DEAL_ENTRY_OUT` deals, return as `TRADE_HISTORY` JSON via existing TCP socket. In DB writer, add `check_xpending()` startup check + `reconciliation_loop()` with env-configurable interval (10-300s, default 30s), insert missing trades with `status='RECONCILED'` bypassing state machine validation.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**D1: Hybrid Sync — Redis Streams Primary, MT5 History Fallback**
- 2-tier: Tier 1 = XPENDING check, Tier 2 = MT5 history poll via `REQUEST_TRADE_HISTORY`
- Merge: Compare DB tickets vs MT5 tickets, insert missing with `status='RECONCILED'`
- Reconciliation flow: every 30s, query DB recent trades, query MT5 via EA command, compare, insert missing

**D2: Implementation Location — Extend `aureus-db-writer`**
- Add as new async task in existing `run()` loop
- No new service — reuse Redis connection, Postgres pool, schema apply

**D3: Configurable Poll Frequency**
- `HISTORY_SYNC_INTERVAL_SEC=30` default
- Min: 10s, Max: 300s, invalid → fallback 30s
- `interval = max(10, min(300, int(os.environ.get('HISTORY_SYNC_INTERVAL_SEC', '30'))))`

**D4: Auto-Fix with `RECONCILED` Status**
- Missing trades auto-inserted with `status='RECONCILED'`
- `ON CONFLICT (trace_id) DO NOTHING`
- Discrepancy logging in structured JSON format

**D5: XPENDING Recovery + MT5 History Fallback**
- Phase 1: `check_xpending()` on startup — recover unacked messages
- Phase 2: `poll_mt5_history()` — query EA for recent trades
- Startup: XPENDING check before main loops start

### the agent's Discretion
None explicitly marked as discretion — all decisions are locked.

### Deferred Ideas (OUT OF SCOPE)
None explicitly deferred.

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| TRADE-03 | Push events từ MT5 EA cập nhật trade records real-time | EA already pushes ORDER_OPENED/ORDER_CLOSED/ORDER_FAILED via TCP → gateway → Redis stream → DB writer. XPENDING recovery ensures no message loss on consumer crash. |
| TRADE-04 | Poll reconciliation mỗi 30-60s | REQUEST_TRADE_HISTORY command + EA HistorySelect API + DB comparison loop + RECONCILED auto-insert. Configurable via HISTORY_SYNC_INTERVAL_SEC. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `redis` (redis-py async) | 7.2.0 | Redis Streams XPENDING, XRANGE, XACK | Already installed in db-writer requirements.txt. `xpending()` with range returns `list[dict]` with `message_id`, `consumer`, `time_since_delivered`, `times_delivered` [VERIFIED: pip show redis] |
| `asyncpg` | 0.31.0 | Postgres/TimescaleDB queries | Already installed. Used for all DB operations in main.py [VERIFIED: pip show asyncpg] |
| MQL5 `HistorySelect`/`HistoryDealSelect` API | Built-in MT5 | Query trade deal history from EA | Standard MQL5 API — `HistorySelect(from, to)` selects range, `HistoryDealsTotal()` returns count, loop via `HistoryDealGetTicket(i)` [VERIFIED: MQL5 docs] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Python `asyncio` | stdlib 3.11 | Concurrent reconciliation loop + stream consumer | For `asyncio.create_task()` pattern in DBWriter.run() |
| Python `json` | stdlib | Serialize/deserialize EA command payloads | For REQUEST_TRADE_HISTORY command and TRADE_HISTORY response |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| XPENDING polling | XAUTOCLAIM with idle threshold | XAUTOCLAIM is cleaner but changes message ownership — XPENDING + XRANGE is read-only inspection, safer for reconciliation audit |
| EA TCP command for history | Redis pub/sub from EA to push history | EA already has TCP command infrastructure — adding new command type is simpler than new pub/sub path |

**Installation:**
No new packages needed — all dependencies already in `services/aureus-db-writer/requirements.txt`.

**Version verification:**
- `redis==7.2.0` [VERIFIED: pip show redis — 7.2.0 installed] — supports `xpending(start, end, count, consumer)` detailed mode
- `asyncpg==0.31.0` [VERIFIED: requirements.txt] — supports all standard asyncpg operations
- Python 3.11-slim [VERIFIED: Dockerfile] — stdlib asyncio, json, logging all available

## Architecture Patterns

### Recommended Project Structure

No new files or directories needed. Changes are confined to existing files:

```
services/aureus-db-writer/
├── main.py                 # EXTEND: Add check_xpending(), reconciliation_loop(), run_reconciliation()
├── schema.sql              # NO CHANGE (aureus_trades already has UNIQUE(trace_id), status TEXT)
├── state_machine.py        # NO CHANGE (reconciliation bypasses state machine)
└── Dockerfile              # NO CHANGE (no new dependencies)

mql5/
└── AureusProvider.mq5      # EXTEND: Add REQUEST_TRADE_HISTORY handler + BuildTradeHistoryJSON() + PushTradeHistory()
```

### Pattern 1: XPENDING Recovery (Read-Only Inspection)

**What:** Check Redis Streams for messages delivered but never ACKed by this consumer group. Re-process them and ACK.

**When to use:** On startup (recover from previous crash) and optionally during reconciliation runs.

**Example:**
```python
async def check_xpending(self):
    """Check for unacknowledged messages from previous runs."""
    # Only check order streams — those are the ones that matter for trades
    order_streams = [s for s in self.known_streams if ":orders" in s]
    for stream in order_streams:
        try:
            # Detailed XPENDING: returns list of dicts
            pending = await self.redis.xpending(stream, CONSUMER_GROUP, '-', '+', 100)
            if not pending:
                continue

            for entry in pending:
                msg_id = entry['message_id']
                idle_ms = entry['time_since_delivered']
                
                # Fetch message content via XRANGE
                messages = await self.redis.xrange(stream, min=msg_id, max=msg_id, count=1)
                if messages:
                    _, payload = messages[0]
                    # Re-process: add to order buffer and flush
                    self.order_buffer.append((stream, msg_id, payload))
                    await self.process_batch()
                    logger.info(f"Recovered unacked message: {msg_id} (idle={idle_ms}ms)")
        except Exception as e:
            logger.error(f"XPENDING check failed for {stream}: {e}")
```

**Source:** Redis XPENDING docs [VERIFIED: redis.readthedocs.io] — `xpending(name, groupname, start, end, count)` returns `list[dict]` with keys: `message_id`, `consumer`, `time_since_delivered`, `times_delivered`

### Pattern 2: MQL5 Trade History Iteration

**What:** EA receives `REQUEST_TRADE_HISTORY` command, queries MT5 deal history, returns matching deals as JSON.

**When to use:** Every reconciliation poll cycle (default 30s).

**Example (MQL5):**
```mql5
//+------------------------------------------------------------------+
//| Build TRADE_HISTORY JSON response                                 |
//+------------------------------------------------------------------+
void SendTradeHistory(datetime fromTime, datetime toTime, long magicFilter=0)
{
   if(!HistorySelect(fromTime, toTime))
   {
      PrintFormat("[AureusProvider] HistorySelect(%s, %s) failed",
                  TimeToString(fromTime), TimeToString(toTime));
      // Send empty response
      string errJson = StringFormat("{\"type\":\"TRADE_HISTORY\",\"trades\":[],\"error\":\"HistorySelect failed\"}");
      g_socket.SendJSON(errJson);
      return;
   }
   
   int total = HistoryDealsTotal();
   string tradesJson = "{\"type\":\"TRADE_HISTORY\",\"trades\":[";
   bool first = true;
   
   for(int i = 0; i < total; i++)
   {
      ulong ticket = HistoryDealGetTicket(i);
      if(!HistoryDealSelect(ticket)) continue;
      
      // Filter: only position close deals
      long entry = HistoryDealGetInteger(ticket, DEAL_ENTRY);
      if(entry != DEAL_ENTRY_OUT) continue;
      
      // Filter: magic number
      long magic = HistoryDealGetInteger(ticket, DEAL_MAGIC);
      if(magicFilter > 0 && magic != magicFilter) continue;
      
      string symbol = HistoryDealGetString(ticket, DEAL_SYMBOL);
      double volume = HistoryDealGetDouble(ticket, DEAL_VOLUME);
      double price  = HistoryDealGetDouble(ticket, DEAL_PRICE);
      double profit = HistoryDealGetDouble(ticket, DEAL_PROFIT);
      double comm   = HistoryDealGetDouble(ticket, DEAL_COMMISSION);
      double swap   = HistoryDealGetDouble(ticket, DEAL_SWAP);
      long   posId  = HistoryDealGetInteger(ticket, DEAL_POSITION_ID);
      long   type   = HistoryDealGetInteger(ticket, DEAL_TYPE);
      long   timeMs = HistoryDealGetInteger(ticket, DEAL_TIME_MSC);
      
      string direction = (type == DEAL_TYPE_BUY) ? "BUY" : "SELL";
      
      if(!first) tradesJson += ",";
      first = false;
      
      tradesJson += StringFormat(
         "{\"ticket\":%I64u,\"position_id\":%I64u,\"symbol\":\"%s\","
         "\"direction\":\"%s\",\"volume\":%.2f,\"close_price\":%.5f,"
         "\"profit\":%.2f,\"commission\":%.2f,\"swap\":%.2f,"
         "\"magic\":%I64u,\"t\":%I64u}",
         ticket, posId, symbol, direction, volume, price,
         profit, comm, swap, magic, timeMs
      );
   }
   
   tradesJson += "]}";
   g_socket.SendJSON(tradesJson);
   PrintFormat("[AureusProvider] TRADE_HISTORY sent: %d deals in range", total);
}
```

**Source:** MQL5 API Reference [VERIFIED: MQL5 docs via web_fetch] — `HistoryDealGetTicket(i)` gets ticket by index, `DEAL_ENTRY_OUT` = position close, `DEAL_TIME_MSC` = millisecond timestamp

### Pattern 3: Reconciliation Loop with DB Comparison

**What:** Periodic async task comparing DB trades vs MT5 history, inserting missing records.

**When to use:** Every N seconds (configurable 10-300s, default 30s).

**Example:**
```python
async def reconciliation_loop(self):
    interval = max(10, min(300, int(os.environ.get('HISTORY_SYNC_INTERVAL_SEC', '30'))))
    logger.info(f"Reconciliation loop started (interval={interval}s)")
    while self.running:
        try:
            await self.run_reconciliation()
        except Exception as e:
            logger.error(f"Reconciliation run failed: {e}")
        await asyncio.sleep(interval)

async def run_reconciliation(self):
    """2-tier reconciliation: XPENDING recovery + MT5 history poll."""
    # Tier 1: Quick XPENDING check
    await self.check_xpending()
    
    # Tier 2: Get recent DB trades
    async with self.pg_pool.acquire() as conn:
        db_trades = await conn.fetch("""
            SELECT ticket, symbol, magic_number, status, trace_id
            FROM aureus_trades
            WHERE closed_at > NOW() - INTERVAL '5 minutes'
               OR (closed_at IS NULL AND filled_at > NOW() - INTERVAL '5 minutes')
        """)
    
    db_tickets = {row['ticket'] for row in db_trades if row['ticket']}
    
    # Request trade history from EA
    five_min_ago_ms = int((time.time() - 300) * 1000)
    now_ms = int(time.time() * 1000)
    
    history_cmd = {
        "type": "REQUEST_TRADE_HISTORY",
        "from_time": five_min_ago_ms,
        "to_time": now_ms,
        "magic_number": None,
        "symbol": None
    }
    
    # Send via Redis pub/sub to gateway (which forwards to EA via TCP)
    await self.redis.publish('aureus:mt5:commands', json.dumps(history_cmd))
    
    # Wait for response (EA responds via TCP → gateway → Redis stream)
    # ... response handling ...
    
    # Compare and insert missing
    for mt5_trade in mt5_trades:
        if mt5_trade['ticket'] not in db_tickets:
            await self.insert_reconciled_trade(mt5_trade)
```

### Anti-Patterns to Avoid

- **Don't use `HistoryOrderSelect` for reconciliation** — Orders track the request, Deals track the actual execution. Use `HistoryDealSelect` with `DEAL_ENTRY_OUT` to find closed positions. [VERIFIED: MQL5 docs]
- **Don't bypass XPENDING before checking it** — XPENDING messages are the fastest recovery path. Always check XPENDING before polling MT5 history.
- **Don't validate RECONCILED trades through state machine** — Reconciled trades may arrive out of order (e.g., CLOSED status without prior PENDING/SENT/FILLED). State machine will reject them. [VERIFIED: state_machine.py — only PENDING→SENT→FILLED→CLOSED allowed]
- **Don't use `DEAL_ENTRY_IN` for reconciliation** — That's position opening. `ORDER_OPENED` events already handle this. Use `DEAL_ENTRY_OUT` for closes.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Pending message recovery | Custom "unacked tracker" | Redis XPENDING + XRANGE | Redis already tracks delivery count, idle time, consumer ownership — battle-tested |
| Trade history iteration | EA-side deal cache in memory | MQL5 HistorySelect/HistoryDealSelect API | MT5 terminal manages deal history — it's the ground truth, handles server sync automatically |
| Time window queries | Custom timestamp comparison | `HistorySelect(datetime from, datetime to)` | Built-in range selection, handles timezone and DST internally |
| Command dedup in EA | New dedup mechanism | Existing `IsDuplicateCmd()`/`RecordCmdId()` FIFO array | Already handles 500 cmd IDs with FIFO eviction [VERIFIED: AureusProvider.mq5 lines 569-591] |
| JSON parsing in EA | Custom JSON library | Existing `ParseJSONString()`/`ParseJSONDouble()`/`ParseJSONLong()` | Already handles all needed field types [VERIFIED: AureusProvider.mq5 lines 530-567] |

**Key insight:** The EA already has all the infrastructure needed — TCP socket, command parsing, ACK/NACK, event pushing, command dedup. The only missing piece is the `REQUEST_TRADE_HISTORY` handler that calls `HistorySelect` + iterates deals.

## Runtime State Inventory

> This is a new feature phase, not a rename/refactor/migration. No runtime state changes required.
> 
> However, the following existing runtime state is relevant:

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | `aureus_trades` table — existing records with statuses: PENDING, SENT, FILLED, CLOSED, FAILED, CANCELLED | New `RECONCILED` status will be added. No migration needed — `status` is TEXT column. |
| Live service config | Redis consumer group `aureus-db-writers` on `aureus:stream:*:orders` streams | XPENDING check will read from existing PEL (Pending Entries List). No config change. |
| OS-registered state | None | — |
| Secrets/env vars | New env var `HISTORY_SYNC_INTERVAL_SEC` (default 30) | Add to docker-compose.dev.yml `aureus-db-writer-dev` environment section |
| Build artifacts | None | — |

## Common Pitfalls

### Pitfall 1: XPENDING Returns Metadata Only, Not Message Content
**What goes wrong:** Developer calls `XPENDING` expecting message payloads, gets only `{message_id, consumer, time_since_delivered, times_delivered}`.
**Why it happens:** Redis XPENDING is designed to return metadata only — content requires a separate `XRANGE` or `XREADGROUP` call.
**How to avoid:** Always follow `XPENDING` with `XRANGE(stream, min=msg_id, max=msg_id, count=1)` to get content. [VERIFIED: Redis docs via web_fetch]
**Warning signs:** `XPENDING` returns entries but no data to re-process.

### Pitfall 2: DEAL_ENTRY_OUT May Not Have Original Open Price
**What goes wrong:** Reconciled trade record missing `entry_price` because closed deal only has `DEAL_PRICE` (close price), not open price.
**Why it happens:** MT5 deal history separates entry deals (`DEAL_ENTRY_IN`) from exit deals (`DEAL_ENTRY_OUT`). The exit deal knows close price but not open price.
**How to avoid:** For `DEAL_ENTRY_OUT` deals, use `HistoryDealGetInteger(ticket, DEAL_POSITION_ID)` to get the position ID, then select the corresponding `DEAL_ENTRY_IN` deal to get `entry_price`. Alternatively, look up existing DB record by `ticket` — if FOUND but missing `closed_at`, update it. If NOT FOUND, record `entry_price` as null and flag for manual review.
**Warning signs:** Reconciled trades with null `entry_price`.

### Pitfall 3: MT5 History Time Range Gaps
**What goes wrong:** `HistorySelect(from, to)` returns fewer deals than expected because MT5 terminal hasn't synced all history from broker server.
**Why it happens:** MT5 caches deal history locally. If the terminal was offline during trade execution, deals may not be available until the terminal syncs with the broker.
**How to avoid:** Use generous time windows (5 minutes lookback). Log when `HistoryDealsTotal()` returns 0 for a non-zero time window as a warning. On terminal reconnect, trigger a wider history query.
**Warning signs:** Reconciliation finds 0 MT5 deals for a time range where DB also has 0 trades, but orders were executed.

### Pitfall 4: Timezone Mismatch Between MT5 and DB
**What goes wrong:** MT5 uses broker server timezone, DB uses UTC. Reconciliation compares wrong time ranges.
**Why it happens:** `DEAL_TIME` and `DEAL_TIME_MSC` return broker-local timestamps. Python `datetime.fromtimestamp()` assumes local timezone unless explicitly told UTC.
**How to avoid:** MT5 `HistoryDealGetInteger(ticket, DEAL_TIME_MSC)` returns milliseconds since epoch (UTC). Python `datetime.fromtimestamp(ms / 1000.0)` uses local system timezone. **Fix:** Use `datetime.utcfromtimestamp(ms / 1000.0)` or `datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc)` to ensure UTC. The existing DB writer code already handles this correctly for stream payloads [VERIFIED: main.py `parse_ts` function].
**Warning signs:** Reconciliation inserts trades with timestamps 7-8 hours off (common for Asia broker servers).

### Pitfall 5: Reconciliation Insert Conflicts with Real-Time Insert
**What goes wrong:** Reconciliation tries to insert a trade that was just inserted by the real-time stream consumer, causing a unique constraint violation.
**Why it happens:** Race condition — real-time stream processes ORDER_CLOSED event and inserts trade at nearly the same time reconciliation runs.
**How to avoid:** Use `ON CONFLICT (trace_id) DO NOTHING` for reconciled inserts. Log a debug message (not error) when conflict occurs — it means real-time path worked correctly. [VERIFIED: schema.sql — `aureus_trades` has `UNIQUE(trace_id)`]
**Warning signs:** Frequent "duplicate key" errors in reconciliation logs — not actually errors, just race conditions.

### Pitfall 6: EA TCP Response Routing
**What goes wrong:** DB writer sends `REQUEST_TRADE_HISTORY` via Redis pub/sub but EA responds via TCP to gateway — response doesn't reach DB writer.
**Why it happens:** The architecture uses TCP socket between EA and gateway, not Redis directly. Commands flow: DB writer → Redis pub/sub → gateway → TCP → EA. Responses flow: EA → TCP → gateway → ??? → DB writer.
**How to avoid:** The gateway must forward EA responses to a Redis stream or pub/sub channel that DB writer subscribes to. Either: (a) gateway publishes TRADE_HISTORY to `aureus:stream:*:orders` stream, or (b) DB writer subscribes to a dedicated response channel via Redis pub/sub. **Recommended:** Gateway publishes to `aureus:stream:{server}:orders` stream so DB writer's existing consumer group processes it naturally.
**Warning signs:** DB writer sends commands but never receives responses.

## Code Examples

Verified patterns from existing codebase:

### EA Command Handler Pattern (from AureusProvider.mq5)

**Source:** `mql5/AureusProvider.mq5` lines 914-990 — `ProcessIncomingCommands()` [VERIFIED: read_file]

```mql5
// Add this handler in ProcessIncomingCommands():
if(StringFind(raw, "REQUEST_TRADE_HISTORY") >= 0)
{
   int fromPos = StringFind(raw, "\"from_time\":");
   int toPos   = StringFind(raw, "\"to_time\":");
   int magicPos = StringFind(raw, "\"magic_number\":");
   
   if(fromPos > 0 && toPos > 0)
   {
      long fromMs = ParseJSONLong(raw, "from_time");
      long toMs   = ParseJSONLong(raw, "to_time");
      long magic  = ParseJSONLong(raw, "magic_number"); // 0 = all
      
      datetime fromTime = (datetime)(fromMs / 1000);
      datetime toTime   = (datetime)(toMs / 1000);
      
      PrintFormat("[AureusProvider] REQUEST_TRADE_HISTORY: %s to %s (magic=%I64d)",
                  TimeToString(fromTime), TimeToString(toTime), magic);
      
      SendTradeHistory(fromTime, toTime, magic);
   }
   return;
}
```

### DB Writer XPENDING Check Pattern

**Source:** Redis docs + existing `process_batch()` order handling [VERIFIED: main.py lines 438-603]

```python
async def check_xpending(self):
    """Recover unacked order messages from all order streams."""
    order_streams = [s for s in self.known_streams if ":orders" in s]
    recovered_count = 0
    
    for stream in order_streams:
        try:
            pending = await self.redis.xpending(stream, CONSUMER_GROUP, '-', '+', 100)
            if not pending:
                continue
            
            for entry in pending:
                msg_id = entry['message_id']
                
                # Fetch content
                messages = await self.redis.xrange(stream, min=msg_id, max=msg_id, count=1)
                if not messages:
                    continue
                
                _, payload = messages[0]
                event_type = payload.get('type', '')
                
                # Only recover real order events, not rejections
                if event_type == 'ORDER_REJECTED':
                    await self.redis.xack(stream, CONSUMER_GROUP, msg_id)
                    continue
                
                # Re-process through existing pipeline
                self.order_buffer.append((stream, msg_id, payload))
                recovered_count += 1
            
            if recovered_count > 0:
                await self.process_batch()
                logger.info(f"Recovered {recovered_count} unacked order messages")
        except Exception as e:
            logger.error(f"XPENDING check failed for {stream}: {e}")
```

### Reconciled Trade Insert Pattern

**Source:** Existing order insert in `process_batch()` + CONTEXT.md D4 [VERIFIED: main.py lines 580-597]

```python
async def insert_reconciled_trade(self, mt5_trade: dict):
    """Insert a trade found by MT5 history reconciliation."""
    import uuid
    
    trace_id = f"reconciled-{mt5_trade['ticket']}-{mt5_trade.get('t', 0)}"
    
    # Parse MT5 millisecond timestamp
    closed_at = datetime.fromtimestamp(
        mt5_trade['t'] / 1000.0, tz=timezone.utc
    ) if mt5_trade.get('t') else None
    
    direction = mt5_trade.get('direction', 'UNKNOWN')
    
    async with self.pg_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO aureus_trades (
                trace_id, ticket, symbol, magic_number,
                direction, entry_type, status,
                exit_price, volume,
                commission, swap, profit,
                closed_at, payload
            ) VALUES ($1, $2, $3, $4, $5, $6, 'RECONCILED', $7, $8, $9, $10, $11, $12, $13)
            ON CONFLICT (trace_id) DO NOTHING
        """, 
            trace_id,
            mt5_trade.get('ticket'),
            mt5_trade.get('symbol', 'UNKNOWN'),
            mt5_trade.get('magic'),
            direction,
            'MARKET',  # Reconciled trades are always market orders
            mt5_trade.get('close_price'),
            mt5_trade.get('volume'),
            mt5_trade.get('commission', 0),
            mt5_trade.get('swap', 0),
            mt5_trade.get('profit', 0),
            closed_at,
            json.dumps({**mt5_trade, "source": "mt5_history_reconciliation"})
        )
        
        logger.info(
            f"Reconciled missing trade: ticket={mt5_trade.get('ticket')}, "
            f"symbol={mt5_trade.get('symbol')}, source=mt5_history"
        )
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Poll-only reconciliation | Hybrid: XPENDING + MT5 history poll | Phase 31 design decision | XPENDING recovery is milliseconds vs seconds for MT5 poll |
| Manual trade reconciliation | Auto-fix with RECONCILED status | Phase 31 design decision | Eliminates data loss risk, enables audit trail |
| New service for reconciliation | Extend existing db-writer | Phase 31 design decision | No new containers, shared connections, simpler deployment |
| DEAL_ENTRY_ALL iteration | Filter DEAL_ENTRY_OUT only | MQL5 best practice | Only exit deals represent closed trades — entry deals are covered by ORDER_OPENED events |

**Deprecated/outdated:**
- **Using `PositionsTotal()` + `PositionSelectByTicket()` for closed trades:** Positions don't exist after close. Must use `HistorySelect()` + `HistoryDealSelect()`. [VERIFIED: MQL5 docs]
- **DEAL_TIME (seconds):** Use `DEAL_TIME_MSC` (milliseconds) for consistent timestamp handling with existing DB writer code. [VERIFIED: MQL5 ENUM_DEAL_PROPERTY_INTEGER]
- **Manual JSON building in EA:** The existing `ParseJSON*` functions + `StringFormat` pattern works. Don't add a JSON library to MQL5. [VERIFIED: AureusProvider.mq5 lines 530-567]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Redis `xpending(start, end, count)` return format is `list[dict]` with keys `message_id`, `consumer`, `time_since_delivered`, `times_delivered` in redis-py 7.2.0 | XPENDING Recovery Pattern | Medium — if format differs, XPENDING check code needs adjustment |
| A2 | Gateway forwards EA TCP responses to Redis streams (pub/sub path exists for responses) | Pitfall 6: EA TCP Response Routing | High — if no response path exists, reconciliation cannot receive MT5 history. Must verify gateway code. |
| A3 | MT5 `DEAL_ENTRY_OUT` deal always has `DEAL_POSITION_ID` linking to the original position | Pitfall 2: Open Price Recovery | Medium — if DEAL_POSITION_ID is 0 for some closes, open price recovery fails |
| A4 | `HistoryDealGetTicket(i)` is the correct function to get deal ticket by index in MQL5 | MQL5 Trade History Pattern | Low — this is standard MQL5 API, well-documented |

## Open Questions

1. **How does the gateway route EA TCP responses back to Redis?**
   - What we know: EA sends JSON via TCP socket to gateway. Gateway receives via `AureusSocket.Receive()`. Gateway publishes market data to Redis streams.
   - What's unclear: Does gateway also publish order events (ORDER_OPENED, ORDER_CLOSED) from EA TCP responses to Redis streams? If so, which stream?
   - Recommendation: Audit gateway code for order event handling. If no path exists, add gateway handler to publish EA order events to `aureus:stream:{server}:orders`.

2. **How to uniquely identify MT5 deals for `trace_id`?**
   - What we know: Real-time trades use `trace_id` from order command (`cmd_id`). MT5 history deals have `ticket` and `DEAL_TIME_MSC` but no `cmd_id`.
   - What's unclear: Should reconciled trades use `trace_id = f"reconciled-{ticket}-{time_ms}"` or match against existing `ticket` column?
   - Recommendation: Use synthetic `trace_id` for reconciled trades (as shown in code examples). The `ON CONFLICT (trace_id) DO NOTHING` handles dedup. For matching real-time vs reconciled, query by `ticket` column.

3. **Should reconciliation query all magic numbers or filter by strategy?**
   - What we know: `aureus_strategy_templates` has `magic_number` column (Phase 26). Strategies have static magic numbers.
   - What's unclear: Should reconciliation poll all magic numbers or only known strategy magic numbers?
   - Recommendation: Start with all magic numbers (null filter). Future optimization: filter by known strategy magic numbers from `aureus_strategy_templates`.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Redis | XPENDING check, stream consumption | ✓ (docker: redis:alpine) | Alpine (6.x or 7.x) | XPENDING is Redis 5.0+ — alpine image supports it |
| PostgreSQL/TimescaleDB | Trade record queries, reconciled inserts | ✓ (docker: timescale/timescaledb:latest-pg15) | PG 15 + TimescaleDB | — |
| MT5 Terminal + EA | Trade history queries via TCP | ✗ (external to Docker) | MT5 build 3xxx+ | If EA not running, reconciliation logs warning, no MT5 data |
| aureus-gateway | TCP ↔ Redis bridge for EA commands | ✓ (docker: services/aureus-gateway) | Python TCP server | — |
| Python 3.11 | DB worker runtime | ✓ (docker: python:3.11-slim) | 3.11 | — |

**Missing dependencies with no fallback:**
- MT5 Terminal with AureusProvider EA running — reconciliation's Tier 2 (MT5 history poll) requires EA to be connected. If EA is offline, only Tier 1 (XPENDING) works. This is acceptable — XPENDING covers stream gaps, MT5 history covers terminal gaps.

**Missing dependencies with fallback:**
- None identified.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (version TBD — not yet in requirements.txt) |
| Config file | none — see Wave 0 |
| Quick run command | `pytest tests/test_reconciliation.py -x -q` |
| Full suite command | `pytest tests/ -x -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TRADE-03 | XPENDING recovery on startup | unit | `pytest tests/test_xpending.py -x` | ❌ Wave 0 |
| TRADE-03 | Real-time order events persist to DB | integration | `pytest tests/test_order_persistence.py -x` | ❌ Wave 0 |
| TRADE-04 | Configurable poll interval validation | unit | `pytest tests/test_reconciliation.py::test_poll_interval -x` | ❌ Wave 0 |
| TRADE-04 | MT5 history comparison detects missing trades | unit (mock) | `pytest tests/test_reconciliation.py::test_missing_trade_detection -x` | ❌ Wave 0 |
| TRADE-04 | RECONCILED status insert with conflict handling | unit | `pytest tests/test_reconciliation.py::test_reconciled_insert -x` | ❌ Wave 0 |
| TRADE-04 | Discrepancy logging format | unit | `pytest tests/test_reconciliation.py::test_discrepancy_log -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_reconciliation.py -x -q`
- **Per wave merge:** `pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_reconciliation.py` — covers TRADE-03, TRADE-04 reconciliation logic
- [ ] `tests/test_xpending.py` — covers XPENDING recovery on startup
- [ ] `tests/conftest.py` — shared fixtures for Redis mock, Postgres mock
- [ ] Framework install: `pip install pytest pytest-asyncio` — not in current requirements.txt
- [ ] `tests/test_mt5_history_parser.py` — covers EA TRADE_HISTORY JSON parsing

## Security Domain

> Security enforcement is not explicitly disabled, so this section is included.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Internal Docker network, no external auth |
| V3 Session Management | no | No user sessions in this service |
| V4 Access Control | no | Service-to-service only |
| V5 Input Validation | yes | Validate EA response fields before DB insert — never trust external data |
| V6 Cryptography | no | No encryption at rest needed for trade data |

### Known Threat Patterns for {stack}

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| EA response injection (malicious JSON via TCP) | Tampering | Validate all fields from TRADE_HISTORY response before DB insert — type check, range check, null handling |
| Reconciliation loop DoS (EA returns millions of deals) | Denial of Service | Limit `HistorySelect` range to 5 minutes, cap total deals processed per run |
| Duplicate trade insertion | Repudiation | `ON CONFLICT (trace_id) DO NOTHING` + synthetic `trace_id` for reconciled trades |
| Timestamp manipulation | Tampering | Use `DEAL_TIME_MSC` (server-side) not local EA time. Validate timestamps are within expected range. |

## Sources

### Primary (HIGH confidence)
- **Codebase: `services/aureus-db-writer/main.py`** — Verified DB writer architecture, order buffer processing, stream consumer loop, timestamp parsing
- **Codebase: `services/aureus-db-writer/schema.sql`** — Verified `aureus_trades` table schema, UNIQUE(trace_id), status TEXT column
- **Codebase: `services/aureus-db-writer/state_machine.py`** — Verified trade state transitions, terminal states
- **Codebase: `mql5/AureusProvider.mq5`** — Verified EA command handling, order event pushing, JSON parsing, dedup, OnTradeTransaction handler
- **Codebase: `services/aureus-db-writer/requirements.txt`** — Verified redis==7.2.0, asyncpg==0.31.0
- **Codebase: `services/aureus-db-writer/Dockerfile`** — Verified python:3.11-slim base
- **Codebase: `docker-compose.dev.yml`** — Verified service topology, env vars
- **Redis docs (redis.readthedocs.io)** — Verified `xpending`, `xrange`, `xclaim`, `xautoclaim` API signatures and return formats for redis-py
- **MQL5 docs (mql5.com/en/docs)** — Verified HistorySelect, HistoryDealsTotal, HistoryDealGetTicket, DEAL_ENTRY, DEAL_TYPE, ENUM_DEAL_PROPERTY_* constants

### Secondary (MEDIUM confidence)
- **CONTEXT.md decisions** — Locked design decisions for hybrid sync, DB writer extension, configurable poll, RECONCILED status
- **Gap detector pattern** (`services/aureus-signal/engine/gap_detector.py`) — Referenced as pattern for gap detection logic, but not directly reused (works on candles, not trades)

### Tertiary (LOW confidence)
- **Gateway response routing** — Assumption A2: Gateway publishes EA order events to Redis streams. Not verified in gateway source code.

## Metadata

**Confidence breakdown:**
- Standard stack: **HIGH** — All versions verified from requirements.txt, pip show, and official docs
- Architecture: **HIGH** — Based on verified codebase analysis (main.py, AureusProvider.mq5, schema.sql, state_machine.py)
- Pitfalls: **MEDIUM** — Most pitfalls verified against code, but gateway response routing (Pitfall 6) needs verification

**Research date:** 2026-04-07
**Valid until:** 2026-05-07 (30 days — stable technologies: Redis, MQL5, asyncpg)
