# Step 4: Config lookback_hours + E2E Downtime Test

> **Phase**: D — Recovery Enhancement  
> **Thời gian**: ~30 phút | **Risk**: Zero (config + test only)  
> **Input**: All changes from Steps 1-3  
> **Output**: Configurable lookback + verified downtime recovery

---

## Mô tả

Thêm env var `GAP_LOOKBACK_HOURS` cho GapDetector. Sau đó chạy full E2E test: simulate downtime → verify tự động recovery cả candles lẫn snapshots.

## Checklist

- [ ] Env var `GAP_LOOKBACK_HOURS` (default 24, range 1-168)
- [ ] GapDetector đọc env var
- [ ] E2E test: stop Signal Engine 3 phút → restart → verify full recovery
- [ ] Verify: candles được backfill
- [ ] Verify: snapshots được tạo cho candles backfilled
- [ ] Verify: live signals tiếp tục bình thường

## Điều kiện nghiệm thu

| # | Điều kiện | Pass? |
|:---|:---|:---|
| 1 | Env var `GAP_LOOKBACK_HOURS` hoạt động | [ ] |
| 2 | After downtime: candles backfilled | [ ] |
| 3 | After downtime: snapshots created cho backfilled candles | [ ] |
| 4 | After downtime: live system tiếp tục bình thường | [ ] |
| 5 | Dashboard hiển thị data liên tục (không có gap) | [ ] |

## Test E2E — Full Downtime Simulation

```bash
# ═══════════════════════════════════════════════
# FULL E2E DOWNTIME RECOVERY TEST
# ═══════════════════════════════════════════════

# 0. Record baseline
echo "=== BEFORE ==="
docker exec aureus_timescaledb psql -U aureus -d aureus -c "
SELECT 'candles' as type, count(*), max(time) FROM aureus_candles WHERE symbol='XAUUSD'
UNION ALL
SELECT 'snapshots', count(*), max(time) FROM aureus_signal_snapshots WHERE symbol='XAUUSD'
"

# 1. STOP Signal Engine (simulate downtime)
echo "=== STOPPING SIGNAL ENGINE ==="
docker stop aureus_signal_engine
echo "Waiting 3 minutes for gap to form..."
sleep 180

# 2. RESTART
echo "=== RESTARTING ==="
docker start aureus_signal_engine

# 3. Wait for recovery (up to 2 minutes)
echo "Waiting for recovery..."
sleep 120

# 4. Verify
echo "=== AFTER RECOVERY ==="
docker exec aureus_timescaledb psql -U aureus -d aureus -c "
SELECT 'candles' as type, count(*), max(time) FROM aureus_candles WHERE symbol='XAUUSD'
UNION ALL
SELECT 'snapshots', count(*), max(time) FROM aureus_signal_snapshots WHERE symbol='XAUUSD'
"

# 5. Check gap coverage
echo "=== GAP CHECK ==="
docker exec aureus_timescaledb psql -U aureus -d aureus -c "
SELECT c.time, s.time IS NOT NULL as has_snapshot
FROM aureus_candles c
LEFT JOIN aureus_signal_snapshots s ON c.time = s.time AND c.symbol = s.symbol
WHERE c.symbol='XAUUSD' AND c.time > NOW() - INTERVAL '10 minutes'
ORDER BY c.time DESC
"
# ALL rows should have has_snapshot = true

# 6. Dashboard check
curl -s http://localhost:8001/api/v1/state/XAUUSD | python -c "
import json, sys
d = json.load(sys.stdin)
print(f'State OK: symbol={d.get(\"symbol\")}, atr={d.get(\"atr\")}')
"

echo "=== TEST COMPLETE ==="
```
