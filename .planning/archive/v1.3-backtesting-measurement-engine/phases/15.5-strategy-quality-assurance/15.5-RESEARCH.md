# Phase 15.5: Strategy Quality Assurance — Research

**Researched:** 2026-03-23
**Researcher:** Agent
**Status:** Complete

## Research Question

> What do I need to know to PLAN this phase well?

---

## 1. Replay Pipeline Architecture

### Reusable Core Functions

The live engine pipeline can be reused for offline replay with zero modifications:

| Function | Module | Replay Role |
|---|---|---|
| `create_signal_set(symbol, cfg)` | `engine/signal_factory.py` | Creates all 17 signal calculators in correct execution order |
| `execute_signals_for_candle(signals, df, state, symbol, redis_client)` | `engine/live_engine.py` | Runs all signals per candle. **Accepts `redis_client=None`** — safe for offline |
| `StrategyRegistry.evaluate_all(df, signals, state_obj)` | `engine/strategies/registry.py` | Runs phased contract: `on_bar_close` → `validate_entry` → `build_order_plan` |
| `SymbolState(symbol)` | `engine/state.py` | Full state tracking — self-contained, no external deps |
| `seed_system_strategies(pool)` | `engine/strategies/seed_strategies.py` | 3 hardcoded strategy configs |

### Replay Loop (Pseudocode)

```python
signals = create_signal_set(symbol, symbol_config)
state = SymbolState(symbol)
registry = StrategyRegistry()
registry.register(TemplateStrategy(config))

for candle in candle_stream:
    df = window_manager.update(symbol, candle)
    state.transient_signals = {}

    execute_signals_for_candle(signals, df, state, symbol, redis_client=None)
    accepted = registry.evaluate_all(df, signals, state)
    rejections = registry.get_rejections(clear=True)
    # Collect results...
```

### Key Constraints
- `WindowManager.max_window=2000` — rolling window size, replay tool should match
- Signal execution ORDER matters (dict insertion order in `signal_factory.py`): structure_processor before choch_up/choch_down
- `state.transient_signals = {}` MUST be cleared each candle cycle
- `state.log_signal(tag, timestamp)` caps at 1000 entries — sufficient for 2000-bar export

---

## 2. Strategy Architecture Deep Dive

### 3-Pillar Framework (TemplateStrategy)

**Pillar 1 — WHAT** (`_evaluate_context`):
- 4 filter types: `trend_alignment`, `session_active`, `ob_imbalance`, `ema_alignment`
- Reads from `SymbolState`: `htf_trend`, `current_session`, `obs`, `emas`

**Pillar 2 — WHEN** (`_evaluate_sequence`):
- O(1) state machine tracking `current_step_index`, `last_matched_candle_idx`
- Features: tag matching, optional skip, `max_wait` timeout, `reset_signals` reset
- Progress persisted in `state_obj.strategy_progress[strategy_name]`

**Pillar 3 — HOW** (`build_order_plan`):
- Order params from `trade_execution` config (size, SL, TP, trailing, early_exits)

### Phased Contract Flow
```
on_bar_close(context) → intent
  ├── _evaluate_context(state)  → {passed, failed_filters}
  ├── _evaluate_sequence(df, state) → {score, missing_required, progress}
  └── reason_code: OK | CONTEXT_FILTER_FAILED | SEQUENCE_NOT_MATCHED | BACKFILL_NOT_READY

validate_entry(intent, context) → {is_valid, reason_code}
build_order_plan(intent, context) → {direction, size, sl, tp, trailing, ...}
```

### Seed Strategy Configs (from `seed_strategies.py`)

| Strategy | Context Filters | Sequence Tags | Min Score |
|---|---|---|---|
| TREND_CONT | trend=BULLISH, session=LON/NY/OVERLAP, ema21_slope=POS | choch_bull(4.0) → sweep_bull(5.0) → fvg_bull(2.0?) | 6.5 |
| SESSION_SWEEP | trend=BULLISH, session=LON/NY | choch_bull(3.5) → sweep_bull(5.0) | 6.0 |
| ORDER_FLOW_DOM | trend=BULLISH, ob_imbalance≥3.0, session=LON/NY/OVERLAP | sweep_bull(7.0) | 7.0 |

**All are BULLISH only.** Future BEARISH variants are deferred.

---

