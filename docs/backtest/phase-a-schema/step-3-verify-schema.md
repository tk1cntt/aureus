# Step 3: Verify Schema & Constraints

> **Phase**: A — Schema & Migration  
> **Thời gian**: ~10 phút | **Risk**: Zero  
> **Input**: Bảng đã tạo từ Step 2  
> **Output**: Xác nhận schema hoạt động đúng

---

## Mô tả

Verify toàn diện schema: columns đúng type, UNIQUE constraint hoạt động, ON CONFLICT DO UPDATE hoạt động, hypertable compression config.

## Checklist

- [ ] Verify columns + types cho `aureus_signal_snapshots`
- [ ] Verify columns + types cho `aureus_backtest_runs`
- [ ] Test INSERT 1 row → SELECT → verify data
- [ ] Test UNIQUE constraint (duplicate insert → error)
- [ ] Test ON CONFLICT DO UPDATE (upsert)
- [ ] Test JSONB column (events, active_obs) lưu + đọc đúng
- [ ] Cleanup test data

## Điều kiện nghiệm thu

| # | Điều kiện | Pass? |
|:---|:---|:---|
| 1 | INSERT thành công | [ ] |
| 2 | SELECT trả về đúng data | [ ] |
| 3 | Duplicate INSERT bị reject (UNIQUE) | [ ] |
| 4 | ON CONFLICT DO UPDATE thay đổi giá trị | [ ] |
| 5 | JSONB lưu + parse đúng | [ ] |
| 6 | Test data đã được cleanup | [ ] |

## Test

```sql
-- 1. Insert test data
INSERT INTO aureus_signal_snapshots 
    (time, symbol, atr, ema_21, ema_200, htf_trend, session, events, active_obs)
VALUES 
    ('2025-01-01 00:00:00+00', 'TEST_SYM', 5.23, 2850.5, 2800.1, 'BULLISH', 'LONDON',
     '[{"tag":"choch_up","pivot_price":2849.0}]'::jsonb,
     '[{"ob_type":"BULLISH","top":2851.0,"bottom":2849.5}]'::jsonb);

-- 2. Verify SELECT
SELECT time, symbol, atr, ema_21, htf_trend, events, active_obs 
FROM aureus_signal_snapshots WHERE symbol = 'TEST_SYM';

-- 3. Test UNIQUE violation
INSERT INTO aureus_signal_snapshots (time, symbol, atr)
VALUES ('2025-01-01 00:00:00+00', 'TEST_SYM', 99.99);
-- Expect: ERROR duplicate key

-- 4. Test ON CONFLICT DO UPDATE
INSERT INTO aureus_signal_snapshots (time, symbol, atr)
VALUES ('2025-01-01 00:00:00+00', 'TEST_SYM', 99.99)
ON CONFLICT (time, symbol) DO UPDATE SET atr = 99.99;

SELECT atr FROM aureus_signal_snapshots WHERE symbol = 'TEST_SYM';
-- Expect: atr = 99.99

-- 5. Test JSONB query
SELECT events->0->>'tag' as event_tag
FROM aureus_signal_snapshots WHERE symbol = 'TEST_SYM';
-- Expect: choch_up

-- 6. Test backtest_runs
INSERT INTO aureus_backtest_runs (symbol, start_time, end_time, status, stats)
VALUES ('TEST_SYM', '2025-01-01', '2025-02-01', 'COMPLETED', 
        '{"win_rate":65.5,"total_trades":12}'::jsonb);
SELECT id, symbol, status, stats->>'win_rate' as win_rate 
FROM aureus_backtest_runs WHERE symbol = 'TEST_SYM';

-- 7. Cleanup
DELETE FROM aureus_signal_snapshots WHERE symbol = 'TEST_SYM';
DELETE FROM aureus_backtest_runs WHERE symbol = 'TEST_SYM';
```
