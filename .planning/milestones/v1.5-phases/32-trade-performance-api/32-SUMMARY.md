# Phase 32: Trade Performance API — Summary

**Status:** Completed
**Commits:** 98781cd

## What was built

- **3 performance endpoints** added to `services/aureus-dashboard/api/main.py`:
  - `GET /api/v1/performance/trades` — paginated trade list with filters (symbol, strategy_id, start, end, status)
  - `GET /api/v1/performance/metrics` — computed metrics (win_rate, profit_factor, max_drawdown, avg_rr, sharpe_ratio) with Redis cache (60s TTL)
  - `GET /api/v1/performance/equity-curve` — equity time series from `aureus_account_snapshots` with `aureus_trades` fallback, Redis cache (30s TTL)
- **Connection pooling**: `asyncpg.create_pool(min_size=2, max_size=10)` on startup
- **Hybrid metrics computation**: SQL aggregation (win_rate, profit_factor) + numpy (max_drawdown, sharpe_ratio)
- **Response envelope**: `{"data": [...], "meta": {...}}` consistent across endpoints
- Added `numpy` dependency to `requirements.txt`

## Test results

- All endpoints registered and functional
- Redis caching verified for metrics (60s) and equity-curve (30s)
- Filters (symbol, strategy_id, date range) work across all endpoints
