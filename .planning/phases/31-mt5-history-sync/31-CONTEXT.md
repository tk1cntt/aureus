# Phase 31 — MT5 History Sync

## CONTEXT

**Phase:** 31
**Requirements:** TRADE-03, TRADE-04
**Goal:** Hybrid sync: push events real-time + poll reconciliation fallback.

---

## Decisions

### D1: Hybrid Sync — Redis Streams Primary, MT5 History Fallback

**Decision:** Reconciliation uses **2-tier approach**:
1. **Tier 1 (Fast):** Check Redis streams for unacked/pending messages (`XPENDING`)
2. **Tier 2 (Fallback):** Poll MT5 order history via EA `REQUEST_BACKFILL` commands
3. **Merge:** Compare both sources against DB `aureus_trades`, insert missing records

**Reconciliation flow:**
```
Every 30s:
  1. Query DB: SELECT ticket, symbol, magic_number, status FROM aureus_trades WHERE closed_at > NOW() - INTERVAL '5 min'
  2. Query MT5: via EA command REQUEST_TRADE_HISTORY (new command type)
  3. Compare: DB tickets vs MT5 tickets
  4. If missing in DB:
     - Check Redis stream first (fast replay)
     - If Redis missing → auto-insert from MT5 history with status='RECONCILED'
  5. Log discrepancies to reconciliation log
```

**Rationale:**
- TRADE-04: "Poll reconciliation chạy mỗi 30-60s, phát hiện và fill gaps"
- Redis streams là fastest path — replay unacked messages không cần query EA
- MT5 history là ground truth — không mất data dù Redis restart
- Hybrid approach đảm bảo **không bao giờ mất trade data**

**Canonical refs:**
- `services/aureus-db-writer/main.py` — Existing stream consumption, can extend with XPENDING check
- `mql5/AureusProvider.mq5` — Existing backfill command handlers (`REQUEST_BACKFILL`)

---

### D2: Implementation Location — Extend `aureus-db-writer`

**Decision:** Reconciliation logic thêm vào **existing `aureus-db-writer` service** dưới dạng new async task trong `run()` loop.

**Implementation:**
```python
class DBWriter:
    async def run(self):
        # Existing: stream consumer loop
        asyncio.create_task(self.stream_consumer_loop())
        
        # New: reconciliation loop (Phase 31)
        asyncio.create_task(self.reconciliation_loop())
    
    async def reconciliation_loop(self):
        interval = int(os.environ.get('HISTORY_SYNC_INTERVAL_SEC', '30'))
        while True:
            await self.run_reconciliation()
            await asyncio.sleep(interval)
    
    async def run_reconciliation(self):
        # Tier 1: Check XPENDING
        # Tier 2: Query MT5 history
        # Merge + insert missing
        pass
```

**Why not new service:**
- DB writer đã có Redis connection, Postgres pool, schema apply
- Thêm 1 task nhẹ — không cần separate container
- Shared codebase → đơn giản deployment + debugging

**Rationale:**
- TRADE-03: "Push events từ MT5 EA cập nhật trade records real-time" — DB writer đã làm việc này
- TRADE-04: "Poll reconciliation fallback" — extension tự nhiên của existing functionality
- Giảm overhead: không cần thêm service, config, monitoring mới

---

### D3: Configurable Poll Frequency

**Decision:** Poll frequency configurable qua environment variable:

```bash
HISTORY_SYNC_INTERVAL_SEC=30  # Default: 30 seconds
```

**Validation:**
- Minimum: 10s (prevent excessive EA queries)
- Maximum: 300s (5 minutes — đảm bảo gaps phát hiện kịp thời)
- Invalid values → fallback to default 30s

**Runtime:**
```python
interval = max(10, min(300, int(os.environ.get('HISTORY_SYNC_INTERVAL_SEC', '30'))))
```

**Rationale:**
- Different trading volumes cần different frequencies
- High-frequency trading → 10-15s
- Normal trading → 30-60s (default)
- Low-volume testing → 120-300s

---

### D4: Auto-Fix with `RECONCILED` Status

**Decision:** Missing trades được **auto-inserted** với special status và source tracking:

**Status values for reconciled trades:**
```python
RECONCILED = 'RECONCILED'  # Trade found by reconciliation, not real-time
```

