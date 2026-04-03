# Requirements Archive: v1.3 Backtesting & Measurement Engine

**Archived:** 2026-04-03
**Status:** SHIPPED

For current requirements, see `.planning/REQUIREMENTS.md`.

---

# Requirements — v1.3 Backtesting & Measurement Engine

> **Source docs:** `docs/backtest/`, user scoping session, party mode review, Nautilus integration research (2026-03-23)
> **Architecture:** Nautilus BacktestEngine + AureusSignalActor + AureusStrategyAdapter

## Strategy Quality Assurance (Pre-Nautilus)
- [ ] **STRATQA-01**: Seed strategy unit tests — test all 3 strategies (TREND_CONT, SESSION_SWEEP, ORDER_FLOW_DOM) with context_filters (trend, session, OB imbalance, EMA slope) + sequence matching
- [ ] **STRATQA-02**: Scenario tests — run strategies through real signal pipeline on curated candle datasets (bullish breakout, ranging market, bearish reversal), verify triggers and rejects
- [ ] **STRATQA-03**: Strategy determinism test — same candle data → identical results on 2 independent runs
- [ ] **STRATQA-04**: `strategy_replay.py` — standalone replay tool (candle→signals→strategy→intents), no Nautilus dependency, generates trigger log + baseline metrics
- [ ] **STRATQA-05**: Baseline report for XAUUSD 30 days — trigger count, trigger rate, score distribution, signal contribution per strategy

## Schema & Data Loader
- [ ] **SCHEMA-01**: Create `aureus_backtest_runs` table (id, symbol, strategy, strategy_config, start/end_time, bar_count, trade_count, stats JSONB, status, nautilus_config JSONB)
- [ ] **SCHEMA-02**: Create `aureus_backtest_trades` hypertable (run_id, time, symbol, direction, entry/exit time/price, sl/tp price, pnl, pnl_pips, exit_reason, duration_minutes, signal_tags JSONB)
- [ ] **SCHEMA-03**: Create `aureus_backtest_equity` hypertable (run_id, time, balance, equity, drawdown, drawdown_pct)
- [ ] **SCHEMA-04**: Create data loader — read `aureus_candles` from TimescaleDB → convert to Nautilus `Bar` via `BarDataWrangler` with instrument definitions

## Nautilus Integration (Core)
- [ ] **NAUTILUS-01**: `AureusSignalActor` (Nautilus Actor) — receives bars via `on_bar()`, runs all 18 Aureus signals per bar, publishes `AureusSignalSnapshot` via `msg_bus`
- [ ] **NAUTILUS-02**: `AureusSignalSnapshot` (Custom Data) — carries signals dict, SymbolState, signal_history, candle_buffer per bar
- [ ] **NAUTILUS-03**: `AureusStrategyAdapter` (Nautilus Strategy) — subscribes to snapshots + bars, calls `on_bar_close()` → `validate_entry()` → `build_order_plan()`, submits bracket orders
- [ ] **NAUTILUS-04**: Backtest runner script — configure `BacktestEngine`, add venue (SIM, MARGIN, bar_execution=True, bar_adaptive_high_low_ordering=True), add Actor + Strategy + data, run, extract results
- [ ] **NAUTILUS-05**: Instrument definitions — CurrencyPair/CFD for each supported symbol (XAUUSD, BTCUSD, ETHUSD...) with correct price_precision, size_precision
- [ ] **NAUTILUS-06**: Venue fill model config — `FillModel(prob_slippage=X)` or `ThreeTierFillModel` configurable per run

## Parity & Correctness
- [ ] **PARITY-01**: Parity validation — `AureusSignalActor` MUST produce identical signal outputs to live engine on same candle data
- [ ] **PARITY-02**: Automated parity test — run N candles through both Actor and live engine, diff signal_history + strategy intents
- [ ] **PARITY-03**: Sample trade set with known expected metrics — validates metric calculator correctness

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

## Measurement Integrity
- [ ] **MEASURE-01**: Spread/commission via Nautilus FillModel config or post-processing deduction (configurable per symbol)
- [ ] **MEASURE-02**: Buy-and-hold benchmark baseline — compare strategy PnL vs passive hold
- [ ] **MEASURE-03**: Walk-forward analysis — train/test window rolling to detect overfitting

