# Requirements — v1.2 Strategy Sequence Engine (Archived)

**Status:** All requirements complete ✅
**Archived:** 2026-03-22

## Strategy Sequence Engine
- [x] **SEQ-01**: Refactor `TemplateStrategy._evaluate_sequence` to correctly process actual signals and state (moving from simulation to production-ready logic).
- [x] **SEQ-02**: Support complex sequence constraints (e.g., maximum candle wait times, strict order enforcement, reset triggers).
- [x] **SEQ-03**: Convert hard-coded strategies (`TrendContinuationStrategy`, `OrderFlowDominanceStrategy`) into sequence configurations.
- [x] **SEQ-04**: Standardize strategy evaluation in engine pipeline to exclusively use the sequence engine (deprecate custom class overrides).

## Traceability
| Requirement | Phase | Outcome |
|---|---|---|
| SEQ-01 | 14 | ✅ Validated — O(1) state machine engine |
| SEQ-02 | 14 | ✅ Validated — max_wait, reset_signals, optional jump |
| SEQ-03 | 15 | ✅ Validated — context_filters + sequence JSON |
| SEQ-04 | 15 | ✅ Validated — registry unified, legacy deleted |
