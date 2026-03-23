# ROADMAP

## Archived Milestones

| Version | Name | Phases | Status |
|---------|------|--------|--------|
| v1.1 | Signal Optimization | 07-13 | ✅ Shipped 2026-03-22 |
| v1.2 | Strategy Sequence Engine | 14-15 | ✅ Shipped 2026-03-22 |

See `.planning/archive/` for full archives.

---

## Current Milestone: v1.3 Backtesting & Measurement Engine

**Goal:** Validate strategy quality independently → integrate NautilusTrader BacktestEngine → persist results → Custom UI + Grafana.

**Phases:** 6

| Phase | Name | Requirements | Status |
|---|---|---|---|
| 15.5 | 0/4 | Planned    |  |
| 16 | Schema & Data Loader | SCHEMA-01→04 | NOT STARTED |
| 17 | Signal Actor & Strategy Adapter | NAUTILUS-01→06, PARITY-01→03 | NOT STARTED |
| 18 | Metrics & Result Persistence | METRIC-01→08, QUALITY-01, MEASURE-01→03 | NOT STARTED |
| 19 | Custom UI & Dashboard | UI-01→08, API-01→06 | NOT STARTED |
| 20 | Grafana Dashboards & Live Alignment | GRAFANA-01→03, LIVE-01→03, RECOV-01→03 | NOT STARTED |

**Architecture ref:** integration plan (`implementation_plan.md` in conversation artifacts)

---

## Phase 15.5: Strategy Quality Assurance

**Requirements:** STRATQA-01→05
**Goal:** Validate strategy correctness and quality INDEPENDENTLY before Nautilus integration. Establish baselines so that poor backtest results can be attributed correctly (strategy problem vs integration problem).

**Rationale:** v1.2 built strategies but has no quality validation. Without baselines, integrating with Nautilus makes debugging impossible — unclear if bad results come from strategy config, signal pipeline, or Nautilus adapter.

**Success Criteria:**
1. Seed strategy unit tests — all 3 strategies (TREND_CONT, SESSION_SWEEP, ORDER_FLOW_DOM) tested with context_filters + sequence
2. Scenario tests — strategies run through real signal pipeline on curated candle datasets, verify triggers/rejects
3. Determinism test — same data → identical results on 2 runs
4. `strategy_replay.py` — standalone replay tool (candle→signals→strategy→intents), no Nautilus dependency
5. Baseline report for XAUUSD 30 days — trigger count, trigger rate, score distribution, signal contribution
6. Baseline artifacts persisted as regression reference

---

## Phase 16: Schema & Data Loader

**Requirements:** SCHEMA-01, SCHEMA-02, SCHEMA-03, SCHEMA-04
**Goal:** Create TimescaleDB tables for backtest results + build data loader that reads `aureus_candles` → converts to Nautilus `Bar` objects via `BarDataWrangler`.

**Success Criteria:**
1. `aureus_backtest_runs`, `aureus_backtest_trades`, `aureus_backtest_equity`, `aureus_backtest_signal_quality` tables exist
2. Data loader reads from `aureus_candles` → produces list of Nautilus `Bar` objects
3. `BarDataWrangler.process()` with correct `ts_init_delta=0` (close-timestamped bars)
4. Instrument definition (XAUUSD CurrencyPair) with correct price/size precision
5. Existing live tables unaffected

---

## Phase 17: Signal Actor & Strategy Adapter

**Requirements:** NAUTILUS-01→06, PARITY-01→03
**Goal:** `AureusSignalActor` (Nautilus Actor) runs all 18 Aureus signals per bar via `msg_bus`. `AureusStrategyAdapter` (Nautilus Strategy) wraps any `BaseStrategy` and submits bracket orders. Backtest runner script ties everything together.

**Success Criteria:**
1. `AureusSignalActor.on_bar()` runs full signal pipeline (same code as live engine)
2. Signal snapshots published via `msg_bus` using Custom Data (`AureusSignalSnapshot`)
3. `AureusStrategyAdapter` receives snapshots, calls `on_bar_close()` → `validate_entry()` → `build_order_plan()`
4. Bracket orders (entry + SL + TP) submitted via `self.submit_order_list()`
5. Nautilus handles SL/TP matching via O→H→L→C bar execution
6. Backtest runner script: configure engine + venue + add data + run + extract results
7. **Parity test passes** — Actor trigger count + timestamps match Phase 15.5 baseline exactly
8. **Deterministic** results with `random_seed`

Canonical refs: existing `aureus-nautilus-node/` as adapter pattern reference

---

## Phase 18: Metrics & Result Persistence

**Requirements:** METRIC-01→08, QUALITY-01, MEASURE-01→03
**Goal:** Custom Nautilus `PortfolioStatistic` subclasses for Aureus-specific metrics. Persist results (trades, equity curve, stats, signal quality) to TimescaleDB.

**Success Criteria:**
1. Win Rate, PnL, Max Drawdown, Sharpe, Profit Factor, Avg R:R calculated correctly
2. Custom `PortfolioStatistic` subclasses registered with `PortfolioAnalyzer`
3. Spread/commission deducted via Nautilus `FillModel` config or post-processing
4. Buy-and-hold benchmark comparison included
5. Walk-forward analysis (train/test window rolling)
6. Signal Quality Calculator — per signal tag: count, win_rate, avg_pips, quality_grade
7. Results persisted to `aureus_backtest_runs`, `aureus_backtest_trades`, `aureus_backtest_equity`, `aureus_backtest_signal_quality`
8. JSON + Markdown report generation

---

## Phase 19: Custom UI & Dashboard

**Requirements:** UI-01→08, API-01→06
**Goal:** Custom web UI for backtest management: runner form, candlestick chart with trade/signal overlays, equity curve, signal quality scorecard. REST API endpoints.

**Success Criteria:**
1. Backtest runner form: select symbol, strategy, date range, venue config
2. BacktestChart renders candles + signal markers (CHOCH/BOS/Sweep) + trade markers
3. Hover tooltip with metadata + context + outcome
4. Trade entry/exit markers + SL/TP dashed lines
5. SignalQualityCard with color-coded win_rate bars + letter grades
6. EquityCurve with drawdown shading
7. All 6 API endpoints functional (trigger backtest, list runs, chart data, snapshot detail, pre-compute trigger/status)
8. Responsive layout

---

## Phase 20: Grafana Dashboards & Live Alignment

**Requirements:** GRAFANA-01→03, LIVE-01→03, RECOV-01→03
**Goal:** Add TimescaleDB datasource to Grafana + supplementary dashboards. Live signal snapshot writes + recovery enhancement.

**Success Criteria:**
1. TimescaleDB datasource provisioned in Grafana
2. "Backtest Performance" dashboard: aggregate stats, equity curves, strategy heatmaps
3. "Signal Quality" dashboard: per-signal win rates, contribution metrics
4. Live engine writes signal snapshots async (fire-and-forget, < 2ms impact)
5. Snapshot gap detection + auto-recovery
6. Data continuity between pre-computed and live snapshots