**Insert logic:**
```python
if trade_missing_in_db:
    await conn.execute("""
        INSERT INTO aureus_trades (
            trace_id, ticket, symbol, magic_number, direction, entry_type,
            status, entry_price, exit_price, sl, tp, volume,
            commission, swap, profit, filled_at, closed_at, payload
        ) VALUES ($1, $2, $3, $4, $5, $6, 'RECONCILED', ...)
        ON CONFLICT (trace_id) DO NOTHING
    """)
    logger.info(f"Reconciled missing trade: ticket={ticket}, symbol={symbol}, source=mt5_history")
```

**Discrepancy logging:**
```json
{
  "type": "RECONCILIATION_DISCREPANCY",
  "timestamp": "2026-04-06T16:50:00Z",
  "action": "INSERT_MISSING_TRADE",
  "ticket": 123456,
  "symbol": "XAUUSD",
  "source": "mt5_history",
  "details": {
    "magic_number": 10000,
    "direction": "BUY",
    "profit": 150.0,
    "filled_at": "2026-04-06T16:45:00Z",
    "closed_at": "2026-04-06T16:49:30Z"
  }
}
```

**Why not manual review:**
- Missing trades là **data loss** — unacceptable cho trading bot
- Auto-fix đảm bảo DB luôn sync với MT5
- `RECONCILED` status cho phép audit sau: `SELECT * FROM aureus_trades WHERE status = 'RECONCILED'`

**Rationale:**
- TRADE-04: "Không mất trade data dù có disconnect hay EA restart"
- Auto-fix guarantee data integrity
- `RECONCILED` status distinguishes from real-time trades for audit

---

### D5: XPENDING Recovery + MT5 History Fallback

**Decision:** Reconciliation uses **2-phase approach** trên mỗi run:

**Phase 1: XPENDING Recovery (cheap, fast)**
```python
async def check_xpending(self):
    """Check for unacknowledged messages from previous runs."""
    pending = await self.redis.xpending(self.order_stream, CONSUMER_GROUP, '-', '+', 100)
    for msg in pending:
        msg_id = msg['message_id']
        # Fetch message content
        messages = await self.redis.xrange(self.order_stream, msg_id, msg_id, 1)
        if messages:
            _, payload = messages[0]
            # Reprocess message
            await self.process_order_message(payload)
            # ACK after successful processing
            await self.redis.xack(self.order_stream, CONSUMER_GROUP, msg_id)
            logger.info(f"Recovered unacked message: {msg_id}")
```

**Phase 2: MT5 History Poll (thorough, slower)**
```python
async def poll_mt5_history(self):
    """Query MT5 for recent trade history and reconcile with DB."""
    # 1. Get recent trades from DB
    db_trades = await self.get_recent_trades_from_db(minutes=5)
    
    # 2. Request trade history from EA
    history_request = {
        "type": "REQUEST_TRADE_HISTORY",
        "from_time": int((time.time() - 300) * 1000),  # 5 minutes ago
        "to_time": int(time.time() * 1000),
        "magic_number": None  # All magic numbers
    }
    await self.redis.publish('aureus:mt5:commands', json.dumps(history_request))
    
    # 3. Wait for response (with timeout)
    # EA responds with array of trade records
    
    # 4. Compare and insert missing
    for mt5_trade in mt5_trades:
        if mt5_trade['ticket'] not in db_trades:
            await self.insert_reconciled_trade(mt5_trade)
```

**Startup behavior:**
```python
async def run(self):
    await self.connect_redis()
    await self.connect_postgres()
    await self.apply_schema()
    
    # Phase 31: Check XPENDING on startup
    await self.check_xpending()
    
    # Start main loops
    asyncio.create_task(self.stream_consumer_loop())
    asyncio.create_task(self.reconciliation_loop())
```

**Why both phases:**
- XPENDING recovery handles **stream gaps** (consumer crash before ACK)
- MT5 history handles **system gaps** (EA restart, Redis purge, network partition)
- Together = comprehensive coverage, không mất data

**Rationale:**
- TRADE-03: Real-time push events — XPENDING recovery đảm bảo không mất messages
- TRADE-04: Poll reconciliation — MT5 history poll đảm bảo data integrity

