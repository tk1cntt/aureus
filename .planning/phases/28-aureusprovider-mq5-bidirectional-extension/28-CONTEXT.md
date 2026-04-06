# Phase 28: AureusProvider.mq5 Bidirectional Extension - Context

**Gathered:** 2026-04-06
**Status:** Ready for planning

<domain>
## Phase Boundary

Mở rộng MT5 EA (`AureusProvider.mq5`) từ unidirectional (chỉ gửi market data lên gateway) thành bidirectional: nhận order commands từ server, execute OrderSend(), và push order events ngược về server. Scope giới hạn ở tầng EA — server-side order management (aureus-trader) thuộc Phase 29.

</domain>

<decisions>
## Implementation Decisions

### D-01: Order Command Protocol — JSON over existing TCP

**Decision:** Tái sử dụng cùng TCP socket đã có giữa EA↔Gateway. Command format là newline-delimited JSON (consistent với protocol hiện tại). Gateway đã có `run_command_subscriber()` forward từ Redis channel `aureus:mt5:commands`.

**Command schemas:**

```json
// OPEN_ORDER command
{
  "type": "OPEN_ORDER",
  "symbol": "XAUUSD",
  "cmd_id": "ord-20260406-001",
  "direction": "BUY",
  "order_type": "MARKET",
  "volume": 0.1,
  "price": 0.0,
  "sl": 1950.50,
  "tp": 1970.00,
  "magic": 10001,
  "comment": "CHOCH_UP"
}

// CLOSE_ORDER command
{
  "type": "CLOSE_ORDER",
  "symbol": "XAUUSD",
  "cmd_id": "cls-20260406-001",
  "ticket": 12345678,
  "volume": 0.0,
  "magic": 10001
}
```

**Required fields cho OPEN_ORDER:**
- `type` = "OPEN_ORDER"
- `symbol` — trading symbol
- `cmd_id` — unique command ID (idempotency key from server, EA dùng để ACK/NACK)
- `direction` — BUY | SELL
- `order_type` — MARKET | LIMIT | STOP (maps từ Phase 26 `entry_type` enum)
- `volume` — lot size (maps từ Phase 26 `size_value` khi `size_mode=FIXED_LOT`)
- `price` — 0 cho MARKET, giá cụ thể cho LIMIT/STOP
- `sl` — stop loss price (absolute, đã được `orders.py` tính từ sl_mode/sl_value)
- `tp` — take profit price (absolute, đã được `orders.py` tính từ tp_mode/tp_value)
- `magic` — magic number (từ Phase 26 D3, static mapping per strategy)
- `comment` — strategy identifier string

**Required fields cho CLOSE_ORDER:**
- `type` = "CLOSE_ORDER"
- `symbol` — trading symbol
- `cmd_id` — unique command ID
- `ticket` — MT5 order ticket number
- `volume` — 0 = close full, >0 = partial close (defer partial close sang ORDER-F02)
- `magic` — magic number (validate ownership)

**Idempotency:** EA giữ set `processed_cmd_ids[]` (string array, max 500 entries, FIFO cleanup). Nếu nhận `cmd_id` đã xử lý → trả NACK với reason `DUPLICATE`.

**Rationale:**
- Tái sử dụng TCP socket giữ connection footprint tối thiểu (1 socket per EA instance)
- Gateway `run_command_subscriber()` đã forward commands từ Redis pub/sub — chỉ cần EA parse thêm command types
- `cmd_id` ở EA cho de-duplicate tại receiver — idempotency key chính (ORDER-07 Phase 29) ở server-side
- `price=0` cho MARKET orders — convention phổ biến trong MQL5

---

### D-02: OrderSend() Execution — Fail-fast, no retry at EA level

**Decision:** EA thực hiện `OrderSend()` **một lần duy nhất** per command. Không retry tại EA — retry logic thuộc về server-side (Phase 29 aureus-trader).

