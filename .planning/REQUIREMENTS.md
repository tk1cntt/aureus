# Requirements — v1.3 Backtesting & Measurement Engine

## Data Loading
- [ ] **DATA-01**: Engine can load historical candles from PostgreSQL database (existing candles table)
- [ ] **DATA-02**: Engine can load historical candles from CSV/JSON file input
- [ ] **DATA-03**: Data loader validates candle continuity (no gaps, correct ordering) before simulation starts

## Strategy Execution
- [ ] **STRAT-01**: Backtester accepts any strategy class implementing BaseStrategy interface (pluggable)
- [ ] **STRAT-02**: Backtester replays candles through strategy's `on_bar_close()` pipeline, collecting intents
- [ ] **STRAT-03**: Backtester evaluates context_filters and sequence matching identically to live engine

## Order Simulation (Phase 1: Simple)
- [ ] **ORDER-01**: Mock executor opens position at entry price when strategy emits actionable intent
- [ ] **ORDER-02**: SL/TP evaluated against each subsequent candle's H/L to determine hit
- [ ] **ORDER-03**: Position closes when SL, TP, or session end is reached
- [ ] **ORDER-04**: Trade log records entry time, exit time, entry price, exit price, direction, PnL per trade

## Metrics & Reporting
- [ ] **METRIC-01**: Calculate Win Rate (winning trades / total trades)
- [ ] **METRIC-02**: Calculate total PnL (net profit/loss across all trades)
- [ ] **METRIC-03**: Calculate Max Drawdown (peak-to-trough equity decline)
- [ ] **METRIC-04**: Calculate Sharpe Ratio (risk-adjusted return)
- [ ] **METRIC-05**: Calculate Profit Factor (gross profit / gross loss)
- [ ] **METRIC-06**: Calculate Average R:R (average reward-to-risk ratio per trade)
- [ ] **METRIC-07**: Output report as JSON file + human-readable markdown summary
- [ ] **METRIC-08**: Include per-trade log with timestamps, prices, direction, and outcome

## Future Requirements
- [ ] **ORDER-F01**: Realistic order simulation — slippage, spread, partial fills, time delay
- [ ] **UI-F01**: Dashboard UI for visualizing backtest results (charts, equity curve)
- [ ] **MULTI-F01**: Multi-strategy comparison in single run

## Out of Scope
- Live trading execution (backtester is simulation only)
- Real-time data streaming (batch processing only)
- Strategy optimization/auto-tuning (parameter sweep)
- Paper trading mode with live data feed

## Traceability
| Requirement | Phase |
|---|---|
| DATA-01 | TBD |
| DATA-02 | TBD |
| DATA-03 | TBD |
| STRAT-01 | TBD |
| STRAT-02 | TBD |
| STRAT-03 | TBD |
| ORDER-01 | TBD |
| ORDER-02 | TBD |
| ORDER-03 | TBD |
| ORDER-04 | TBD |
| METRIC-01 | TBD |
| METRIC-02 | TBD |
| METRIC-03 | TBD |
| METRIC-04 | TBD |
| METRIC-05 | TBD |
| METRIC-06 | TBD |
| METRIC-07 | TBD |
| METRIC-08 | TBD |
