# Phase 02 Research — Signal EMA Optimization

## Context
Phase 02 targets `SIG-02`: optimize and validate `ema` without changing trading intent or emitted event semantics.

## Baseline Findings
1. `EMASignal.calculate` already uses a hybrid path in `ema.py`:
   - warmup batch via `pandas.DataFrame.ewm(...)`
   - incremental O(1) update using cached `state_obj.emas[period]["current"]`
2. Output contract currently includes:
   - `tag`: `ema_{period}_up` or `ema_{period}_down`
   - optional `cross`: `ema_{period}_cross_up|down`
   - `period`, `value`, `t`
3. Existing EMA test coverage is narrow:
   - `test_ema_o1.py` validates parity vs pandas and empty-frame behavior
   - no dedicated live-engine integration test for EMA signal flow

## Risks
1. **Contract regression risk**
   - Refactoring EMA internals could accidentally change `tag/cross` naming or timestamp key semantics.
2. **State-shape fragility risk**
   - Cached EMA path assumes dict shape and key presence; malformed state may silently route to fallback repeatedly.
3. **Integration masking risk**
   - Without dedicated integration tests, factory/runtime wiring regressions may pass unit-only checks.
4. **Governance gap risk**
   - Phase can appear complete without explicit proof for TST-02/03/04 in EMA scope.

## Recommended Strategy
1. Preserve current event contract exactly (`ema_{period}_*` tags and `t` output key).
2. Harden state handling in place:
   - keep current `state_obj.emas[period]` schema (`current`, `prev`, `slope`)
   - add explicit guard coverage via tests for fallback behavior when cached keys are missing.
3. Add dedicated EMA integration tests (mirroring ATR integration style):
   - execute through `execute_signals_for_candle`
   - verify EMA tags and state progression post-warmup
   - verify signal history includes EMA outputs with expected timestamp mapping.
4. Enforce phase gate evidence with focused commands and coverage run for EMA scope.

## Validation Architecture
- **Sampling strategy**
  - Per implementation task: run focused EMA tests (`test_ema_o1.py`, EMA integration test file).
  - Per wave completion: run full `services/aureus-signal/tests` subset for EMA-related flow.
- **Gate criteria mapping**
  - `SIG-02`: parity and contract-preserving behavior in unit + integration outputs.
  - `TST-01`: dedicated EMA unit test file remains green.
  - `TST-02`: dedicated EMA integration test file added and green.
  - `TST-03`: coverage check for EMA module and related tests >= 80%.
  - `TST-04`: phase closure blocked unless all above checks pass.
- **Failure handling**
  - Any contract drift (`tag/cross/t`) is blocking.
  - Any integration-only failure is blocking even if unit parity passes.

## Implementation Notes
- Keep changes scoped to EMA and its immediate tests; do not refactor broader signal protocol in this phase.
- Prefer deterministic test candles in integration tests to avoid flaky crossover assertions.
