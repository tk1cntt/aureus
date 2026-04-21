# Phase 28: AureusProvider.mq5 Bidirectional Extension — Research

## RESEARCH COMPLETE

**Date:** 2026-04-06
**Phase:** 28 — AureusProvider.mq5 Bidirectional Extension
**Requirements:** ORDER-04, ORDER-05, ORDER-06

---

## 1. Current Architecture Analysis

### AureusProvider.mq5 (647 LOC)
- **Unidirectional:** Sends TICK, CANDLE, BACKFILL messages to gateway
- **Existing receive path:** `ProcessIncomingCommands()` at line 509 — parses `REQUEST_BACKFILL` and `REQUEST_BACKFILL_COUNT` commands from gateway
- **JSON parser:** `ParseJSONString()` at line 493 — extracts string fields only, needs numeric parsers
- **Timer:** 100ms interval handles candle polling + command processing
- **Connection:** Single TCP socket via `AureusSocketLib.mqh`

### AureusSocketLib.mqh (331 LOC)
- `SendJSON(json)` — sends newline-delimited JSON, handles partial sends
- `Receive()` — reads available data from socket, returns string
- `EnsureConnected()` — auto-reconnect with delay
- **Already bidirectional-capable** — no changes needed to socket lib

### aureus-gateway/main.py (338 LOC)
- **`run_command_subscriber()`** (line 282): Already subscribes to Redis `aureus:mt5:commands`, forwards JSON to EA via TCP writer
- **`active_connections[symbol]`**: Tracks TCP writers per symbol for routing
- **`process_message()`** (line 78): Handles TICK/CANDLE/BACKFILL — needs extension for ORDER events
- **Message models:** Pydantic BaseModel validation — needs new ORDER event models

---

## 2. MQL5 OrderSend() API Research

### Market Order
```cpp
MqlTradeRequest request;
MqlTradeResult  result;
ZeroMemory(request);
ZeroMemory(result);

request.action       = TRADE_ACTION_DEAL;
request.symbol       = symbol;
request.volume       = volume;
request.type         = ORDER_TYPE_BUY; // or ORDER_TYPE_SELL
request.price        = SymbolInfoDouble(symbol, SYMBOL_ASK); // or SYMBOL_BID
request.sl           = sl_price;
request.tp           = tp_price;
request.deviation    = max_slippage;
request.magic        = magic_number;
request.type_filling = ORDER_FILLING_IOC;
request.comment      = comment;
```

### Pending Order (LIMIT/STOP)
```cpp
request.action       = TRADE_ACTION_PENDING;
request.type         = ORDER_TYPE_BUY_LIMIT;  // or SELL_LIMIT, BUY_STOP, SELL_STOP
request.price        = entry_price;           // Required trigger price
request.type_filling = ORDER_FILLING_RETURN;  // Standard for pending
request.type_time    = ORDER_TIME_GTC;        // Good Till Cancel
```

### Order Type Mapping
| direction + order_type | MQL5 type |
|------------------------|-----------|
| BUY + MARKET | `ORDER_TYPE_BUY` |
| SELL + MARKET | `ORDER_TYPE_SELL` |
| BUY + LIMIT | `ORDER_TYPE_BUY_LIMIT` |
| SELL + LIMIT | `ORDER_TYPE_SELL_LIMIT` |
| BUY + STOP | `ORDER_TYPE_BUY_STOP` |
| SELL + STOP | `ORDER_TYPE_SELL_STOP` |

### Pre-validation with OrderCheck()
```cpp
MqlTradeCheckResult checkResult;
if(!OrderCheck(request, checkResult)) {
    // checkResult.retcode has the reason
    // checkResult.comment has description
}
```

### Key Return Codes
| retcode | Meaning |
|---------|---------|
| 10009 (`TRADE_RETCODE_DONE`) | Success |
| 10019 (`TRADE_RETCODE_NO_MONEY`) | Insufficient margin |
| 10016 (`TRADE_RETCODE_INVALID_STOPS`) | Invalid SL/TP |
| 10017 (`TRADE_RETCODE_TRADE_DISABLED`) | Trading disabled |
| 10018 (`TRADE_RETCODE_MARKET_CLOSED`) | Market closed |

---

## 3. OnTradeTransaction() for Close Detection

```cpp
void OnTradeTransaction(const MqlTradeTransaction& trans,
                        const MqlTradeRequest& request,
                        const MqlTradeResult& result)
{
    if(trans.type == TRADE_TRANSACTION_DEAL_ADD) {
        if(HistoryDealSelect(trans.deal)) {
            long entry = HistoryDealGetInteger(trans.deal, DEAL_ENTRY);
            if(entry == DEAL_ENTRY_OUT) {
                // Position closed — extract deal properties
                string symbol = HistoryDealGetString(trans.deal, DEAL_SYMBOL);
                long magic = HistoryDealGetInteger(trans.deal, DEAL_MAGIC);
                long ticket = HistoryDealGetInteger(trans.deal, DEAL_POSITION_ID);
                double volume = HistoryDealGetDouble(trans.deal, DEAL_VOLUME);
                double profit = HistoryDealGetDouble(trans.deal, DEAL_PROFIT);
                double commission = HistoryDealGetDouble(trans.deal, DEAL_COMMISSION);
                double swap = HistoryDealGetDouble(trans.deal, DEAL_SWAP);
                double price = HistoryDealGetDouble(trans.deal, DEAL_PRICE);
            }
        }
    }
}
```

**Key considerations:**
- Filter by `DEAL_MAGIC` — only report bot-managed positions
- `DEAL_ENTRY_OUT` fires for both full and partial closes
- `DEAL_POSITION_ID` = the original position ticket (not the deal ticket)
- Can also detect `DEAL_ENTRY_IN` for order opened confirmation (supplementary to OrderSend result)

---

## 4. Gateway Extension Points

### New event types to handle in `process_message()`:
- `ORDER_OPENED` → publish to Redis `aureus:mt5:events`
- `ORDER_CLOSED` → publish to Redis `aureus:mt5:events`
- `ORDER_FAILED` → publish to Redis `aureus:mt5:events`
- `ACK` → publish to Redis `aureus:mt5:events`
- `NACK` → publish to Redis `aureus:mt5:events`

### New Pydantic models needed:
- `OrderOpenedEvent`
- `OrderClosedEvent`
- `OrderFailedEvent`
- `AckEvent`
- `NackEvent`

### Redis channel:
- Commands: `aureus:mt5:commands` (existing)
- Events: `aureus:mt5:events` (new — PUBLISH channel for downstream consumers)

---

## 5. Validation Architecture

### Testability Constraints
- **MQL5 code cannot be unit tested in Python** — it runs inside MetaTrader 5 terminal
- **Gateway Python code can be fully unit tested**
- **Integration test:** Simulate EA TCP client → send order events → verify Redis publish

### Validation Strategy
1. **Gateway unit tests:** Mock TCP client sends ORDER_OPENED/CLOSED/FAILED JSON, verify Pydantic validation and Redis publish
2. **EA compilation test:** Verify `AureusProvider.mq5` compiles without errors in MetaEditor
3. **Manual integration test:** Run EA in MT5 demo account, send OPEN_ORDER via Redis → verify ACK → verify OrderSend execution → verify ORDER_OPENED event

---

*Research completed: 2026-04-06*
