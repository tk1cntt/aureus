# Requirements — v1.3 Backtesting & Measurement Engine

> **Source docs:** `docs/backtest/` (Phases A-F), user scoping session

## Schema & Infrastructure
- [ ] **SCHEMA-01**: Create `aureus_signal_snapshots` hypertable (time, symbol, atr, ema_21..ema_200, vol_sma_20, htf_trend, market_regime, session, events JSONB, active_obs JSONB, swing_label)
- [ ] **SCHEMA-02**: Create `aureus_backtest_runs` table (id, created_at, symbol, start/end_time, strategy_ids, status, stats JSONB, trades JSONB, equity_curve JSONB)
- [ ] **SCHEMA-03**: Index `idx_signal_snapshots_sym_time` and UNIQUE(time, symbol) with ON CONFLICT DO UPDATE

## Signal Pre-computation
- [ ] **COMPUTE-01**: Extract `create_signal_set()` factory function (shared between live engine + signal_computer)
- [ ] **COMPUTE-02**: Create shared `build_snapshot()` + `batch_insert_snapshots()` utility functions
- [ ] **COMPUTE-03**: Standalone `signal_computer.py` — replay candles, calculate all signals per-candle, batch insert snapshots
- [ ] **COMPUTE-04**: CLI args: --symbol, --start, --end, --months + progress tracking via Redis

## Live System Alignment
- [ ] **LIVE-01**: Live Signal Engine ghi signal snapshot mỗi nến mới (async, fire-and-forget via asyncio.create_task)
- [ ] **LIVE-02**: DB connection pool (asyncpg) cho async writes, error handling không crash main loop
- [ ] **LIVE-03**: Data liền mạch giữa pre-computed (cũ) và live (mới)

## Recovery Enhancement
- [ ] **RECOV-01**: Refactor `recalculate_all_signals()` — chạy signals per-candle (thay vì chỉ nến cuối)
- [ ] **RECOV-02**: `GapDetector.find_snapshot_gaps()` — detect nến có candle nhưng thiếu snapshot
- [ ] **RECOV-03**: `integrity_and_recalc_task` check cả candle gaps lẫn snapshot gaps

## Backtest Engine Core
- [ ] **ENGINE-01**: `BacktestRunnerV2` class — đọc snapshots + rebuild state + evaluate strategies
- [ ] **ENGINE-02**: Verify snapshots tồn tại trước khi chạy, JOIN candles + snapshots
- [ ] **ENGINE-03**: Rebuild `signal_history` + `SymbolState` (atr, emas, trend, regime, session, obs) từ snapshots
- [ ] **ENGINE-04**: Strategy evaluation per-candle — pluggable, bất kỳ BaseStrategy subclass
- [ ] **ENGINE-05**: Order management — SL/TP evaluated against H/L, position close on SL/TP/SESSION_END

## Trade Logging
- [ ] **TRADE-01**: Per-trade record: entry_time, exit_time, entry_price, exit_price, direction, pnl, exit_reason
- [ ] **TRADE-02**: Persist results vào `aureus_backtest_runs` (survives restart)

## Metrics & Quality
- [ ] **METRIC-01**: Win Rate (winning / total trades)
- [ ] **METRIC-02**: Total PnL (net profit/loss)
- [ ] **METRIC-03**: Max Drawdown (peak-to-trough equity decline)
- [ ] **METRIC-04**: Sharpe Ratio (risk-adjusted return)
- [ ] **METRIC-05**: Profit Factor (gross profit / gross loss)
- [ ] **METRIC-06**: Average R:R (reward/risk per trade)
- [ ] **METRIC-07**: Output JSON + Markdown report
- [ ] **METRIC-08**: Per-trade log with timestamps, prices, direction, outcome
- [ ] **QUALITY-01**: Signal Quality Calculator — per signal tag: count, win_rate, avg_pips, trade_rate, quality_grade

## API Endpoints
- [ ] **API-01**: `POST /api/v1/backtest/v2` — trigger backtest
- [ ] **API-02**: `GET /api/v1/backtest/runs?symbol=X` — list all runs
- [ ] **API-03**: `GET /api/v1/backtest/{run_id}/chart-data` — full data for chart
- [ ] **API-04**: `GET /api/v1/signal-snapshot/{symbol}/{timestamp}` — detail for tooltip
- [ ] **API-05**: `POST /api/v1/precompute` — trigger signal pre-computation
- [ ] **API-06**: `GET /api/v1/precompute/status/{symbol}` — pre-compute progress

## Chart UI (Dashboard)
- [ ] **UI-01**: `BacktestChart.tsx` — extend SMCChart with signal event markers + trade markers
- [ ] **UI-02**: `SignalTooltip.tsx` — glassmorphism hover popup with metadata + context + outcome
- [ ] **UI-03**: Trade markers (entry/exit circles) + SL/TP dashed horizontal lines
- [ ] **UI-04**: `SignalQualityCard.tsx` — scorecard panel with win_rate bars + letter grades
- [ ] **UI-05**: `EquityCurve.tsx` — lightweight-charts area chart (green/red) with drawdown shading
- [ ] **UI-06**: Redesign `backtest/page.tsx` — chart + quality + equity + trade log layout
- [ ] **UI-07**: Pre-compute trigger button + progress bar UI
- [ ] **UI-08**: Click signal type → filter/highlight markers on chart

## Future Requirements
- [ ] **ORDER-F01**: Realistic order simulation — slippage, spread, partial fills
- [ ] **MULTI-F01**: Multi-strategy comparison in single run
- [ ] **OPT-F01**: Strategy parameter optimization / auto-tuning sweep

## Out of Scope
- Live trading execution (simulation only)
- Real-time data streaming (batch only)
- Paper trading mode

## Traceability
| Requirement | Phase |
|---|---|
| SCHEMA-01→03 | 16 |
| COMPUTE-01→04 | 17 |
| LIVE-01→03 | 18 |
| RECOV-01→03 | 19 |
| ENGINE-01→05, TRADE-01→02, QUALITY-01 | 20 |
| METRIC-01→08, API-01→06 | 21 |
| UI-01→08 | 22 |
