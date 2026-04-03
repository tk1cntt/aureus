---
status: partial
phase: 15.5-strategy-quality-assurance
source: 15.5-01-PLAN.md, 15.5-02-PLAN.md, 15.5-03-PLAN.md, 15.5-04-PLAN.md
started: 2026-03-23T20:14:11+07:00
updated: 2026-03-24T00:51:00+07:00
---

## Current Test

number: 6
name: Replay Persistence Schema and Results Are Queryable
expected: |
  After running `psql $DATABASE_URL -f scripts/create_replay_table.sql` and then
  `python scripts/strategy_replay.py` (without `--no-persist`), querying
  `aureus_strategy_replay_results` should return recent rows with symbol, strategy,
  counts, and deterministic flag.
awaiting: user response

## Tests

### 1. Fixture Export Script Produces Frozen Candle CSVs
expected: From `services/aureus-signal/`, running `python scripts/export_candle_fixtures.py` should create fixture files in `tests/fixtures/` (including `candles_XAUUSD.csv` and `candles_AUDUSD.csv`) with header `t,o,h,l,c,v` and up to 2000 data rows each.
result: pass

### 2. Context Filter Unit Tests Pass
expected: Running `python -m pytest tests/test_strategy_context_filters.py -v --tb=short` from `services/aureus-signal/` should pass and validate context filter behavior for `TREND_CONT`, `SESSION_SWEEP`, and `ORDER_FLOW_DOM`.
result: pass

### 3. Strategy Determinism Tests Pass
expected: Running `python -m pytest tests/test_strategy_determinism.py -v --tb=short` from `services/aureus-signal/` should pass and show deterministic outcomes across independent strategy/registry runs.
result: pass

### 4. Full Pipeline Scenario Tests Pass
expected: Running `python -m pytest tests/test_strategy_scenario.py -v --tb=short` from `services/aureus-signal/` should pass and confirm full signal→strategy replay behavior on fixture data with valid reject reason handling and deterministic replay.
result: pass

### 5. Replay CLI Works in Single Mode
expected: Running `python scripts/strategy_replay.py --symbol XAUUSD --strategy TREND_CONT --no-persist --skip-determinism --bars 250` from `services/aureus-signal/` should complete successfully and print a metrics summary (bars, triggers, rejects, reason breakdown).
result: pass

### 6. Replay Persistence Schema and Results Are Queryable
expected: After running `psql $DATABASE_URL -f scripts/create_replay_table.sql` and then `python scripts/strategy_replay.py` (without `--no-persist`), querying `aureus_strategy_replay_results` should return recent rows with symbol, strategy, counts, and deterministic flag.
result: blocked
blocked_by: server
reason: "DATABASE_URL is not set, so persistence verification could not be executed."

## Summary

total: 6
passed: 5
issues: 0
pending: 0
skipped: 0
blocked: 1

## Gaps

[none yet]
