# Step 3: Persist Results to aureus_backtest_runs

> **Phase**: E — Backtest Engine v2  
> **Thời gian**: ~20 phút | **Risk**: Thấp  
> **Input**: Backtest results từ Step 1  
> **Output**: Results stored in DB, queryable later

---

## Mô tả

Sau khi backtest hoàn thành, INSERT kết quả vào `aureus_backtest_runs`. Include stats, trades, equity_curve, signal_quality.

## Checklist

- [ ] INSERT INTO `aureus_backtest_runs` sau khi backtest xong
- [ ] Store: symbol, start_time, end_time, strategy_ids
- [ ] Store: status = 'COMPLETED' (hoặc 'FAILED')
- [ ] Store: stats (JSONB), trades (JSONB), equity_curve (JSONB)
- [ ] Return `run_id` cho frontend
- [ ] Query: GET run by id
- [ ] Query: LIST runs by symbol

## Điều kiện nghiệm thu

| # | Điều kiện | Pass? |
|:---|:---|:---|
| 1 | Backtest result được lưu vào DB | [ ] |
| 2 | Query by id trả về đúng data | [ ] |
| 3 | Query list by symbol trả về tất cả runs | [ ] |
| 4 | JSONB fields parse đúng | [ ] |
| 5 | Data persist qua service restart | [ ] |

## Test

```sql
-- After running a backtest
SELECT id, symbol, start_time, end_time, status,
       stats->>'win_rate' as win_rate,
       stats->>'total_trades' as total_trades,
       jsonb_array_length(trades) as trade_count
FROM aureus_backtest_runs
ORDER BY created_at DESC LIMIT 5;
```
