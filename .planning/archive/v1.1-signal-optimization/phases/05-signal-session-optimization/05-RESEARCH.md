# Phase 05 Research — Signal Session Optimization

## Context
Phase 05 targets `SIG-05`: optimize and validate `session` signal behavior without changing trading intent, while preserving downstream runtime contracts.

## Baseline Findings
1. `session.py` currently:
   - classifies user-time windows (`ASIA`, `LONDON`, `NEW_YORK`, else `LUNCH_TIME`)
   - updates `state_obj.current_session`
   - maintains `tracking_vars['session_hlo']`
   - returns `tag = "market_session"` payload with broker/user time metadata
2. Session behavior influences downstream logic via `current_session` in:
   - `engine/strategies/trend_continuation.py`
   - `engine/strategies/order_flow_dominance.py`
   - `engine/logic/judges/structure.py`
3. Session state is serialized/restored through:
   - `engine/state_snapshot.py`
   - `engine/snapshot_utils.py`
   - `engine/state.py` default (`OFF_MARKET`)
4. There are no dedicated `session` test files yet in `services/aureus-signal/tests`.

## Risks
1. **Boundary drift risk**: inclusive/exclusive hour boundaries can unintentionally shift classifications.
2. **DST mapping risk**: broker DST transitions can misclassify session if timestamp mapping is inconsistent.
3. **Contract risk**: mutating `current_session`/`session_hlo` behavior can regress downstream strategy and judge logic.
4. **Coverage risk**: missing dedicated unit + integration tests can fail `TST-01..04` gates.

## Decisions
1. Preserve contract behavior:
   - `tag = "market_session"`
   - `state_obj.current_session` update semantics
   - backward-compatible `tracking_vars['session_hlo']` shape
2. Keep session windows aligned to Phase 05 context baseline (GMT+7 buckets).
3. Add dedicated session coverage at:
   - unit (`session` classification + boundary + DST-safe behavior)
   - execute-signals integration (`signal_history`/tag/timestamp behavior)
   - runtime-path integration (`run_signal_engine` persists stable session state)
4. Keep phase closure gated by explicit coverage command and validation evidence.

## Validation Architecture
- **Task-level checks**: session unit + execute-signals integration.
- **Runtime-path check**: live-engine integration using fake infra pattern.
- **Phase gate**: combined pytest coverage command for changed session scope and new tests; closure blocked unless all checks pass.