**Market Order flow:**
1. Nhận OPEN_ORDER với `order_type=MARKET`
2. Fill `MqlTradeRequest` struct:
   - `action = TRADE_ACTION_DEAL`
   - `type = ORDER_TYPE_BUY/SELL`
   - `symbol, volume, sl, tp, magic, comment`
   - `type_filling = ORDER_FILLING_IOC` (Instant or Cancel — phổ biến nhất)
   - `deviation = 20` (max slippage points, configurable via input param)
3. Check `OrderCheck()` trước `OrderSend()` — pre-validate margin/volume
4. Execute `OrderSend()` → parse `MqlTradeResult`
5. Push ORDER_OPENED (nếu `result.retcode == TRADE_RETCODE_DONE`) hoặc ORDER_FAILED

**Pending Order flow (LIMIT/STOP):**
1. Nhận OPEN_ORDER với `order_type=LIMIT` hoặc `STOP`
2. Fill `MqlTradeRequest` struct:
   - `action = TRADE_ACTION_PENDING`
   - `type = ORDER_TYPE_BUY_LIMIT/SELL_LIMIT/BUY_STOP/SELL_STOP` (derived from direction + order_type)
   - `price` — entry price cho pending order
   - `symbol, volume, sl, tp, magic, comment`
3. Execute `OrderSend()` → push ORDER_OPENED (pending placed) hoặc ORDER_FAILED

**Error handling — fail-fast:**
- `TRADE_RETCODE_NO_MONEY` → ORDER_FAILED, reason="INSUFFICIENT_MARGIN"
- `TRADE_RETCODE_INVALID_STOPS` → ORDER_FAILED, reason="INVALID_STOPS"
- `TRADE_RETCODE_TRADE_DISABLED` → ORDER_FAILED, reason="TRADE_DISABLED"
- `TRADE_RETCODE_MARKET_CLOSED` → ORDER_FAILED, reason="MARKET_CLOSED"
- Bất kỳ retcode != DONE → ORDER_FAILED, reason=retcode description

**Trade context busy (`TRADE_RETCODE_SERVER_DISABLES_AT`):** Đây là trường hợp duy nhất EA xử lý bằng cách **queue command** và retry sau 1 timer cycle (100ms). Max 3 retries, sau đó ORDER_FAILED.

**New input parameter:**
```mql5
input int InpMaxSlippage = 20;  // Max slippage for market orders (points)
```

**Rationale:**
- Fail-fast giữ EA đơn giản — EA là execution layer, không phải decision layer
- Server-side (Phase 29) có thể re-send command nếu cần retry (đã có `cmd_id` cho idempotency)
- `OrderCheck()` trước `OrderSend()` tránh unnecessary server requests
- Trade context busy là lỗi tạm thời (MT5 serialized trade requests) — cần short retry
- Slippage configurable vì khác nhau giữa forex (5-10) và crypto (20-50)

---

### D-03: Order Event Responses — Push events qua cùng TCP socket

**Decision:** EA push order events ngược về Gateway qua **cùng TCP socket** đang kết nối. Gateway parse event và publish lên Redis channel `aureus:mt5:events`.

**Event schemas:**

```json
// ORDER_OPENED event
{
  "type": "ORDER_OPENED",
  "cmd_id": "ord-20260406-001",
  "symbol": "XAUUSD",
  "ticket": 12345678,
  "direction": "BUY",
  "order_type": "MARKET",
  "volume": 0.1,
  "open_price": 1960.25,
  "sl": 1950.50,
  "tp": 1970.00,
  "magic": 10001,
  "t": 1712376000000
}

// ORDER_CLOSED event (from OnTradeTransaction)
{
  "type": "ORDER_CLOSED",
  "symbol": "XAUUSD",
  "ticket": 12345678,
  "direction": "BUY",
  "volume": 0.1,
  "open_price": 1960.25,
  "close_price": 1968.50,
  "profit": 82.50,
  "commission": -0.70,
  "swap": 0.00,
  "magic": 10001,
  "t": 1712379600000
}

// ORDER_FAILED event
{
  "type": "ORDER_FAILED",
  "cmd_id": "ord-20260406-001",
  "symbol": "XAUUSD",
  "reason": "INSUFFICIENT_MARGIN",
  "retcode": 10019,
  "t": 1712376000000
}
```

