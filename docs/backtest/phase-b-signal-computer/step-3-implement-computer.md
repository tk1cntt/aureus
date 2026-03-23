# Step 3: Implement Signal Computer Script

> **Phase**: B — Signal Computer  
> **Thời gian**: ~1 giờ | **Risk**: Thấp (standalone, không đụng live)  
> **Input**: `signal_factory.py` (Step 1) + `snapshot_utils.py` (Step 2)  
> **Output**: `services/aureus-signal/signal_computer.py`

---

## Mô tả

Script chạy standalone, đọc candles lịch sử → replay tính signals per-candle → batch ghi vào `aureus_signal_snapshots`. Có CLI args, progress tracking, error handling.

## Checklist

- [ ] File `signal_computer.py` chạy được standalone
- [ ] CLI args: `--symbol` (required), `--start`, `--end`, `--months`
- [ ] Connect DB (asyncpg) + Redis
- [ ] Load candles từ `aureus_candles` (ORDER BY time ASC)
- [ ] Tạo WindowManager + signals via `create_signal_set()`
- [ ] Replay loop:
  - [ ] `window_manager.update(symbol, candle)` per-candle
  - [ ] Clear `state.transient_signals = {}` trước mỗi nến
  - [ ] Chạy ALL signals qua `signal_calc.calculate()`
  - [ ] `state.log_signal()` cho events
  - [ ] `build_snapshot(state, candle)` → append to batch
- [ ] Batch insert mỗi 500 rows
- [ ] Progress tracking: Redis key `aureus:precompute:status:{symbol}`
- [ ] Summary log: total candles, total events, duration
- [ ] Graceful error handling (continue on individual signal error)

## Điều kiện nghiệm thu

| # | Điều kiện | Pass? |
|:---|:---|:---|
| 1 | Script chạy không crash với `--symbol XAUUSD --months 1` | [ ] |
| 2 | Output rows ≈ input candle count (±5%) | [ ] |
| 3 | Progress key cập nhật trong Redis | [ ] |
| 4 | EMA/ATR values không null (sau warmup 20 bars) | [ ] |
| 5 | Events xuất hiện (JSONB not null ở ít nhất vài rows) | [ ] |
| 6 | Performance: < 3ms/candle | [ ] |

## Test

```bash
# 1. Chạy cho 1 ngày (nhỏ, nhanh)
cd services/aureus-signal
python signal_computer.py --symbol XAUUSD --start 2026-02-25 --end 2026-02-26

# 2. Verify row count
docker exec aureus_timescaledb psql -U aureus -d aureus -c "
SELECT count(*), min(time), max(time) 
FROM aureus_signal_snapshots 
WHERE symbol='XAUUSD' AND time >= '2026-02-25' AND time < '2026-02-26'
"
# Expect: ~1440 rows (1 day of M1 candles)

# 3. Verify data quality
docker exec aureus_timescaledb psql -U aureus -d aureus -c "
SELECT time, atr, ema_21, htf_trend, session,
       CASE WHEN events IS NOT NULL THEN jsonb_array_length(events) ELSE 0 END as event_count
FROM aureus_signal_snapshots 
WHERE symbol='XAUUSD' AND time >= '2026-02-25'
ORDER BY time ASC LIMIT 30
"

# 4. Verify progress
redis-cli GET aureus:precompute:status:XAUUSD

# 5. Chạy cho 1 tuần (medium test)
python signal_computer.py --symbol XAUUSD --start 2026-02-20 --end 2026-02-27
```

## Rollback

```bash
# Xóa pre-computed data
docker exec aureus_timescaledb psql -U aureus -d aureus -c "
DELETE FROM aureus_signal_snapshots WHERE symbol='XAUUSD'
"
```
