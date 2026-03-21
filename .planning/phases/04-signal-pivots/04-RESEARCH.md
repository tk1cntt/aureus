# Phase 04 Research — Signal Pivots Optimization

## Context
Phase 04 targets `SIG-04`: optimize and validate `pivots` without changing trading intent, with conservative scope locked in `04-CONTEXT.md`.

## Baseline Findings
1. `pivots.py` relies on `zigzag_pro2` output and merges structural metadata (`is_choch`, `ob`, `fvg`, `broken`, `breakout_t`) into pivot history.
2. Strategy consumption is tag-sequence based (`signal_history`) while event flow is handled through runtime/event filtering.
3. `signal_factory.py` provides pivots wiring and normalized snapshot behavior when signal state is absent.
4. `state.py` and `swing_points` continuity are critical for deterministic downstream behavior.

## Risks
1. **Semantic drift risk**: changing pivot core math or confirmation timing can break MQL5 parity and strategy behavior.
2. **Contract drift risk**: changing output shape (`tag`, `price`, `t`, `is_high`) can break runtime/storage consumers.
3. **State integrity risk**: malformed candle/state windows may cause nondeterministic updates or persistence mismatch.
4. **Coverage gate risk**: missing dedicated pivots tests can hide regressions and fail `TST-01..04`.

## Decisions
1. Keep `zigzag_pro2` algorithm and non-repaint confirmation semantics unchanged.
2. Restrict changes to defensive hardening around input/state handling and deterministic guardrails.
3. Preserve pivots output and metadata compatibility contract.
4. Add dedicated unit/integration/runtime pivots tests and enforce `100%` coverage for changed pivots scope.

## Validation Architecture
- Per-task checks: pivots unit and integration tests.
- Per-wave checks: runtime path + factory/contract stability checks.
- Phase gate: combined coverage command on pivots signal scope; phase closure blocked unless all gates pass.
