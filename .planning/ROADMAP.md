# ROADMAP

## Archived Milestones

| Version | Name | Phases | Status |
|---------|------|--------|--------|
| v1.1 | Signal Optimization | 07-13 | ✅ Shipped 2026-03-22 |
| v1.2 | Strategy Sequence Engine | 14-15 | ✅ Shipped 2026-03-22 |

See `.planning/archive/` for full archives.

---

## Current Milestone: v1.3 Backtesting & Measurement Engine

**Goal:** Build full backtest infrastructure from schema → signal pre-computation → live alignment → recovery → engine → metrics → chart UI.
**Phases:** 7

| Phase | Name | Requirements | Status |
|---|---|---|---|
| 16 | Schema & Migration | SCHEMA-01→03 | NOT STARTED |
| 17 | Signal Pre-computation (Offline) | COMPUTE-01→04 | NOT STARTED |
| 18 | Live System Alignment | LIVE-01→03 | NOT STARTED |
| 19 | Recovery Enhancement | RECOV-01→03 | NOT STARTED |
| 20 | Backtest Engine Core | ENGINE-01→05, TRADE-01→02, QUALITY-01 | NOT STARTED |
| 21 | Metrics, API & Reporting | METRIC-01→08, API-01→06 | NOT STARTED |
| 22 | Chart UI & Dashboard | UI-01→08 | NOT STARTED |

Canonical refs: `docs/backtest/` (Phase A→F plans)

---

## Phase 16: Schema & Migration
**Requirements:** SCHEMA-01, SCHEMA-02, SCHEMA-03
**Goal:** Create TimescaleDB tables `aureus_signal_snapshots` (hypertable) and `aureus_backtest_runs`. Zero live impact.

**Success Criteria:**
1. `aureus_signal_snapshots` exists as hypertable with UNIQUE(time, symbol)
2. `aureus_backtest_runs` exists with JSONB columns for stats/trades/equity_curve
3. Index for query performance, ON CONFLICT DO UPDATE works
4. Existing live tables unaffected

Canonical refs: `docs/backtest/phase-a-schema/PLAN.md`

---

## Phase 17: Signal Pre-computation (Offline)
**Requirements:** COMPUTE-01, COMPUTE-02, COMPUTE-03, COMPUTE-04
**Goal:** Standalone `signal_computer.py` that replays historical candles, calculates all 18 signals per candle, and batch-inserts snapshots. Shared `create_signal_set()` factory and `build_snapshot()` utility.

**Success Criteria:**
1. `create_signal_set()` factory reusable from both live engine and signal_computer
2. `build_snapshot()` + `batch_insert_snapshots()` shared utilities work
3. Pre-compute 1 day (~1440 candles) completes < 10s
4. ON CONFLICT re-run produces no duplicates
5. Progress tracking via Redis key

Canonical refs: `docs/backtest/phase-b-signal-computer/PLAN.md`

---

## Phase 18: Live System Alignment
**Requirements:** LIVE-01, LIVE-02, LIVE-03
**Goal:** Live Signal Engine writes signal snapshots every candle (async, fire-and-forget). Seamless data continuity between pre-computed and live data.

**Success Criteria:**
1. Snapshot written every new candle (async, < 2ms latency impact)
2. DB error does NOT crash live system
3. Snapshot format identical to Phase 17 (shared build_snapshot)
4. Dashboard and Redis state unaffected

Canonical refs: `docs/backtest/phase-c-live-alignment/PLAN.md`

---

## Phase 19: Recovery Enhancement
**Requirements:** RECOV-01, RECOV-02, RECOV-03
**Goal:** Fix `recalculate_all_signals()` to run signals per-candle (not just last). Add snapshot gap detection to GapDetector.

**Success Criteria:**
1. Recalc runs signals per-candle with signal_history accumulation
2. Recalc 2000 candles completes < 30s
3. `find_snapshot_gaps()` detects missing snapshots
4. Auto-recovery fills snapshot gaps automatically

Canonical refs: `docs/backtest/phase-d-recovery/PLAN.md`

---

## Phase 20: Backtest Engine Core
**Requirements:** ENGINE-01→08, TRADE-01→02, QUALITY-01, PARITY-01→03
**Goal:** `BacktestRunnerV2` reads pre-computed snapshots, rebuilds state, runs strategies, manages orders (SL/TP), logs trades, calculates signal quality. Includes parity validation against live engine.

**Success Criteria:**
1. Backtest 2 weeks (~20,160 candles) completes < 15s
2. State rebuilt correctly from snapshots (atr, emas, trend, obs, events)
3. Strategy triggers occur (not empty like old engine)
4. SL/TP evaluated against H/L correctly, **deterministic SL/TP priority rule** when both hit same candle
5. **Warm-up period** (first N candles) excluded from metrics
6. **Adapter layer** for `on_bar_close()` — no Redis/live dependencies
7. Per-trade log: entry/exit time/price, direction, pnl, exit_reason
8. Signal quality scorecard per tag
9. **Parity test passes** — same data through backtest vs live engine produces identical signals/intents
10. Sample trade set with known expected metrics validates calculator

Canonical refs: `docs/backtest/phase-e-backtest-engine/PLAN.md`

---

## Phase 21: Metrics, API & Reporting
**Requirements:** METRIC-01→08, MEASURE-01→03, API-01→06
**Goal:** Calculate all metrics from trade log, persist results, expose via REST API. Includes spread/commission, benchmark, and walk-forward analysis.

**Success Criteria:**
1. Win Rate, PnL, Max Drawdown, Sharpe, Profit Factor, Avg R:R correct
2. **Spread/commission** deducted from PnL (configurable per symbol)
3. **Buy-and-hold benchmark** comparison included in report
4. **Walk-forward analysis** — train/test window rolling to detect overfitting
5. JSON + Markdown reports generated
6. Results persisted in `aureus_backtest_runs`
7. All 6 API endpoints functional
8. Pre-compute trigger + status endpoints work

Canonical refs: `docs/backtest/phase-e-backtest-engine/PLAN.md` (Steps 2-4)

---

## Phase 22: Chart UI & Dashboard
**Requirements:** UI-01→08
**Goal:** Redesign backtest page with interactive chart (signal markers, trade markers, tooltips), quality scorecard, equity curve, and pre-compute controls.

**Success Criteria:**
1. BacktestChart renders candles + signal event markers (CHOCH/BOS/Sweep)
2. Hover tooltip shows metadata + context + outcome (glassmorphism)
3. Trade entry/exit markers + SL/TP dashed lines
4. SignalQualityCard with color-coded win_rate bars + letter grades
5. EquityCurve via lightweight-charts with drawdown shading
6. Pre-compute trigger + progress bar functional
7. Click signal type → filter markers on chart
8. Responsive layout

Canonical refs: `docs/backtest/phase-f-chart-ui/PLAN.md`
