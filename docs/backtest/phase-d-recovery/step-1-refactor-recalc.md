# Step 1: Refactor recalculate_all_signals() — Per-candle

> **Phase**: D — Recovery Enhancement  
> **Thời gian**: ~45 phút | **Risk**: Trung bình (sửa critical function)  
> **Input**: `recalculate_all_signals()` trong `main.py` dòng 576-622  
> **Output**: Function chạy signals per-candle + ghi snapshots

---

## Mô tả

Thay đổi lớn nhất trong Phase D: thay vì chạy signals 1 lần cuối, chạy cho TỪNG nến. Ghi signal snapshot cho mỗi nến qua `build_snapshot()` + `batch_insert_snapshots()`.

## Trạng thái hiện tại (BUG)

```python
# HIỆN TẠI: Replay 2000 nến nhưng chỉ chạy signals nến cuối
for row in reversed(rows):
    window_manager.update(symbol, candle_data)  # ← Mỗi nến
# ...
df = window_manager.get_df(symbol)
for tag, signal_calc in signals.items():
    res = signal_calc.calculate(df, state, ...)  # ← CHỈ 1 LẦN
```

## Thay đổi cần làm

```python
# SAU SỬA: Chạy signals PER-CANDLE
for row in reversed(rows):
    df, state = window_manager.update(symbol, candle_data)
    state.transient_signals = {}  # Clear trước mỗi nến
    
    if df is not None and len(df) >= 5:
        for tag, signal_calc in signals.items():
            res = signal_calc.calculate(df, state, ...)  # ← MỖI NẾN
            if res:
                state.log_signal(...)
        
        snapshot_batch.append(build_snapshot(state, candle_data))
        if len(snapshot_batch) >= 500:
            await batch_insert_snapshots(db_pool, symbol, snapshot_batch)
            snapshot_batch = []
```

## Checklist

- [ ] Move signal calculation INSIDE per-candle loop
- [ ] Clear `transient_signals` trước mỗi nến
- [ ] Guard: `len(df) >= 5` trước khi chạy signals
- [ ] `build_snapshot()` per-candle
- [ ] Batch insert mỗi 500 rows
- [ ] Final batch insert sau loop
- [ ] Strategy evaluation chỉ chạy 1 lần trên state cuối
- [ ] Redis state update sau cùng
- [ ] Log tổng thời gian recalc

## Điều kiện nghiệm thu

| # | Điều kiện | Pass? |
|:---|:---|:---|
| 1 | Recalc 2000 nến hoàn thành < 30 giây | [ ] |
| 2 | snapshots được ghi cho ≥ 1990 nến (trừ warmup) | [ ] |
| 3 | `signal_history` có events (không trống) | [ ] |
| 4 | Redis state vẫn đúng sau recalc | [ ] |
| 5 | Live signal processing tiếp tục bình thường | [ ] |

## Test

```bash
# 1. Trigger recalc manually (restart signal engine)
docker compose -f aureus-foundation.yml restart aureus-signal

# 2. Watch logs
docker logs -f aureus_signal_engine --since 1m
# Expect: "[Recalc] Starting..." → "[Recalc] Complete (2000 bars, snapshots written)"

# 3. Check snapshots in DB
docker exec aureus_timescaledb psql -U aureus -d aureus -c "
SELECT count(*), min(time), max(time) 
FROM aureus_signal_snapshots 
WHERE symbol='XAUUSD' AND time > NOW() - INTERVAL '48 hours'
"
# Expect: ~1990+ rows

# 4. Verify signal_history populated
curl http://localhost:8001/api/v1/state/XAUUSD | python -c "
import json, sys
d = json.load(sys.stdin)
print(f'signal_history: {len(d.get(\"signal_history\", []))} entries')
"
```

## Rollback

Revert `recalculate_all_signals()` về phiên bản cũ. Signal snapshots từ live (Phase C) vẫn tiếp tục ghi.
