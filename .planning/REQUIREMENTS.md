# Requirements

## Strategy Sequence Engine
- [ ] **SEQ-01**: Refactor `TemplateStrategy._evaluate_sequence` to correctly process actual signals and state (moving from simulation to production-ready logic).
- [ ] **SEQ-02**: Support complex sequence constraints (e.g., maximum candle wait times, strict order enforcement, reset triggers).
- [ ] **SEQ-03**: Convert hard-coded strategies (`TrendContinuationStrategy`, `OrderFlowDominanceStrategy`) into sequence configurations.
- [ ] **SEQ-04**: Standardize strategy evaluation in engine pipeline to exclusively use the sequence engine (deprecate custom class overrides).

## Future Requirements
- TBD

## Out of Scope
- Creating new signal types (focus is only on strategy orchestration of existing signals).
- Performance optimizations that alter trading behavior without correctness parity.

## Traceability
| Requirement | Phase |
|---|---|
| SEQ-01 | 14 |
| SEQ-02 | 14 |
| SEQ-03 | 15 |
| SEQ-04 | 15 |
