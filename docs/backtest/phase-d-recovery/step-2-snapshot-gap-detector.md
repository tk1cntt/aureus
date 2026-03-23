# Step 2: Thêm find_snapshot_gaps() vào GapDetector

> **Phase**: D — Recovery Enhancement  
> **Thời gian**: ~20 phút | **Risk**: Thấp  
> **Input**: `gap_detector.py`  
> **Output**: Method mới `find_snapshot_gaps()`

---

## Mô tả

Thêm method detect nến có candle trong DB nhưng thiếu signal snapshot. Dùng LEFT JOIN giữa `aureus_candles` và `aureus_signal_snapshots`.

## Checklist

- [ ] Method `find_snapshot_gaps(symbol, lookback_hours=24)`
- [ ] Query: LEFT JOIN candles vs snapshots, WHERE snapshot IS NULL
- [ ] Exclude weekends (giống `find_gaps()`)
- [ ] Return format giống `find_gaps()`: list of {start, end, count}
- [ ] Group consecutive missing snapshots thành ranges

## Điều kiện nghiệm thu

| # | Điều kiện | Pass? |
|:---|:---|:---|
| 1 | Method tồn tại và callable | [ ] |
| 2 | Detect đúng khi xóa 10 snapshots | [ ] |
| 3 | Return empty list khi không có gaps | [ ] |
| 4 | Exclude weekends đúng | [ ] |

## Test

```sql
-- Setup: Delete 10 snapshots to create gap
DELETE FROM aureus_signal_snapshots 
WHERE symbol='XAUUSD' 
AND time IN (
    SELECT time FROM aureus_signal_snapshots 
    WHERE symbol='XAUUSD' 
    ORDER BY time DESC LIMIT 10
);
```

```python
# Call find_snapshot_gaps
from engine.gap_detector import GapDetector
detector = GapDetector(db_pool)
gaps = await detector.find_snapshot_gaps("XAUUSD")
print(f"Found {len(gaps)} gap ranges")
# Expect: ≥ 1 gap range containing ~10 minutes
```

## Rollback

Remove method. Không ảnh hưởng gì.
