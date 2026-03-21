# REQUIREMENTS — Milestone v1.1 Signal Optimization

## v1.1 Requirements

### Signal Scope (`SIG`)
- [x] **SIG-01**: Optimize and validate `atr` signal without changing trading intent.
- [x] **SIG-02**: Optimize and validate `ema` signal without changing trading intent.
- [x] **SIG-03**: Optimize and validate `fvg` signal without changing trading intent.
- [x] **SIG-04**: Optimize and validate `pivots` signal without changing trading intent.
- [x] **SIG-05**: Optimize and validate `session` signal without changing trading intent.
- [x] **SIG-06**: Optimize and validate `sweep` signal without changing trading intent.
- [x] **SIG-07**: Optimize and validate `trend` signal without changing trading intent.
- [x] **SIG-08**: Optimize and validate `volume_sma` signal without changing trading intent.
- [x] **SIG-09**: Optimize and validate `structure` signal without changing trading intent.
- [x] **SIG-10**: Optimize and sweep_targets within structure efficiently.
- [x] **SIG-11**: System GC via Daily Signal Recalculation loop.

### Test Quality Gates (`TST`)
- [x] **TST-01**: For each signal phase, create/maintain a dedicated **unit test file** for that signal.
- [x] **TST-02**: For each signal phase, create/maintain a dedicated **integration test file** when integrated into `aureus-signal` flow.
- [x] **TST-03**: Test coverage for each signal phase must be **>= 80%** on changed signal code and related test scope.
- [x] **TST-04**: A phase cannot be marked complete unless unit + integration tests pass and coverage gate (`100%`) is met.

### Governance (`VAL`)
- [x] **VAL-01**: Roadmap must keep exactly **one signal per phase**.
- [x] **VAL-02**: Requirement-to-phase traceability must remain complete and explicit.

## Phase 1 Evidence

- Phase folder: `.planning/phases/01-signal-atr/`
- Research: `.planning/phases/01-signal-atr/RESEARCH.md`
- Plan: `.planning/phases/01-signal-atr/PLAN.md`
- Validation: `.planning/phases/01-signal-atr/VALIDATION.md`
- Summary: `.planning/phases/01-signal-atr/SUMMARY.md`

## Future Requirements (Deferred)

- **FUT-01**: Cross-service E2E live-trading simulation under stress.
- **FUT-02**: Long-horizon replay with persistent golden outputs.

## Out of Scope (v1.1)

- **OOS-01**: Strategy family redesign.
- **OOS-02**: Non-signal broker/exchange adapter rewrites.
- **OOS-03**: Dashboard/UI feature redesign.

## Traceability (updated by roadmap)

| Requirement ID | Planned Phase | Success Criteria Ref |
|---|---|---|
| SIG-01 | 1 | P1-C1, P1-C2 |
| SIG-02 | 2 | P2-C1, P2-C2 |
| SIG-03 | 3 | P3-C1, P3-C2 |
| SIG-04 | 4 | P4-C1, P4-C2 |
| SIG-05 | 5 | P5-C1, P5-C2 |
| SIG-06 | 6 | P6-C1, P6-C2 |
| SIG-07 | 7 | P7-C1, P7-C2 |
| SIG-08 | 8 | P8-C1, P8-C2 |
| SIG-09 | 9 | P9-C1, P9-C2 |
| SIG-10 | 10 | P10-C1, P10-C2 |
| SIG-11 | 11 | GC Daily Loop |
| TST-01 | 1-11 | Px-C3 |
| TST-02 | 1-11 | Px-C4 |
| TST-03 | 1-11 | Px-C5 |
| TST-04 | 1-11 | Px-C6 |
| VAL-01 | 1-11 | roadmap structure |
| VAL-02 | 1-11 | traceability tables |
