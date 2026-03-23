# Step 3: Update integrity_and_recalc_task — Snapshot Awareness

> **Phase**: D — Recovery Enhancement  
> **Thời gian**: ~20 phút | **Risk**: Thấp  
> **Input**: `find_snapshot_gaps()` từ Step 2  
> **Output**: Background task kiểm tra cả candle gaps lẫn snapshot gaps

---

## Mô tả

Mở rộng `integrity_and_recalc_task()` để sau khi candle gaps cleared, cũng kiểm tra snapshot gaps. Nếu có snapshot gaps → trigger recalc.

## Thay đổi logic

```python
# HIỆN TẠI:
if gaps:
    # Request backfill
else:
    if not recalc_triggered:
        await recalculate_all_signals(...)
        recalc_triggered = True

# SAU SỬA:
if gaps:
    # Request backfill for candles
    recalc_triggered = False
else:
    # Check snapshot gaps too
    snapshot_gaps = await detector.find_snapshot_gaps(symbol)
    if snapshot_gaps or not recalc_triggered:
        logger.info(f"[Integrity] Snapshot gaps: {len(snapshot_gaps)}. Triggering recalc...")
        await recalculate_all_signals(...)
        recalc_triggered = True
```

## Checklist

- [ ] Import `find_snapshot_gaps` 
- [ ] Call `find_snapshot_gaps()` khi candle gaps cleared
- [ ] Trigger recalc khi có snapshot gaps
- [ ] Log snapshot gap count
- [ ] Không trigger recalc liên tục (only once until new gaps appear)

## Điều kiện nghiệm thu

| # | Điều kiện | Pass? |
|:---|:---|:---|
| 1 | Khi có snapshot gaps → recalc triggered | [ ] |
| 2 | Sau recalc → snapshot gaps cleared | [ ] |
| 3 | Không recalc liên tục (chỉ 1 lần) | [ ] |
| 4 | Log hiển thị snapshot gap count | [ ] |

## Test

```bash
# 1. Delete some snapshots
docker exec aureus_timescaledb psql -U aureus -d aureus -c "
DELETE FROM aureus_signal_snapshots 
WHERE symbol='XAUUSD' AND time IN (
    SELECT time FROM aureus_signal_snapshots 
    WHERE symbol='XAUUSD' ORDER BY time DESC LIMIT 5
)
"

# 2. Wait for integrity task to detect
docker logs -f aureus_signal_engine --since 1m
# Expect: "[Integrity] Snapshot gaps: X. Triggering recalc..."

# 3. Verify gaps filled
docker exec aureus_timescaledb psql -U aureus -d aureus -c "
SELECT count(*) FROM aureus_signal_snapshots 
WHERE symbol='XAUUSD' AND time > NOW() - INTERVAL '30 minutes'
"
```
