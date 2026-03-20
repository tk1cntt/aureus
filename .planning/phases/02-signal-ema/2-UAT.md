---
status: completed
phase: 02-signal-ema
source: 02-01-PLAN.md, 02-VALIDATION.md
started: 2026-03-20T22:53:16+07:00
updated: 2026-03-20T23:21:13+07:00
---

## Current Test

number: 4
name: Focused EMA verification gate remains green
expected: |
  Running focused command `python -m pytest tests/test_ema_o1.py`
  `tests/test_ema_integration_execute_signals_for_candle.py --cov=engine.signals.ema`
  `--cov-report=term-missing -q` returns all pass and coverage >= 80%.
awaiting: none

## Tests

### 1. EMA emits directional signal after warmup
expected: Trigger a short replay/stream with EMA(21) enabled and at least 23 candles; output includes `ema_21_up|ema_21_down` and each emitted EMA event includes valid `t`.
result: [passed]

### 2. EMA state progresses candle-to-candle
expected: After warmup, processing one new candle changes cached `state.emas[21]["current"]` (not frozen/reused incorrectly).
result: [passed]

### 3. Malformed cached EMA state falls back safely
expected: If EMA cache for period 21 is malformed (missing `current`), calculation still succeeds via deterministic fallback and rewrites cache with `current`, `prev`, `slope`.
result: [passed]

### 4. Focused EMA verification gate remains green
expected: Running focused command `python -m pytest tests/test_ema_o1.py tests/test_ema_integration_execute_signals_for_candle.py --cov=engine.signals.ema --cov-report=term-missing -q` returns all pass and coverage >= 80%.
result: [passed]

## Summary

total: 4
passed: 4
issues: 0
pending: 0
skipped: 0

## Gaps

[none]
