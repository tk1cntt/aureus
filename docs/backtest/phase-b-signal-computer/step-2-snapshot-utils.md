# Step 2: Create Shared Snapshot Utilities

> **Phase**: B — Signal Computer  
> **Thời gian**: ~30 phút | **Risk**: Thấp  
> **Input**: Schema design từ Phase A  
> **Output**: `services/aureus-signal/engine/snapshot_utils.py`

---

## Mô tả

Tạo 2 utility functions mà cả live engine, signal_computer, và recovery đều dùng chung:
1. `build_snapshot()` — Collect state values → dict cho DB insertion
2. `batch_insert_snapshots()` — Batch INSERT vào `aureus_signal_snapshots`

## Checklist

- [ ] Tạo file `snapshot_utils.py`
- [ ] `build_snapshot(state, candle) -> Dict`
  - [ ] Collect: atr, ema_21..ema_200, vol_sma_20
  - [ ] Collect: htf_trend, market_regime, session
  - [ ] Collect: transient_signals → events JSONB
  - [ ] Collect: active OBs (non-mitigated, limit 10) → active_obs JSONB
  - [ ] Detect swing_label nếu có pivot mới tại nến này
  - [ ] Return flat dict với timestamp + symbol
- [ ] `batch_insert_snapshots(db_pool, symbol, snapshots: List[Dict])`
  - [ ] Dùng `executemany` hoặc `COPY` cho performance
  - [ ] `ON CONFLICT (time, symbol) DO UPDATE SET ...`
  - [ ] Handle empty list gracefully
  - [ ] Error logging (không raise)

## Điều kiện nghiệm thu

| # | Điều kiện | Pass? |
|:---|:---|:---|
| 1 | `build_snapshot()` trả về dict có ≥ 15 keys | [ ] |
| 2 | JSONB fields (events, active_obs) serializable | [ ] |
| 3 | `batch_insert_snapshots()` insert 100 rows thành công | [ ] |
| 4 | Duplicate insert (ON CONFLICT) update giá trị mới | [ ] |
| 5 | Empty list input không crash | [ ] |

## Test

```python
# Unit test build_snapshot
from engine.snapshot_utils import build_snapshot
from engine.state import SymbolState

state = SymbolState("TEST")
state.atr = 5.5
state.emas = {21: {"current": 2850.0}, 200: {"current": 2800.0}}
state.htf_trend = "BULLISH"
state.market_regime = "TREND_UP"
state.current_session = "LONDON"
state.transient_signals = {"choch_up": {"tag": "choch_up", "pivot_price": 2849.0}}
state.obs = [{"ob_type": "BULLISH", "top": 2851, "bottom": 2849, "mitigated": False}]

candle = {"t": "1718444400", "symbol": "TEST"}
snapshot = build_snapshot(state, candle)
print(f"Keys: {len(snapshot)}")
print(f"atr: {snapshot['atr']}")
print(f"events: {snapshot['events']}")
print(f"active_obs: {snapshot['active_obs']}")
assert snapshot["atr"] == 5.5
assert "choch_up" in str(snapshot["events"])
print("✅ build_snapshot OK")
```

```bash
# Integration test: batch insert
cd services/aureus-signal
python -c "
import asyncio
from engine.snapshot_utils import batch_insert_snapshots
# ... connect to DB, insert 10 test rows, verify, cleanup
"
```