**ORDER_CLOSED detection:**
- Implement `OnTradeTransaction()` callback — MT5 native event khi position closes
- Filter by `magic` number (Phase 26 D3) — chỉ report positions do bot mở
- Include P&L data (`profit`, `commission`, `swap`) cho Phase 30/31 trade state management

**Gateway-side changes:**
- Thêm message type validation cho `ORDER_OPENED`, `ORDER_CLOSED`, `ORDER_FAILED` trong `process_message()`
- Publish events lên Redis channel `aureus:mt5:events` (dùng `PUBLISH`, analogous to `aureus:mt5:commands`)
- **Không cần heartbeat riêng cho orders** — heartbeat hiện tại của socket đã đủ kiểm tra connectivity

**Rationale:**
- Cùng TCP socket = không tăng connection complexity
- Gateway đã có pattern bi-directional (nhận data + gửi commands) — thêm events chỉ là thêm message types
- `OnTradeTransaction()` là preferred MQL5 approach (event-driven, không cần polling)
- Magic number filter đảm bảo chỉ track bot orders, không lẫn manual trades
- Redis channel `aureus:mt5:events` cho Phase 29 (aureus-trader) subscribe

---

### D-04: ACK/NACK Protocol — Immediate synchronous ACK, async result event

**Decision:** **2-phase response pattern:**

1. **Phase 1 — Immediate ACK/NACK** (< 100ms): EA nhận command → validate format + check idempotency → trả ACK hoặc NACK ngay lập tức
2. **Phase 2 — Async result event**: EA execute OrderSend() → push ORDER_OPENED/ORDER_FAILED event (có thể mất 200ms-2s tùy market condition)

**ACK/NACK schemas:**

```json
// ACK — command accepted, will execute
{
  "type": "ACK",
  "cmd_id": "ord-20260406-001",
  "t": 1712376000000
}

// NACK — command rejected, will NOT execute
{
  "type": "NACK",
  "cmd_id": "ord-20260406-001",
  "reason": "DUPLICATE",
  "t": 1712376000000
}
```

**NACK reasons:**
- `DUPLICATE` — cmd_id đã xử lý trước đó
- `INVALID_COMMAND` — thiếu required fields hoặc format sai
- `UNKNOWN_SYMBOL` — symbol không nằm trong EA config
- `TRADE_DISABLED` — EA trading bị tắt (AutoTrading off)

**Flow tổng quát:**
```
Server → Gateway → EA: OPEN_ORDER {cmd_id: "X"}
EA → Gateway → Redis: ACK {cmd_id: "X"}           ← immediate
EA executes OrderSend()...
EA → Gateway → Redis: ORDER_OPENED {cmd_id: "X"}   ← async (200ms-2s later)
```

**Timeout handling (server-side Phase 29):**
- Server expect ACK within 5s → nếu không nhận → assume connection lost
- Server expect ORDER_OPENED/FAILED within 30s after ACK → nếu không → timeout alert
- **EA không quản lý timeout** — chỉ gửi responses, server tracking

**Rationale:**
- 2-phase pattern tách "command received" khỏi "command executed" — server biết ngay EA nhận được command
- ACK/NACK nhanh cho server feedback loop (connection alive + command valid)
- Async result cho phép OrderSend() chạy tự nhiên mà không block socket reading
- NACK reasons cụ thể giúp server debug (DUPLICATE khác INVALID_COMMAND khác TRADE_DISABLED)
- Timeout thuộc server-side — EA giữ stateless (ngoại trừ cmd_id dedup set)

