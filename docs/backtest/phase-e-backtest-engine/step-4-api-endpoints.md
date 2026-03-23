# Step 4: API Endpoints

> **Phase**: E — Backtest Engine v2  
> **Thời gian**: ~45 phút | **Risk**: Thấp  
> **Input**: BacktestRunnerV2, quality calculator, DB tables  
> **Output**: REST API endpoints cho frontend

---

## Mô tả

Thêm các endpoints vào Dashboard API để frontend có thể trigger backtest, monitor progress, và query results.

## Endpoints

### 4a. `POST /api/v1/backtest/v2`
- **Input**: `{ symbol, start, end, strategy_ids? }`
- **Output**: `{ run_id, status: "RUNNING" }`
- **Logic**: Spawn background task, return immediately

### 4b. `GET /api/v1/backtest/runs?symbol=X`
- **Input**: Query param `symbol`
- **Output**: `[{ id, symbol, start_time, end_time, status, stats }]`
- **Logic**: SELECT from `aureus_backtest_runs`

### 4c. `GET /api/v1/backtest/{run_id}/chart-data`
- **Input**: Path param `run_id`
- **Output**: 
  ```json
  {
    "candles": [...],
    "signal_events": [...],
    "swing_points": [...],
    "obs": [...],
    "trades": [...],
    "signal_quality": [...],
    "equity_curve": [...]
  }
  ```
- **Logic**: JOIN candles + snapshots + backtest results

### 4d. `POST /api/v1/precompute`
- **Input**: `{ symbol, months: 6 }`
- **Output**: `{ status: "STARTED" }`
- **Logic**: Spawn `signal_computer` as background task

### 4e. `GET /api/v1/precompute/status/{symbol}`
- **Input**: Path param `symbol`
- **Output**: `{ progress: 78.5, processed: 12000, total: 15300 }`
- **Logic**: Read Redis key

### 4f. `GET /api/v1/signal-snapshot/{symbol}/{timestamp}`
- **Input**: Path params
- **Output**: Full snapshot row for tooltip
- **Logic**: SELECT from `aureus_signal_snapshots`

## Checklist

- [ ] Endpoint 4a: POST backtest/v2
- [ ] Endpoint 4b: GET backtest/runs
- [ ] Endpoint 4c: GET backtest/{id}/chart-data
- [ ] Endpoint 4d: POST precompute
- [ ] Endpoint 4e: GET precompute/status
- [ ] Endpoint 4f: GET signal-snapshot detail
- [ ] Error handling (404, 400, 500)
- [ ] CORS headers

## Điều kiện nghiệm thu

| # | Điều kiện | Pass? |
|:---|:---|:---|
| 1 | POST backtest/v2 trả về run_id | [ ] |
| 2 | GET runs trả về list | [ ] |
| 3 | GET chart-data trả về full payload | [ ] |
| 4 | POST precompute starts background task | [ ] |
| 5 | GET precompute/status trả về progress | [ ] |
| 6 | GET signal-snapshot trả về detail | [ ] |
| 7 | Invalid requests → proper error codes | [ ] |

## Test

```bash
# 4a. Run backtest
curl -X POST http://localhost:8001/api/v1/backtest/v2 \
  -H "Content-Type: application/json" \
  -d '{"symbol":"XAUUSD","start":"2026-02-20","end":"2026-02-27"}'
# Expect: {"run_id": 1, "status": "RUNNING"}

# 4b. List runs
curl http://localhost:8001/api/v1/backtest/runs?symbol=XAUUSD
# Expect: array of runs

# 4c. Chart data (after completion)
curl http://localhost:8001/api/v1/backtest/1/chart-data | python -c "
import json, sys
d = json.load(sys.stdin)
for k, v in d.items():
    print(f'{k}: {len(v) if isinstance(v, list) else type(v).__name__}')
"

# 4d. Pre-compute
curl -X POST http://localhost:8001/api/v1/precompute \
  -H "Content-Type: application/json" \
  -d '{"symbol":"XAUUSD","months":1}'

# 4e. Status
curl http://localhost:8001/api/v1/precompute/status/XAUUSD

# 4f. Signal detail
curl http://localhost:8001/api/v1/signal-snapshot/XAUUSD/1709337600
```