## API Endpoints
- [ ] **API-01**: `POST /api/v1/backtest/v2` — trigger backtest (symbol, strategy, date range, venue config)
- [ ] **API-02**: `GET /api/v1/backtest/runs?symbol=X` — list all runs
- [ ] **API-03**: `GET /api/v1/backtest/{run_id}/chart-data` — full data for chart
- [ ] **API-04**: `GET /api/v1/signal-snapshot/{symbol}/{timestamp}` — detail for tooltip
- [ ] **API-05**: `POST /api/v1/precompute` — trigger signal pre-computation
- [ ] **API-06**: `GET /api/v1/precompute/status/{symbol}` — pre-compute progress

## Custom UI (Primary)
- [ ] **UI-01**: Backtest runner form — select symbol, strategy, date range, venue config
- [ ] **UI-02**: `BacktestChart` — candlestick chart with signal event markers (CHOCH/BOS/Sweep)
- [ ] **UI-03**: Trade markers (entry/exit) + SL/TP dashed lines overlay
- [ ] **UI-04**: Hover tooltip with signal metadata + context + outcome
- [ ] **UI-05**: `SignalQualityCard` — scorecard with win_rate bars + letter grades
- [ ] **UI-06**: `EquityCurve` — area chart with drawdown shading
- [ ] **UI-07**: Pre-compute trigger button + progress bar
- [ ] **UI-08**: Click signal type → filter/highlight markers on chart

## Grafana (Supplementary)
- [ ] **GRAFANA-01**: Add TimescaleDB datasource to Grafana provisioning
- [ ] **GRAFANA-02**: "Backtest Performance" dashboard — aggregate stats, equity curves, strategy comparison heatmaps
- [ ] **GRAFANA-03**: "Signal Quality" dashboard — per-signal win rates, contribution metrics across runs

## Live System Alignment
- [ ] **LIVE-01**: Live Signal Engine ghi signal snapshot mỗi nến mới (async fire-and-forget)
- [ ] **LIVE-02**: DB connection pool (asyncpg) cho async writes, error handling không crash main loop
- [ ] **LIVE-03**: Data liền mạch giữa pre-computed (cũ) và live (mới)

## Recovery Enhancement
- [ ] **RECOV-01**: Refactor `recalculate_all_signals()` — chạy signals per-candle
- [ ] **RECOV-02**: `GapDetector.find_snapshot_gaps()` — detect nến có candle nhưng thiếu snapshot
- [ ] **RECOV-03**: `integrity_and_recalc_task` check cả candle gaps lẫn snapshot gaps

## Future Requirements (v1.4+)
- [ ] **ORDER-F01**: Advanced fill models — `ProbabilisticFillModel`, `SizeAwareFillModel`
- [ ] **MULTI-F01**: Multi-strategy comparison / A/B test in single run
- [ ] **OPT-F01**: Strategy parameter optimization / auto-tuning sweep
- [ ] **MULTI-F02**: Multi-symbol concurrent backtest
- [ ] **CONFIG-F01**: Strategy config versioning — backtest with historical config snapshots
- [ ] **DATA-F01**: Auto-refresh pre-computed data (scheduled re-compute)

## Out of Scope
- Custom order matching engine (Nautilus handles this)
- Custom SL/TP priority logic (Nautilus `bar_adaptive_high_low_ordering`)
- Custom slippage simulation (Nautilus `FillModel`)
- Paper trading mode
- Strategy auto-optimization / parameter sweep
- Multi-symbol concurrent in v1.3

## Traceability
| Requirement | Phase |
|---|---|
| STRATQA-01→05 | 15.5 |
| SCHEMA-01→04 | 16 |
| NAUTILUS-01→06, PARITY-01→03 | 17 |
| METRIC-01→08, QUALITY-01, MEASURE-01→03 | 18 |
| UI-01→08, API-01→06 | 19 |
| GRAFANA-01→03, LIVE-01→03, RECOV-01→03 | 20 |