---

## New EA Command Type

**REQUEST_TRADE_HISTORY** — Server requests trade history from EA:

```json
{
  "type": "REQUEST_TRADE_HISTORY",
  "from_time": 1712352000000,
  "to_time": 1712355600000,
  "magic_number": null,
  "symbol": null
}
```

**EA Response:**
```json
{
  "type": "TRADE_HISTORY",
  "trades": [
    {
      "ticket": 123456,
      "symbol": "XAUUSD",
      "magic_number": 10000,
      "direction": "BUY",
      "entry_price": 2665.5,
      "exit_price": 2670.0,
      "sl": 2650.0,
      "tp": 2680.0,
      "volume": 0.1,
      "commission": -0.5,
      "swap": 0.0,
      "profit": 45.0,
      "open_time": 1712352000000,
      "close_time": 1712355000000
    }
  ]
}
```

**EA Implementation (MQL5):**
- Handle `REQUEST_TRADE_HISTORY` in `ProcessIncomingCommands()`
- Use `HistorySelect(from_time, to_time)` to get trades in range
- Filter by `magic_number` if specified
- Return as JSON array via TCP

---

## Reusable Assets

### EXISTS (can reuse):
- ✅ DB writer infrastructure: `services/aureus-db-writer/main.py` — stream consumer, DB pool
- ✅ State machine: `services/aureus-db-writer/state_machine.py` — validate trade transitions
- ✅ Schema: `services/aureus-db-writer/schema.sql` — `aureus_trades` table
- ✅ EA backfill commands: `mql5/AureusProvider.mq5` — `REQUEST_BACKFILL` pattern
- ✅ Gap detection: `services/aureus-signal/engine/gap_detector.py` — pattern for gap finding
- ✅ Redis consumer groups: existing `xreadgroup` pattern in DB writer
- ✅ Retry logic: `services/aureus-trader/dispatcher.py` — exponential backoff pattern

### MUST BUILD:
- ❌ `REQUEST_TRADE_HISTORY` command handler in EA
- ❌ `TRADE_HISTORY` response from EA
- ❌ XPENDING check in DB writer startup
- ❌ Reconciliation loop in DB writer
- ❌ MT5 history comparison logic
- ❌ Auto-insert for missing trades with `RECONCILED` status
- ❌ Discrepancy logging

## Carry-forward from prior phases

| Source | Decision | Relevance |
|--------|----------|-----------|
| Phase 26 | `magic_number` per strategy | Filter for reconciliation queries |
| Phase 28 | EA pushes ORDER_OPENED/CLOSED/FAILED | Primary source for trade data |
| Phase 29 | `cmd_id` idempotency key | Maps to `trace_id` in DB |
| Phase 30 | `aureus_trades` table with UNIQUE(trace_id) | Target for reconciliation upserts |
| Phase 30 | State machine validates transitions | Reconciliation inserts bypass validation |

## Requirements Detail

### TRADE-03: Push events từ MT5 EA cập nhật trade records real-time
- [ ] XPENDING recovery on startup (recover unacked messages)
- [ ] Real-time order events from `aureus:stream:*:orders`
- [ ] State transition validation before DB write
- [ ] ON CONFLICT upsert for idempotent writes

### TRADE-04: Poll reconciliation mỗi 30-60s
- [ ] Configurable poll interval via `HISTORY_SYNC_INTERVAL_SEC`
- [ ] REQUEST_TRADE_HISTORY command to EA
- [ ] Compare DB vs MT5 history
- [ ] Auto-insert missing trades with `RECONCILED` status
- [ ] Discrepancy logging for audit trail

## Success Criteria (Updated)

1. ✅ Push events từ MT5 EA cập nhật trade records real-time (existing + XPENDING recovery)
2. ✅ Poll reconciliation chạy mỗi 30s (configurable), phát hiện và fill gaps
3. ✅ Không mất trade data dù có disconnect hay EA restart (XPENDING + MT5 history)
4. ✅ Reconciliation log ghi nhận mọi discrepancy được sửa
5. ✅ Missing trades auto-inserted với `status='RECONCILED'`
6. ✅ Discrepancy log format chuẩn cho audit

---
*Context created: 2026-04-06*
*Ready for planning*
