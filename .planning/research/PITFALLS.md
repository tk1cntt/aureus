# Pitfalls Research: Signal Delivery & Trade Management

## Critical Pitfalls

### 1. MT5 State Drift (HIGH RISK)
**What:** External DB representation of orders becomes desynchronized from actual MT5 terminal state.
**When:** Network disconnect, EA restart, manual trades in MT5, partial fills.
**Prevention:**
- Phase 6 (history sync) MUST implement reconciliation loop
- Use `magic` number to distinguish bot orders from manual trades
- Never trust cached state — always verify via MT5 history on reconnect
- **Phase:** aureus-trader core + history sync

### 2. Duplicate Order Execution (HIGH RISK)
**What:** Same strategy match triggers multiple orders (race condition).
**When:** Signal engine emits duplicate events, Redis consumer restart, slow MT5 response.
**Prevention:**
- Idempotency key per strategy match (hash of symbol + strategy + timestamp)
- Order state machine prevents re-sending if already in `sent` or `filled` state
- Dedup window (e.g., ignore same signal within 60s)
- **Phase:** aureus-trader core

### 3. Telegram Rate Limiting (MEDIUM RISK)
**What:** Telegram API rejects messages with `429 Too Many Requests`.
**When:** High-frequency signals across multiple symbols (>30 msg/s).
**Prevention:**
- Internal message queue with rate limiter (max 25 msg/s with buffer)
- Batch similar signals into single message if within time window
- Exponential backoff on 429 errors
- **Phase:** aureus-notifier

### 4. TCP Connection Drop Between aureus-trader and MT5 EA (HIGH RISK)
**What:** Orders sent but never received by MT5, or MT5 events lost.
**When:** Network instability, MT5 restart, EA reload.
**Prevention:**
- Heartbeat mechanism (already exists in AureusProvider.mq5)
- Order queue with retry on reconnect — don't discard unsent orders
- Acknowledgement protocol: each order command gets ACK/NACK from EA
- Queue persistence: save pending orders to DB before sending
- **Phase:** aureus-trader + AureusProvider.mq5 extension

### 5. Strategy Contract Breaking Change (MEDIUM RISK)
**What:** Adding new fields (entry_type, sl, tp) breaks existing strategy evaluation.
**When:** Code update without backward compatibility.
**Prevention:**
- New fields MUST be optional with sensible defaults
- Existing strategies continue working unchanged
- Version flag in strategy output for migration
- **Phase:** Strategy contract enhancement

### 6. Order Latency (MEDIUM RISK)
**What:** Delay between strategy match and actual MT5 order execution causes price slippage.
**When:** Multiple hops: signal engine → Redis → aureus-trader → TCP → EA → MT5 server.
**Prevention:**
- Minimize message serialization overhead (compact JSON)
- Direct TCP connection (skip gateway for orders — separate port)
- Log latency at each hop for monitoring
- Market order tolerance: accept slippage within configured range
- **Phase:** aureus-trader + monitoring

### 7. History Sync Data Volume (LOW RISK)
**What:** Polling full MT5 history periodically creates excessive load.
**When:** Many trades, frequent poll interval.
**Prevention:**
- Only query new trades since last sync timestamp
- Use `HistorySelect()` with time range, not full history
- Push events handle 99% of cases, poll only catches gaps
- **Phase:** MT5 history sync

## Warning Signs During Development

| Signal | Indicates | Action |
|--------|-----------|--------|
| Orders appearing without matching DB record | State drift | Check reconciliation loop |
| Same order ticket in DB twice | Dedup failure | Add unique constraint on ticket |
| Telegram messages delayed >5s | Rate limiting hit | Check queue depth |
| MT5 EA logs "send failed" | TCP connection issue | Check heartbeat + reconnect |
| Strategy output missing SL/TP | Contract not updated | Verify strategy inherits new contract |
| Dashboard shows stale data | Sync lag | Check poll interval + push events |
