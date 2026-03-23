# Step 4: Rebuild, Deploy & Monitor

> **Phase**: C — Live System Alignment  
> **Thời gian**: ~15 phút | **Risk**: Thấp  
> **Input**: All changes from Steps 1-3  
> **Output**: Live system chạy ổn định + ghi snapshots

---

## Mô tả

Rebuild Docker image, restart, monitor 10 phút để xác nhận mọi thứ ổn định.

## Checklist

- [ ] Docker image rebuild thành công
- [ ] Service restart không lỗi
- [ ] Monitor 10 phút: không error bất thường
- [ ] Snapshots được ghi liên tục mỗi phút
- [ ] Dashboard vẫn hoạt động bình thường
- [ ] Redis state cập nhật bình thường

## Điều kiện nghiệm thu

| # | Điều kiện | Pass? |
|:---|:---|:---|
| 1 | 10 phút chạy không error | [ ] |
| 2 | ≥ 8 snapshots ghi trong 10 phút | [ ] |
| 3 | Dashboard hiển thị data bình thường | [ ] |
| 4 | Latency signal processing ổn định | [ ] |

## Test

```bash
# 1. Rebuild
docker compose -f aureus-foundation.yml up -d --build aureus-signal

# 2. Monitor logs 10 phút
timeout 600 docker logs -f aureus_signal_engine --since 1m

# 3. Count snapshots
docker exec aureus_timescaledb psql -U aureus -d aureus -c "
SELECT count(*), min(time), max(time)
FROM aureus_signal_snapshots 
WHERE time > NOW() - INTERVAL '15 minutes' AND symbol='XAUUSD'
"

# 4. Dashboard check
curl http://localhost:8001/api/v1/state/XAUUSD | python -c "
import json, sys
d = json.load(sys.stdin)
print(f'Symbol: {d.get(\"symbol\")}')
print(f'ATR: {d.get(\"atr\")}')
print(f'Swing points: {len(d.get(\"swing_points\", []))}')
print('✅ Dashboard OK')
"
```
