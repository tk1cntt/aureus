# Phase 15.17: Decouple Strategy Engine — UAT

**Phase:** 15.17-decouple-strategy-engine
**Date:** 2026-04-01
**Status:** PASS (with cleanup applied)

## Test Results

### T1: Aggregator emits signal stream ✅
**Expectation:** `live_engine.py` serializes signal payload and pushes to `aureus:stream:{symbol}:signals` after `execute_signals_for_candle`.
**Result:** PASS — Line 637 contains `xadd(f"aureus:stream:{symbol}:signals", ...)` with payload including `log_signal_normalize`, `current_signal`, `transient_signals`, `swing_points`, `signals_snapshot`, and OHLCV data. `maxlen=1000` applied.

### T2: Aggregator no longer evaluates strategies inline ✅
**Expectation:** `live_engine.py` main loop does NOT contain `evaluate_all`, `process_triggers`, or inline trade management.
**Result:** PASS — All strategy evaluation, trade manager, and rejection emission logic removed from main loop (former lines 692-773). Only `evaluate_all` calls remain in warmup (line 411) and recalculation (line 1088) paths, which is correct behavior.

### T3: State persistence remains in aggregator ✅
**Expectation:** `aureus:state:{symbol}` Redis writes and TimescaleDB snapshot logic stay in `live_engine.py`.
**Result:** PASS — `r.set(f"aureus:state:{symbol}", ...)` at line 730. `insert_single_snapshot` at line 739. Checkpoint marker at line 747. All intact.

### T4: Strategy Executor consumes signal stream ✅
**Expectation:** `strategy_executor.py` connects to `aureus:stream:{symbol}:signals` via consumer group and runs `evaluate_all`.
**Result:** PASS — Consumer group `aureus-strategy-executor-group` created. `run_strategy_executor()` contains async loop with `xreadgroup`, JSON deserialization, `SymbolState` reconstruction, `evaluate_all` call, enrichment, rejection emission, `trade_manager.update_orders`, `process_triggers`, and `ai_queue` integration.

### T5: Executor has observability & metadata enrichment ✅
**Expectation:** Version metadata, snapshot capture, and rejection logging present in executor.
**Result:** PASS — `enrich_strategy_decisions_with_contract_metadata` and `enrich_registry_rejections_with_contract_metadata` present. `emit_registry_rejections` publishes to `aureus:stream:{symbol}:orders`.

### T6: Executor has trade/order simulation & AI trigger ✅
**Expectation:** `trade_manager.update_orders`, `process_triggers`, and `ai_queue` present in executor.
**Result:** PASS — All three confirmed in executor main loop.

### T7: Dead code cleaned from aggregator ✅
**Expectation:** Functions moved to executor should not remain as dead code in aggregator.
**Result:** PASS — Removed `enrich_strategy_decisions_with_contract_metadata`, `enrich_registry_rejections_with_contract_metadata`, and `emit_registry_rejections` from `live_engine.py`. AI queue functions (`brain_worker`, `execute_pulse`, `execute_audit`, `queue_periodic_ai_analysis`, `queue_ai_audit_task`) retained — still used by AI pulse trigger in aggregator main loop.

## Issues Found
None — all acceptance criteria met.

## Cleanup Applied
- Removed 3 dead functions from `live_engine.py` (55 lines).
