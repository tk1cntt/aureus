# Phase 06 Research — Signal Sweep Optimization

## Context
Phase 06 targets `SIG-06`: optimize and validate `sweep` signal behavior with correctness-first hardening, while preserving trading intent and downstream runtime contracts.

## Baseline Findings
1. `sweep.py` currently:
   - consumes `state_obj.sweep_targets` and evaluates only the latest closed candle
   - emits at most one trigger per candle (`sweep_bull` or `sweep_bear`)
   - deduplicates by `tag + price_swept + t` against `state_obj.signal_history`
   - writes transient payloads to `state_obj.transient_signals[tag]`
   - invokes `request_ai_update("STOP_HUNT")` when a new sweep is emitted
2. Downstream consumers depend on stable sweep contracts:
   - `engine/signals/sweep_bull.py`
   - `engine/signals/sweep_bear.py`
   - `engine/event_filter.py` (structural tag trigger path)
3. Target lifecycle is state-driven:
   - swept target is removed from active list
   - unswept targets remain in `state_obj.sweep_targets`
4. Existing test baseline has only partial guard coverage (`test_signal_contract_normalization.py`), but no dedicated sweep unit/integration test pack.

## Risks
1. **Contract drift risk**: modifying payload/tag semantics can break outlet and event-filter flows.
2. **Dedup regression risk**: incorrect dedup logic can emit duplicate sweeps in the same candle.
3. **State mutation risk**: unsafe updates to `sweep_targets` can cause replay inconsistency.
4. **Coverage risk**: missing dedicated tests can fail `TST-01..04` phase gates.

## Decisions
1. Preserve public sweep contracts and payload shape:
   - tags stay `sweep_bull` / `sweep_bear`
   - payload keys remain `tag`, `t`, `price_swept`, `source_type`, `source_t`, `fidelity`, `market_regime`
2. Keep conservative lifecycle policy:
   - max 1 trigger per candle
   - remove triggered target, retain non-triggered targets
3. Keep regime gating semantics unchanged:
   - bullish sweep only for `TREND_UP` / `SIDEWAYS`
   - bearish sweep only for `TREND_DN` / `SIDEWAYS`
4. Add dedicated Phase 06 validation pack:
   - sweep-focused unit tests
   - execute-signals integration tests
   - live-engine/runtime integration tests
   - explicit coverage gate for sweep scope

## Validation Architecture
- **Task-level checks**: sweep unit + execute-signals integration tests.
- **Runtime-path check**: live-engine integration verifying factory wiring and structural tag flow.
- **Phase gate**: combined pytest + coverage command for sweep signal scope; closure blocked unless all gates pass.
