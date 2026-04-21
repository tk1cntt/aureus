# Phase 28+29 — Integration Test Report

**Date:** 2026-04-06
**Test Type:** End-to-End Integration (Redis → Trader → Gateway → MT5 EA → Order Execution)

---

## Pipeline Tested

```
STRATEGY_MATCH event (Redis pub/sub)
    ↓
aureus-trader (Phase 29)
    - Subscribe aureus:signals:XAUUSD
    - Validate STRATEGY_MATCH event
    - Build OPEN_ORDER command
    - Check idempotency (dedup)
    - Queue order in Redis List
    - Publish to aureus:mt5:commands
    ↓
aureus-gateway
    - Subscribe aureus:mt5:commands
    - Forward command to MT5 EA via TCP
    ↓
AureusProvider.mq5 (Phase 28)
    - Parse OPEN_ORDER JSON
    - Validate order params
    - Execute OrderSend()
    - Push ACK/NACK + ORDER_OPENED via TCP
    ↓
aureus-gateway
    - Receive ACK from EA
    - Publish to aureus:mt5:events
    ↓
aureus-trader
    - Receive ORDER_OPENED event
    - Mark order as executed
```

---

## Test Results

### Test 1: Field Name Compatibility ✅
**Issue:** Phase 26 strategy contract dùng field names khác với Phase 29 validator

| Field | Phase 26 | Phase 29 (original) | Phase 29 (fixed) |
|-------|----------|---------------------|------------------|
| Direction | `side` | `direction` | ✅ Accept both |
| Stop Loss | `sl` | `sl_absolute` | ✅ Accept both |
| Take Profit | `tp` | `tp_absolute` | ✅ Accept both |
| Size Mode | `FIXED_UNITS` | `FIXED_LOT` | ✅ Accept both |

**Fix:** Updated `validator.py` and `order_builder.py` to accept both naming conventions.

### Test 2: Idempotency Key Generation ✅
**Issue:** `generate_cmd_id()` đọc `t` từ `data` dict nhưng `t` nằm ở root event

**Before:**
```python
signal_ts = data.get("signal_ts", data.get("t", ""))  # data["t"] = None!
```

**After:**
```python
signal_ts = event.get("t", data.get("signal_ts", ""))  # ✅ reads root level
```

**Result:** Each unique `t` generates unique `cmd_id`, preventing false duplicates.

### Test 3: Full Pipeline Execution ✅

**Test Event:**
```json
{
  "type": "STRATEGY_MATCH",
  "symbol": "XAUUSD",
  "t": 1712359200,
  "data": {
    "strategy": "CHOCH_UP",
    "strategy_id": 10,
    "side": "BUY",
    "entry_type": "MARKET",
    "size_value": 0.01,
    "size_mode": "FIXED_UNITS",
    "magic_number": 10000,
    "sl": 4670.0,
    "tp": 4690.0,
    "reason_code": "OK"
  }
}
```

**Logs:**
```
12:45:50 [INFO] Order queued: ord-c92d6765fa64 XAUUSD BUY
12:45:57 [INFO] Order executed: ord-c92d6765fa64 ticket=1575234201
```

**Gateway Logs:**
```
12:45:50 [INFO] [XAUUSD] [run_command_subscriber] 2... Forwarded command to EA for XAUUSD
```

**Result:** ✅ Order executed with ticket `1575234201`

---

## Integration Test Checklist

| Component | Test | Status |
|-----------|------|--------|
| aureus-trader | Subscribes to `aureus:signals:{symbol}` | ✅ |
| aureus-trader | Validates STRATEGY_MATCH with Phase 26 fields | ✅ |
| aureus-trader | Generates unique cmd_id per event | ✅ |
| aureus-trader | Detects duplicate orders | ✅ |
| aureus-trader | Publishes to `aureus:mt5:commands` | ✅ |
| aureus-gateway | Forwards command to MT5 EA | ✅ |
| AureusProvider.mq5 | Parses OPEN_ORDER JSON | ✅ |
| AureusProvider.mq5 | Executes OrderSend() | ✅ |
| AureusProvider.mq5 | Validates SL/TP levels | ✅ |
| aureus-trader | Receives ORDER_OPENED event | ✅ |

---

## Known Issues Resolved

1. ✅ **Field name mismatch** — Fixed with dual-name acceptance
2. ✅ **cmd_id collision** — Fixed by reading `t` from root event
3. ✅ **INVALID_STOPS rejection** — Fixed by using realistic SL/TP values

---

## Lessons Learned

### SL/TP Values Must Be Realistic
- XAUUSD current price: ~4680
- SL=2650, TP=2680 → INVALID_STOPS (too far from current price)
- SL=4670, TP=4690 → ✅ Accepted (~10 points from current)

**Rule:** SL/TP must be within reasonable distance of current market price (SYMBOL_TRADE_STOPS_LEVEL).

### Event Structure Matters
- `t`, `symbol`, `type` ở root level
- Strategy-specific data trong `data` dict
- `generate_cmd_id()` cần access cả root và `data`

---

## Next Steps

1. ✅ Pipeline hoàn chỉnh đã hoạt động
2. 🔄 Phase 30 (Trade State Management) — lưu trade records vào DB
3. 🔄 Phase 31 (MT5 History Sync) — reconcile trades từ MT5
4. 🔄 Phase 32 (Trade Performance API) — tính toán metrics

---

*Integration test completed: 2026-04-06*
*All 10 checks passed*
*Pipeline: Redis → Trader → Gateway → MT5 EA → Order executed ✅*
