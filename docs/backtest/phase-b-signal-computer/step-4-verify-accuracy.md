# Step 4: Verify Data Accuracy

> **Phase**: B — Signal Computer  
> **Thời gian**: ~30 phút | **Risk**: Zero (read-only)  
> **Input**: Pre-computed data từ Step 3  
> **Output**: Xác nhận data chính xác

---

## Mô tả

So sánh pre-computed signal values với live system (Redis state) và kiểm tra tính hợp lý. Đảm bảo re-run (idempotent) không tạo duplicates.

## Checklist

- [ ] EMA values khớp với live state (±0.1%)
- [ ] ATR values hợp lý (> 0, < 50 cho XAUUSD)
- [ ] HTF Trend phân bố hợp lý (BULLISH/BEARISH/NEUTRAL)
- [ ] Session phân bố đúng theo giờ
- [ ] Events xuất hiện (CHOCH/BOS/Sweep tags đều có)
- [ ] Re-run không duplicate (count giữ nguyên)
- [ ] Active OBs JSONB parseable

## Điều kiện nghiệm thu

| # | Điều kiện | Pass? |
|:---|:---|:---|
| 1 | EMA values hợp lý (> 0, monotonic window) | [ ] |
| 2 | ATR values > 0 cho tất cả rows sau warmup | [ ] |
| 3 | Ít nhất 3 loại event tags xuất hiện | [ ] |
| 4 | Session = ASIA/LONDON/NEW_YORK/OFF_MARKET tùy giờ | [ ] |
| 5 | Re-run count = first run count | [ ] |

## Test

```sql
-- 1. EMA continuity check (không nhảy bất thường)
SELECT time, ema_21, 
       ABS(ema_21 - LAG(ema_21) OVER (ORDER BY time)) as ema_diff
FROM aureus_signal_snapshots 
WHERE symbol='XAUUSD' AND ema_21 IS NOT NULL
ORDER BY time DESC LIMIT 20;

-- 2. Distribution check
SELECT htf_trend, count(*) 
FROM aureus_signal_snapshots WHERE symbol='XAUUSD'
GROUP BY htf_trend;

SELECT session, count(*) 
FROM aureus_signal_snapshots WHERE symbol='XAUUSD'
GROUP BY session;

-- 3. Event diversity check
SELECT DISTINCT jsonb_array_elements(events)->>'tag' as event_tag
FROM aureus_signal_snapshots 
WHERE symbol='XAUUSD' AND events IS NOT NULL;

-- 4. ATR sanity check
SELECT min(atr), avg(atr), max(atr), count(*) as total, 
       count(CASE WHEN atr IS NULL THEN 1 END) as null_count
FROM aureus_signal_snapshots WHERE symbol='XAUUSD';

-- 5. Re-run idempotent test
SELECT count(*) as before_rerun FROM aureus_signal_snapshots WHERE symbol='XAUUSD';
-- Run signal_computer.py again
SELECT count(*) as after_rerun FROM aureus_signal_snapshots WHERE symbol='XAUUSD';
-- Expect: same count
```
