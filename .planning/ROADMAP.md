# ROADMAP

## Archived Milestones

| Version | Name | Phases | Status |
|---------|------|--------|--------|
| v1.1 | Signal Optimization | 07-13 | ✅ Shipped 2021-03-22 |
| v1.2 | Strategy Sequence Engine | 14-15 | ✅ Shipped 2021-03-22 |

See `.planning/archive/` for full archives.

---

## Current Milestone: v1.3 Backtesting & Measurement Engine

**Goal:** Validate strategy quality independently → integrate NautilusTrader BacktestEngine → persist results → Custom UI + Grafana.

**Phases:** 9

| Phase | Name | Requirements | Status |
|---|---|---|---|
| 15.5 | Strategy Quality Assurance | STRATQA-01→05 | PLANNED |
| 15.6 | Sweep rule & AI sentiment stabilization | Internal stabilization | ✅ COMPLETE |
| 15.7 | Sequence enabled but no-entry trigger diagnosis | Internal strategy debug/instrumentation | PLANNED |
| 15.8 | Signal→Nautilus order-open delivery diagnosis & contract alignment | Internal runtime integration debug/alignment | PLANNED |
| 15.9 | Enrich signal_history with semantic metadata | Internal semantic observability | DONE |
| 15.10 | Pydantic Signal History Refactoring | Refactor signal history to strong-typed Pydantic classes | EXECUTING (REOPENED) |
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

### Phase 15.6: Update SWEEP detected rules for OB states and analyze sentiment mapping via _AI_TAG_TO_TRIGGER

**Goal:** Ổn định chất lượng trigger event cho sweep lifecycle và chốt rõ vai trò của sentiment AI để tránh sửa sai hướng.
**Requirements**: Internal stabilization (sweep/event-policy/logging observability)
**Depends on:** Phase 15.5
**Plans:** 1/1 plans complete

Plans:
- [x] Cập nhật rule `SWEEP DETECTED` theo OB states và verify bằng test
- [x] Điều tra warning `missing origin_timestamp` trong live path và chốt root-cause
- [x] Phân tích mapping sentiment qua `_AI_TAG_TO_TRIGGER`, xác nhận sentiment là dự đoán AI nên không thay đổi logic

### Phase 15.7: Strategy sequences enabled nhưng không trigger vào lệnh

**Goal:** Phân tích và xác định nguyên nhân tại sao strategy có sequence conditions đều bật/đạt nhưng không sinh trade intent hoặc không đi tới order submission.
**Requirements**: Internal strategy debug/instrumentation (entry gating path observability)
**Depends on:** Phase 15.6
**Plans:** 0/1 plans complete

Plans:
- [ ] Thảo luận và chốt giả thuyết nguyên nhân chính trên luồng `on_bar_close` → `validate_entry` → `build_order_plan`
- [ ] Xác định điểm cần instrument/log để tách bạch lỗi do signal, context_filters, sequence matcher hay risk/execution guard
- [ ] Tạo context đầu vào cho research/planning phase fix

### Phase 15.8: Signal→Nautilus order-open delivery diagnosis & contract alignment

**Goal:** Khoanh vùng và chốt nguyên nhân khiến trigger/order-open từ `aureus-signal` không đi được tới `aureus-nautilus-node`, sau đó chuẩn hóa contract runtime để order-open được nhận và xử lý nhất quán theo symbol thực tế.
**Requirements**: Internal runtime integration debug/alignment (stream wiring, symbol routing, order payload contract)
**Depends on:** Phase 15.7
**Plans:** 0/1 plans complete

Plans:
- [ ] Xác nhận điểm đứt luồng thực tế trong chain `aureus-signal` → Redis stream `:orders` → `aureus-nautilus-node`/bridge consumer
- [ ] Chốt contract stream/symbol (không hardcode `XAUUSD`, hỗ trợ symbol runtime như `ETHUSD`)
- [ ] Chốt contract payload `ORDER_OPEN` giữa producer/consumer (mapping trường bắt buộc, validation gates, reject-reason observability)
- [ ] Tạo phase context `15.8-CONTEXT.md` làm đầu vào cho research/planning phase fix

### Phase 15.9: Enrich signal_history with semantic metadata

**Goal:** Mở rộng mỗi record trong `signal_history` để giải thích nghiệp vụ trực tiếp tại thời điểm signal xuất hiện (category, value, explain, inputs) hỗ trợ AI narrative validation.
**Requirements**: Internal semantic observability
**Depends on:** Phase 15.8
**Plans:** 0/0 plans complete

Plans:
- [ ] Thêm metadata category, value, explain, inputs vào signal_history và giữ tương thích ngược
- [ ] Cập nhật call-sites trong engine (live, backtest, signal_computer)
- [ ] Điều chỉnh consumer (ai_validator, UI data pipeline) để tương thích và hiển thị metadata mới

### Phase 15.10: Pydantic Signal History Refactoring

**Goal:** Ổn định lại contract `signal_history/log_signal` sau vòng rollback cục bộ, đảm bảo đồng nhất giữa `state.py` và các call-sites runtime trước khi tiếp tục refactor kiểu mạnh Pydantic.
**Requirements**: Contract stabilization for safe continuation of type-safety refactor.
**Depends on:** Phase 15.9
**Plans:** 1/3 plans tracked (execution reopened)

Plans:
- [x] Đồng bộ trạng thái hiện tại vào `.planning/STATE.md`, `.planning/ROADMAP.md`, `.planning/phases/15.10-refactor-signal-history/*`
- [x] Ghi nhận drift hiện tại: `state.log_signal` legacy signature vs metadata kwargs call-sites trong `live_engine.py`, `backtest_engine.py`, `signal_computer.py`
- [x] Chốt quick verification hiện tại: `pytest tests/test_decision_trace_schema.py tests/test_signal_contract_normalization.py -q` → 19 passed
- [ ] Plan 02: normalize `signal_history` theo canonical schema (`t/symbol/timeframe/state/events`) dựa trên sample `normalize_signal_history`
- [ ] Plan 03: thực thi 2 todo pending — migrate `market_regime` → `htf_trend` và điều tra/fix thiếu event `sweep`/`MITIGATED` trong `signal_history_normalized`

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