## 3. Existing Test Patterns

### Unit Tests (Reusable for Strategy Unit Tests)

`test_template_strategy.py` (220 lines, 8 tests):
- `MockState` class — minimal: `signal_history=[], strategy_progress={}`
- `create_mock_df(t_val)` — single-row DataFrame
- Tests: sequence match, reset priority, timeout, optional skip, evaluate, on_bar_close, validate_entry, build_order_plan

**Gap:** No tests for `_evaluate_context` (context_filters). Phase 15.5 MUST add these.

### Parity Tests (`_o1` pattern)

`test_atr_o1.py` pattern:
- `np.random.seed(42)` for deterministic data
- Run signal on known data, compare against ground truth (pandas reference impl)
- `test_deterministic_repeatability_for_same_series` — two independent runs must produce identical results

**Reusable pattern for strategy determinism tests.**

### Integration Tests (`_integration_execute_signals_for_candle` pattern)

13 existing files covering all signals through `execute_signals_for_candle()`.

**Reusable pattern for scenario tests — run strategies through full signal pipeline on curated data.**

---

## 4. Data Export & Fixture Strategy

### Source: `aureus_candles` TimescaleDB Table
```sql
SELECT time, symbol, open, high, low, close, volume, timeframe
FROM aureus_candles
WHERE symbol = $1 AND timeframe = 'M1'
ORDER BY time ASC
LIMIT 2000
```

### Export Format (CSV)
```csv
t,o,h,l,c,v
1710000000,2050.50,2055.00,2048.00,2053.00,1500
```

- `t` as unix timestamp (int), OHLCV as floats
- One file per symbol: `tests/fixtures/candles_{symbol}.csv`
- Committed to repo as frozen test data

### Symbol Config
- Replay tool loads `symbols.json` for per-symbol params (digits, point, pivot config)
- `create_signal_set(symbol, config)` handles parameterization

---

## 5. Replay Result Persistence

### Proposed Table: `aureus_strategy_replay_results`

```sql
CREATE TABLE aureus_strategy_replay_results (
    id SERIAL PRIMARY KEY,
    run_id UUID NOT NULL DEFAULT gen_random_uuid(),
    symbol TEXT NOT NULL,
    strategy_name TEXT NOT NULL,
    strategy_config JSONB,
    bar_count INT,
    trigger_count INT,
    trigger_rate FLOAT,
    reject_count INT,
    reject_reasons JSONB,       -- {reason_code: count}
    score_min FLOAT,
    score_max FLOAT,
    score_avg FLOAT,
    signal_contribution JSONB,  -- {tag: trigger_count}
    session_distribution JSONB, -- {session: trigger_count}
    context_filter_stats JSONB, -- {passed: N, failed: N, failed_breakdown: {...}}
    deterministic BOOLEAN,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 6. Risk & Edge Cases

| Risk | Mitigation |
|---|---|
| Signal order dependency | Use `create_signal_set()` directly — preserves dict insertion order |
| Redis-dependent signals | `execute_signals_for_candle()` accepts `None` — verified in code |
| `SymbolState.news_events` | Set to `[]` in replay — news is non-deterministic |
| `state.log_signal` caps at 1000 | Sufficient for 2000-bar window; not a risk |
| `backfill_status` check in `on_bar_close` | Replay context must set `backfill_status: "READY"` |
| FVG signals behind feature flag | Set `AUREUS_ENABLE_FVG_SIGNAL=1` env var if needed in replay |

---

## Validation Architecture

### Layer 1: Strategy Unit Tests
- Context filter evaluation per strategy
- Sequence matching edge cases (timeout, reset, optional skip)
- Score threshold boundaries
- **Determinism:** Two runs on same data → identical results

### Layer 2: Scenario Tests (Integration)
- Load CSV fixture data into DataFrame
- Run `execute_signals_for_candle()` → `evaluate_all()` through full pipeline
- Assert: trigger count > 0 for known bullish data, reject reasons match expectations
- Market scenario variants: bullish breakout, ranging market, bearish reversal

### Layer 3: Replay Tool + Baseline
- CLI tool with argparse: single/batch/full matrix modes
- Persist Tier 2 metrics to TimescaleDB
- Baseline comparison for regression detection

---

*Phase: 15.5-strategy-quality-assurance*
*Research completed: 2026-03-23*
