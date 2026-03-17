# Signal Optimization Implementation Plan

This plan outlines a staged, verified approach to optimizing `StructureSignal` and `PivotSignal` to improve performance while guaranteeing 100% parity with MQL5 logic.

## Proposed Changes

### Phase 1: Verification & Benchmarking
- [ ] **[NEW] [signal_optimization_benchmark.py](file:///d:/Aureus/services/aureus-signal/tests/signal_optimization_benchmark.py)**: Create a script to run current logic on a large dataset (10,000+ candles) and generate a "Golden Hash" of all pivots, CHoCHs, and OBs.
- [ ] Establish performance baseline (execution time per cycle).

### Phase 2: Low-Risk Performance Wins
#### [MODIFY] [structure.py](file:///d:/Aureus/services/aureus-signal/engine/signals/structure.py)
- **Lazy `t_map`**: Store `t_map` in `state_obj` and update incrementally instead of regenerating every cycle.
- **Micro-caching for `_verify_mitigations`**: Instead of a full historical sweep, check only the current candle for "Active" OBs first. If a touch is detected, perform the precise sweep only once.

#### [MODIFY] [pivots.py](file:///d:/Aureus/services/aureus-signal/engine/signals/pivots.py)
- **Incremental state updates**: Ensure `zigzag_engine` parameters are updated only when they actually change.

### Phase 3: Algorithm Optimization (Step-by-Step)
#### [MODIFY] [structure.py](file:///d:/Aureus/services/aureus-signal/engine/signals/structure.py)
- **Pivot Search Truncation**: Introduce a "Lookback Window" for pivot scanning, with a safety buffer based on ATR or Max Consolidation Period.
- **Numpy/Vectorized Access**: Replace row-by-row iteration in `_process_ob` with vectorized price comparisons where applicable.

## Verification Plan

### Automated Tests
- Run `signal_optimization_benchmark.py` after every phase. If the "Golden Hash" changes, the optimization is rejected.
- Run `pytest d:\Aureus\services\aureus-signal\tests\test_zigzag_ob_logic.py` to ensure existing edge cases are still handled correctly.

### Manual Verification
- Review logs for consistency in OB/CHoCH detection between optimized and original versions.