### Agent's Discretion
- **Queue buffer size** cho trade context busy retry — agent decides optimal size (recommend 5-10)
- **Deviation points** default value — 20 points, nhưng agent có thể adjust nếu research cho thấy khác
- **cmd_id dedup array size** — 500 entries, FIFO, agent tùy chỉnh

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### MQL5 EA Source
- `mql5/AureusProvider.mq5` — Current EA (647 LOC), `ProcessIncomingCommands()` function at line 509 is the extension point
- `mql5/AureusSocketLib.mqh` — Socket library with `SendJSON()`, `Receive()`, reconnect logic

### Gateway
- `services/aureus-gateway/main.py` — Gateway server, `run_command_subscriber()` at line 282 forwards Redis commands to EA
- `services/aureus-gateway/main.py` — `process_message()` at line 78 needs extension for ORDER_OPENED/CLOSED/FAILED events

### Prior Phase Contracts
- `.planning/phases/26-signal-event-pipeline-strategy-contract/26-CONTEXT.md` — Phase 26 D1 (entry_type enum), D2 (size_mode/size_value), D3 (magic_number static mapping), D5 (SL/TP contract)
- `.planning/phases/27-telegram-notification-service/27-CONTEXT.md` — Phase 27 pub/sub patterns

### Codebase Maps
- `.planning/codebase/INTEGRATIONS.md` — Redis integration patterns, `aureus:mt5:commands` channel

### MQL5 Reference
- MQL5 `OrderSend()` function: fills `MqlTradeRequest`, returns `MqlTradeResult`
- MQL5 `OnTradeTransaction()` callback: fires on position open/close/modify events
- MQL5 `OrderCheck()`: pre-validate before OrderSend()

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`ProcessIncomingCommands()`** (`AureusProvider.mq5` L509): Already parses JSON commands from socket — extend with OPEN_ORDER/CLOSE_ORDER handling
- **`ParseJSONString()`** (`AureusProvider.mq5` L493): Simple JSON string field parser — extend with `ParseJSONLong()`, `ParseJSONDouble()` for numeric fields
- **`g_socket.SendJSON()`** (`AureusSocketLib.mqh` L185): Send JSON back to gateway — reuse for ACK/NACK/ORDER events
- **`g_socket.Receive()`** (`AureusSocketLib.mqh` L301): Already reads incoming data — no changes needed
- **`run_command_subscriber()`** (`main.py` L282): Gateway forwards Redis `aureus:mt5:commands` → EA — already bi-directional infrastructure

### Established Patterns
- **Message format:** Newline-delimited JSON over TCP (consistent across all message types)
- **Command routing:** Gateway maintains `active_connections[symbol]` writer set — commands route to correct EA
- **Redis pub/sub:** Commands via `PUBLISH aureus:mt5:commands`, events via `PUBLISH aureus:mt5:events` (new)

### Integration Points
- **EA → Gateway:** Extend `process_message()` to handle 3 new event types (ORDER_OPENED, ORDER_CLOSED, ORDER_FAILED)
- **Gateway → Redis:** New `PUBLISH aureus:mt5:events` for downstream consumers (Phase 29 aureus-trader, Phase 30 trade state)
- **EA OnTradeTransaction:** New MQL5 callback for position close detection

</code_context>

<specifics>
## Specific Ideas

- User muốn cả 4 areas dùng "suggest tốt nhất" — agent đã pick approach tốt nhất dựa trên codebase context
- 2-phase ACK/NACK protocol (D-04) critical cho reliability — tách "received" khỏi "executed"
- Fail-fast tại EA (D-02) giữ EA simple — complexity thuộc server-side Phase 29

</specifics>

<deferred>
## Deferred Ideas

- **Partial close support** — ORDER-F02, volume > 0 trong CLOSE_ORDER (future requirement)
- **Order modification** — ORDER-F01, update SL/TP after entry (future requirement)
- **Trailing stop** — không trong requirements, defer to future
- **Multi-EA management** — nếu chạy nhiều EA instances trên nhiều charts, cần routing phức tạp hơn (future)

None — discussion stayed within phase scope

</deferred>

---

*Phase: 28-aureusprovider-mq5-bidirectional-extension*
*Context gathered: 2026-04-06*
