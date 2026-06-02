# TPO Detector Signal Debug — Root Cause Analysis

## Pipeline Trace

### Stage A: TPO Computation — WORKING

- `tpo.py:TPOSignal.calculate()` (line 37) runs in `execute_signals_for_candle()` via `signal_calc.calculate(df, state, ...)`.
- Produces `tpo_d0`, `tpo_d1`, `tpo_h1`, `tpo_m30` blocks with POC/VAH/VAL/shape.
- Result tag `"tpo"` is emitted and mapped to candle record via `map_signal_to_candle_record()`.
- **Verdict: TPO computation runs correctly in live engine.**

### Stage B: Detectors — WORKING (in isolation)

- `tpo_detectors.py` contains 3 detectors: `VARejectionDetector`, `VABreakoutAcceptanceDetector`, `TrendPullbackDetector`.
- Each detector receives a context dict with `timeframes` (D1/H1/M30) and `bias`, then checks price-level relations.
- All 3 detectors are called from `_maybe_emit_tpo_strategy_tags()` in `live_engine.py` line 103-106.
- **Verdict: Detectors execute and produce candidates with `valid=True/False`, `setup`, `side`, `score`.**

### Stage C: Strategy Signal Bridge — PARTIALLY WORKING (tags stored but not in event stream)

- `tpo_strategy.py:tpo_strategy_tags_from_candidates()` (line 11) maps `(setup, side)` pairs to tags like `tpo_va_rejection_bull` via `TPO_TAG_MAPPING` (line 1-8).
- Tags are stored in `state.transient_signals[tag]` at `live_engine.py` line 110.
- **BUG #1: Tags are NOT added to the candle record's `_events_map`.**
  - `_maybe_emit_tpo_strategy_tags()` only writes to `state.transient_signals`.
  - It does NOT call `state.map_signal_to_candle_record(record, tag=tag, ...)`.
  - The `record` parameter is not even passed to the function.
- The sequence evaluator (`template.py:_evaluate_sequence()`, line 497) reads events from `record.to_dict()["signals"]["events"]`, NOT from `transient_signals`.
- **Verdict: Tags exist in `transient_signals` but never reach the sequence evaluator's event source.**

### Stage D: Context Filter — NOT IMPLEMENTED (silently passes)

- All 6 TPO strategies define `context_filters: [{"type": "tpo_context", ...}]` in `seed_strategies.py` lines 601, 616, 631, 643, 655, 667.
- `template.py:_evaluate_context()` (line 50) handles: `trend_alignment`, `session_active`, `ob_imbalance`, `ema_alignment`, `ema_relation`, `trend_cont_poc_cisd`, `cisd_consensus`.
- **BUG #2: No handler for `f_type == "tpo_context"`.**
  - Unrecognized filter types fall through the `if/elif` chain without being added to `failed`.
  - `passed = len(failed) == 0` returns `True` — the filter always passes.
- This means ALL TPO strategies pass context evaluation regardless of bias/confidence requirements.
- **Verdict: Context filter is dead code. It never blocks, but also never validates.**

### Stage E: Sequence Matching — BLOCKED (never finds TPO tags)

- `template.py:_evaluate_sequence()` iterates `log_signal_normalize` records (line 479-486).
- For each record, it reads `record["signals"]["events"]` (line 498).
- It matches event tags against `self.sequence[].tag` (e.g., `tpo_va_rejection_bull`).
- Since TPO tags are only in `transient_signals` and NOT in candle record events, the sequence never matches.
- **Verdict: Sequence matching is the terminal blocker. TPO tags never appear in the event stream.**

## Root Cause Summary

**Primary root cause (Stage C):** `_maybe_emit_tpo_strategy_tags()` in `live_engine.py` line 94-116 stores TPO strategy tags only in `state.transient_signals` but does not add them to the candle record's events via `map_signal_to_candle_record()`. The sequence evaluator reads from candle record events, so TPO tags are invisible to it.

**Secondary issue (Stage D):** The `tpo_context` filter type is not implemented in `template.py:_evaluate_context()`. It silently passes, meaning TPO strategies never validate bias/confidence pre-conditions even when the primary bug is fixed.

## Fixes Applied

### Fix 1 — Pass `record` to `_maybe_emit_tpo_strategy_tags` and map tags to candle record

**File:** `services/aureus-signal/engine/live_engine.py` line 94, 114, 170

- Function signature changed to accept `record=None`.
- After storing tag in `transient_signals`, also calls `state.map_signal_to_candle_record(record, tag=tag, value=result)`.
- Call site updated to pass `record=record`.

### Fix 2 — Add `tpo_context` handler in `template.py:_evaluate_context()`

**File:** `services/aureus-signal/engine/strategies/template.py` after line 304

- New `elif f_type == "tpo_context"` block.
- Reads `tpo_profile` from state, builds context via `TPOContextBuilder`, checks D1 bias against allowed bias list from strategy config.

## Tests

All 22 existing TPO tests pass (post-fix). Full suite: 695 passed, 9 failed (all pre-existing, unrelated to TPO).
