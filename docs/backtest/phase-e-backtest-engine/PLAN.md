# Phase E: Backtest Engine v2

> **Độ khó**: ⭐⭐⭐⭐ | **Ảnh hưởng Live**: Zero | **Thời gian**: 3-4 giờ  
> **Phụ thuộc**: Phase A (schema), Phase B (pre-computed data tồn tại trong DB)  
> **Mô tả**: Backtest engine mới đọc signal snapshots có sẵn, rebuild state, chạy strategies, quản lý orders. Tách biệt hoàn toàn với live system.

---

## Checklist tính năng

- [ ] `BacktestRunnerV2` class với method `run(symbol, start, end, strategy_ids)`
- [ ] Verify snapshots tồn tại trước khi chạy
- [ ] Load snapshots + candles (JOIN query)
- [ ] Rebuild `signal_history` từ snapshot events
- [ ] Rebuild `SymbolState` (atr, emas, trend, regime, session, obs) từ snapshot
- [ ] Strategy evaluation per-candle
- [ ] Order management (SL/TP) tách biệt
- [ ] Lưu kết quả vào `aureus_backtest_runs`
- [ ] Signal Quality calculation
- [ ] API endpoints: `POST /backtest/v2`, `GET /backtest/runs`, `GET /backtest/{id}/chart-data`

---

## Steps

### Step 1: Implement `BacktestRunnerV2` — Core Logic
- **File mới**: `services/aureus-signal/engine/backtest_engine_v2.py`
- **Mô tả**: Main class đọc snapshots + chạy strategies
- **Logic**:
  1. Verify snapshots exist (count query)
  2. JOIN `aureus_candles` + `aureus_signal_snapshots` cho thời gian backtest
  3. Iterate từng row:
     - Restore state từ snapshot (atr, emas, trend, regime, session)
     - Restore OBs từ `active_obs` JSONB
     - Inject events vào `signal_history` + `transient_signals`
     - `state.update_with_candle()` cho OB/FVG lifecycle
     - `strategy_registry.evaluate_all()`
     - Order management (SL/TP check)
     - Clear transient signals
  4. Aggregate results: trades, stats, equity_curve
- **Điều kiện hoàn thành**: Chạy backtest trên pre-computed data thành công
- **Test**: Chạy 1 tuần backtest → kiểm tra trades hợp lý

### Step 2: Signal Quality Calculator
- **File thêm vào**: `backtest_engine_v2.py` hoặc `services/aureus-signal/engine/quality_calculator.py`
- **Mô tả**: Tính quality scorecard cho từng signal type
- **Logic**:
  - Cho mỗi signal tag (choch_up, sweep_bull, etc.)
  - Đếm appearances → correlate với trades trong lookahead window (30 nến)
  - Tính: count, win_rate, avg_pips, trade_rate, quality_grade
- **Điều kiện hoàn thành**: Trả về signal quality dict
- **Test**: Run quality calculator → verify grades hợp lý

### Step 3: Persist Results to `aureus_backtest_runs`
- **File**: `backtest_engine_v2.py`
- **Mô tả**: Sau khi backtest xong, INSERT kết quả vào DB
- **Nội dung**:
  ```python
  await db.execute("""
    INSERT INTO aureus_backtest_runs 
    (symbol, start_time, end_time, strategy_ids, status, stats, trades, equity_curve)
    VALUES ($1, $2, $3, $4, 'COMPLETED', $5, $6, $7)
  """, ...)
  ```
- **Điều kiện hoàn thành**: Results persist qua restart
- **Test**: Run backtest → restart server → query results vẫn còn

### Step 4: API Endpoints
- **File**: `services/aureus-dashboard/api/main.py`
- **Endpoints mới**:
  1. `POST /api/v1/backtest/v2` — Trigger backtest v2
  2. `GET /api/v1/backtest/runs?symbol=X` — List all runs
  3. `GET /api/v1/backtest/{run_id}/chart-data` — Full data cho chart
  4. `GET /api/v1/signal-snapshot/{symbol}/{timestamp}` — Detail cho tooltip
  5. `POST /api/v1/precompute` — Trigger signal pre-computation
  6. `GET /api/v1/precompute/status/{symbol}` — Pre-compute progress
- **Điều kiện hoàn thành**: Tất cả endpoints respond đúng
- **Test**: Call từng endpoint via curl, verify response

---

## Điều kiện nghiệm thu Phase E

| # | Điều kiện | Verified? |
|:---|:---|:---|
| E1 | `BacktestRunnerV2.run()` hoàn thành không error | [ ] |
| E2 | Backtest 2 tuần (~20,160 nến) hoàn thành < 15 giây | [ ] |
| E3 | `signal_history` rebuilt đúng từ snapshot events | [ ] |
| E4 | Strategy triggers xảy ra (không trống như engine cũ) | [ ] |
| E5 | Orders có SL/TP hits hợp lý | [ ] |
| E6 | Signal quality scorecard có data | [ ] |
| E7 | Results persist trong `aureus_backtest_runs` | [ ] |
| E8 | API endpoints respond đúng format | [ ] |
| E9 | Live system không bị ảnh hưởng | [ ] |

---

## Test End-to-End Phase E

```bash
# 1. Ensure pre-computed data exists (Phase B)
docker exec aureus_timescaledb psql -U aureus -d aureus -c "
SELECT count(*) FROM aureus_signal_snapshots WHERE symbol='XAUUSD'
"

# 2. Run backtest via API
curl -X POST http://localhost:8001/api/v1/backtest/v2 \
  -H "Content-Type: application/json" \
  -d '{"symbol":"XAUUSD","start":"2026-02-01","end":"2026-02-14"}'

# 3. Check results
curl http://localhost:8001/api/v1/backtest/runs?symbol=XAUUSD | python -m json.tool

# 4. Get chart data for a run
curl http://localhost:8001/api/v1/backtest/1/chart-data | python -m json.tool | head -50

# 5. Verify signal quality
curl http://localhost:8001/api/v1/backtest/1/chart-data | python -c "
import json, sys
data = json.load(sys.stdin)
print('Signal Quality:')
for sq in data.get('signal_quality', []):
    print(f\"  {sq['tag']}: {sq['win_rate']:.1f}% win, {sq['count']} signals\")
"

# 6. Compare with old backtest (regression)
# Run same period with old engine → compare trade count
```
