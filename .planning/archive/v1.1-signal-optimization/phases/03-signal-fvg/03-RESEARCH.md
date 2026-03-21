# Phase 03 Research — Signal FVG Optimization

## Context
Phase 03 targets `SIG-03`: optimize and validate `fvg` without changing trading intent, while preserving runtime compatibility.

## Baseline Findings
1. `fvg.py` emits transient structural keys used by `event_filter`:
   - `fvg_bull_new`, `fvg_bear_new`
   - `fvg_bull_mitigated`, `fvg_bear_mitigated`
2. Strategy-facing sequence signals are tag-based via `signal_history`:
   - `fvg_up` from `fvg_up.py`
   - `fvg_down` from `fvg_down.py`
3. Factory registration is feature-flagged (`AUREUS_ENABLE_FVG_SIGNAL`) in `signal_factory.py`.
4. Existing tests have FVG factory-flag assertions, but no dedicated FVG unit/helper/runtime integration suite.

## Risks
1. **Contract drift risk**: changing event keys or tag/timestamp shape can break downstream runtime/strategy behavior.
2. **State robustness risk**: malformed `state_obj.fvgs` entries may create nondeterministic mitigation behavior.
3. **Coverage gate risk**: lacking dedicated FVG tests can fail `TST-01..04` and hide regressions.

## Decisions
1. Keep dual compatibility in this phase:
   - transient event keys for runtime filtering
   - `fvg_up` / `fvg_down` tags for strategy sequencing
2. Keep mitigation semantics `touch` + emit-once.
3. Add missing dedicated FVG tests across unit/helper/runtime path.
4. Enforce explicit coverage gate (`100%`) for changed FVG signal scope.

## Validation Architecture
- Per-task quick checks: FVG unit + helper integration tests.
- Per-wave checks: include factory/contract and runtime-path integration test.
- Phase gate: run combined coverage command for FVG signal modules and block closure if `<80%`.
