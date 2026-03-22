# ROADMAP

## Archived Milestones

| Version | Name | Phases | Status |
|---------|------|--------|--------|
| v1.1 | Signal Optimization | 07-13 | ✅ Shipped 2026-03-22 |
| v1.2 | Strategy Sequence Engine | 14-15 | ✅ Shipped 2026-03-22 |

See `.planning/archive/` for full archives.

---

## Current Milestone: v1.3 Backtesting & Measurement Engine

**Goal:** Build a backtesting engine to simulate strategy execution on historical data, validate SL/TP logic, and output measurable performance metrics.
**Phases:** 3

| Phase | Name | Requirements | Status |
|---|---|---|---|
| 16 | Data Loading & Candle Replay | DATA-01, DATA-02, DATA-03 | NOT STARTED |
| 17 | Order Simulation & Trade Log | STRAT-01, STRAT-02, STRAT-03, ORDER-01, ORDER-02, ORDER-03, ORDER-04 | NOT STARTED |
| 18 | Metrics Engine & Reporting | METRIC-01 → METRIC-08 | NOT STARTED |

---

## Phase 16: Data Loading & Candle Replay
**Requirements:** DATA-01, DATA-02, DATA-03
**Goal:** Build data loaders (DB + CSV/JSON) that produce a standardized candle DataFrame, validate continuity, and replay candles one-by-one through a strategy's `on_bar_close` pipeline.

**Success Criteria:**
1. `CandleLoader` loads candles from PostgreSQL with symbol/timeframe/date range filters.
2. `CandleLoader` loads candles from CSV/JSON files with the same output format.
3. Validation rejects datasets with gaps or duplicate timestamps.
4. Replay loop feeds candles sequentially, building state progressively (mimicking live engine).

Canonical refs: `services/aureus-signal/engine/strategies/template.py`, `services/aureus-signal/engine/strategies/base.py`

---

## Phase 17: Order Simulation & Trade Log
**Requirements:** STRAT-01, STRAT-02, STRAT-03, ORDER-01, ORDER-02, ORDER-03, ORDER-04
**Goal:** Build a mock order executor that opens positions from strategy intents, evaluates SL/TP against candle H/L, and logs every trade with full detail.

**Success Criteria:**
1. Any `BaseStrategy` subclass can be plugged into the backtester (not hard-coded to TemplateStrategy).
2. Strategy's `on_bar_close` → `build_order_plan` pipeline produces intents identical to live engine.
3. Mock executor opens position at entry price, tracks SL/TP/trailing per subsequent candle.
4. Each trade logged: entry_time, exit_time, entry_price, exit_price, direction, pnl, exit_reason (SL/TP/SESSION_END).
5. Context filters and sequence matching produce identical results to live engine.

Canonical refs: `services/aureus-signal/engine/strategies/template.py`, `services/aureus-signal/engine/strategies/base.py`

---

## Phase 18: Metrics Engine & Reporting
**Requirements:** METRIC-01 → METRIC-08
**Goal:** Calculate performance metrics from the trade log and output comprehensive reports in JSON + markdown format.

**Success Criteria:**
1. Win Rate calculated correctly (winning / total trades).
2. Total PnL reflects sum of all trade PnLs.
3. Max Drawdown measured as peak-to-trough equity decline.
4. Sharpe Ratio calculated using trade returns and risk-free rate.
5. Profit Factor = gross profit / gross loss.
6. Average R:R = average (actual reward / planned risk) per trade.
7. JSON report contains all metrics + per-trade log.
8. Markdown report is human-readable with summary table + trade detail.
