# SPEC_ADAPTIVE_SCORING

## 1. Purpose

Define how adaptive regime scoring is introduced safely without breaking deterministic core signal/strategy behavior.

## 2. Core Principle

Adaptive module is additive. Deterministic base rules remain the primary truth.

## 3. Two-Phase Operating Model

## 3.1 Phase A: Observe-Only (default)
- Adaptive module computes regime score and diagnostics only.
- Adaptive output must **not** alter entry trigger decisions.
- Outputs are logged for evaluation and calibration.

## 3.2 Phase B: Controlled Activation
- Adaptive output may influence trigger gating only after activation criteria pass.
- Activation scope is per strategy (and optionally per symbol cluster).
- Must support immediate rollback to Phase A.

## 4. Backtest-Driven Calibration

Calibration window is user-selected at backtest runtime (not hard-coded in spec).

Required evaluation metrics:
- `winrate`
- `profit_factor`
- `max_drawdown`

Calibration artifacts must persist:
- backtest window metadata
- data source/version
- strategy version
- score model version
- resulting activation thresholds

## 5. Activation Decision Rules

1. No activation if trace completeness is below required quality gate.
2. No activation if sample size is below configured minimum.
3. Activation only when calibrated metric thresholds are satisfied.
4. Activation event must be logged with reason and evidence refs.

## 6. Runtime Behavior in Phase B

Allowed behaviors (configurable):
- gate entry (`allow|deny`)
- weight selection among strategy variants
- risk profile modulation (if explicitly enabled)

Disallowed behaviors without explicit spec upgrade:
- changing base signal primitive definitions,
- bypassing state machine/validator checks.

## 7. Safety and Rollback

Mandatory rollback triggers:
- metric degradation below rollback thresholds,
- integrity errors in scoring pipeline,
- trace or calibration inconsistency.

Rollback action:
- switch to Phase A,
- preserve full incident log,
- emit alert event.

## 8. Observability Requirements

Must expose by strategy:
- phase state (`A|B`)
- current regime score distributions
- activation threshold set id
- recent pass/fail counts versus thresholds
- last rollback reason (if any)

## 9. Testing Requirements

- Phase A non-interference tests (adaptive cannot change entries)
- Activation gate tests
- Rollback trigger tests
- Determinism tests with adaptive enabled/disabled in same phase

---
Version: `v1.0.0`
