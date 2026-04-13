# Intel: Signals Triggering on Service Restart

**Created:** 2026-04-13
**Issue:** Khi restart `aureus-signal-dev`, signals và strategies được trigger ngay lập tức — stale data từ quá khứ được xử lý như real-time events.

---

## Root Causes

### RC1: `strategy_progress` restored from snapshot (Primary)
- **File:** `engine/state_snapshot.py` lines 286-291
- **Mechanism:** Snapshot lưu mid-sequence state → restore → delta candles complete sequence → strategy triggers
- **Impact:** Strategy alert từ historical data, không phải real-time

### RC2: `evaluate_all` called without `backfill_status` context
- **File:** `engine/live_engine.py` line 474
- **Mechanism:** Startup calls `evaluate_all(df, signals, state)` — no context dict → `backfill_status` defaults to `"READY"` → strategy evaluates as if live
- **Impact:** Strategies fire during WARMING phase

### RC3: `transient_signals` not cleared after delta loop
- **File:** `engine/live_engine.py` line 404 (end of loop, no clear)
- **Mechanism:** Last delta candle emits signal → persists in state → serialized to Redis → may trigger notification
- **Impact:** Stale transient_signals survive into live phase

### RC4: `cisd_tracker` not serialized (inconsistent state)
- **File:** `engine/state.py` — `to_dict()` does not include `cisd_tracker`
- **Mechanism:** CISD tracker lost on restart but other signal states (obs, fvgs) are restored → inconsistent signal landscape
- **Impact:** CISD may fire false signals while OB/FVG have restored state

---

## Solution Architecture Decision

### Proposed: B + C + Backfill Flag

| Component | Action | File | Risk |
|-----------|--------|------|------|
| **B (Primary)** | Pass `backfill_status: "WARMING"` to `evaluate_all` during startup, re-evaluate after READY | `live_engine.py:474` | Low |
| **C (Safety)** | Clear `transient_signals` after delta loop completes | `live_engine.py:404` | Zero |
| **D (Defense)** | Set `state._backfill_mode = True` during delta loop; signal calculators check flag before emitting | `live_engine.py:375`, signal `calculate()` methods | Low |

### Rejected:
- **A (Clear strategy_progress):** Loses mid-sequence context, waste of partial matches
- **Full skip delta signal processing:** Delta candles need state building (OB zones, FVG detection), only emission needs suppression

### Trade-offs Accepted:
- Mid-sequence sequences may become "zombie" if market moved past — acceptable, will be cleaned by natural expiry (max_length timeout)
- Slightly more complex signal calculator interface (need to check backfill flag) — minimal overhead

---

## Known Risks (Post-Implementation)

1. **Other eval paths may bypass gate** — integrity check, recalc task could call strategy evaluation without checking backfill_status
2. **No idempotency for signal emission** — same signal could emit on multiple restarts over same delta window
3. **State serialization inconsistency** — not all signal trackers are in `to_dict()` (cisd_tracker missing)

---

## Verification Checklist

After implementation, verify:
- [ ] Restart service → no signals/strategies trigger during warmup
- [ ] First real-time candle after warmup → signals work normally
- [ ] Redis state after startup → no stale transient_signals
- [ ] Strategy mid-sequence before restart → restored but not fired until real-time match
- [ ] CISD tracker state consistent with other signals after restart
- [ ] Telegram notifications → no false alerts on restart
