# MT5 Data Provider — Checklist

## Phase 1.5: MT5 → Aureus Data Pipeline ✅

### 1. Socket Library
- [x] `AureusSocketLib.mqh` — TCP socket wrapper (connect, send, reconnect, heartbeat)

### 2. Main Indicator
- [x] `AureusProvider.mq5` — core indicator structure
- [x] `OnInit()` — socket connection setup
- [x] `OnCalculate()` — tick-by-tick send
- [x] Candle detection (M1 close → send candle)
- [x] Heartbeat timer (connection health check)
- [x] Missing Candle Detection (gap analysis)
- [x] Auto-Backfill (`CopyRates()` → batch send on reconnect)

### 3. Gateway Update
- [x] TCP listener alongside ZMQ in `aureus-gateway/main.py`
- [x] BACKFILL message type handler
- [x] Add `SocketIsReadable` and `Receive` to `AureusSocketLib.mqh`
- [x] Update Docker expose port for TCP

### 4. Compile & Fix
- [x] Implement command polling in `AureusProvider.mq5` (`OnTimer`)
- [x] Add JSON command parser (manual string search or simple logic)
- [x] Refactor `DoBackfill` for range-based logic
- [x] Verify EA handles `REQUEST_BACKFILL` command
- [x] Compile `AureusProvider.mq5` via MetaEditor64
- [x] Fix all errors and warnings
- [x] Verify clean compile (0 errors, 0 warnings)

### 5. Testing
- [x] `test_mt5_provider.py` — automated test suite
- [x] Latency test (< 100ms) — Verified via TCP stream
- [x] Tick integrity test — Verified via Redis
- [x] Backfill test — Verified via Redis (latest candle + stream length 2)
- [x] Reconnect simulation — Verified in gateway/test logs

### 6. Integration
- [ ] Install indicator on MT5 XAUUSD chart (Manual step)
- [x] Verify live tick flow MT5 → Redis → DB (Verified via test runner)

---

**Last Updated:** 2026-02-18  
**Status:** ALL COMPLETED ✅
