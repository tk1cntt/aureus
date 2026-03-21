# Phase 07 Verification Plan: Signal Trend Optimization

## Automated Tests

### 1. Unit Tests (`tests/test_trend*.py`)
- **Sideways Matrix Logic:** Inject `state_obj` with 2 unmitigated Bullish and 2 Bearish OBs. Verify `regime="SIDEWAYS"` and `htf_trend="NEUTRAL"`.
- **Trend Up Logic:** Inject `state_obj` with 2 Bullish OBs and 0 Bearish, with `price > ema`. Verify `regime="TREND_UP"` and `htf_trend="BULLISH"`.
- **Trend Down Logic:** Inject 0 Bullish, 2 Bearish, `price < ema`. Verify `BEARISH`.
- **Divergence Logic (News Sweep):** Inject 2 Bullish, 0 Bearish, but `price < ema`. Verify `NEUTRAL`.
- **Mitigated OB Ignored:** Inject 2 Bullish (one mitigated, one unmitigated). Verify it counts as `1` Bullish OB and fails to trigger trend.

### 2. Integration Tests
- **Candle Integration:** `pytest services/aureus-signal/tests/test_trend_integration*.py` (ensure sweeping or structural signals don't crash when trend format changes).

### 3. Coverage Gate
- `python -m pytest services/aureus-signal/tests/ -k "test_trend" --cov=services/aureus-signal/engine/signals/trend.py --cov-report=term-missing -q`
- Must achieve >= 90% coverage for `trend.py`.

## Sign-off Checklist
- [ ] Matrix rules (N=2, M>=2) implemented correctly.
- [ ] Divergent setups explicitly return NEUTRAL.
- [ ] Existing downstream tests that expect the `trend` dictionary format are updated (`slope` -> `delta`/`ob_count`).
- [ ] All verification commands pass successfully.
