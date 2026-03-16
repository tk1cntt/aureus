# Analysis of Signal Design Complexity: `structure.py`

## Overview
`StructureSignal` (at `engine/signals/structure.py`) implements Market Structure Shifts (CHoCH) and Order Block (OB) creation by mirroring MQL5 logic. It depends on `ZigZagPro` (at `engine/common/zigzag_pro2.py`) for pivot points.

## Core Logic Flow & Complexity

### 1. The Pivot-Centric Scan (`calculate`)
- **Action**: Iterates through `state_obj.swing_points`.
- **Logic**: For each pivot (HH/LL), it checks if subsequent price action has broken it.
- **Risk**: 
    - **Performance**: O(N_pivots * N_candles_remaining). As history grows, the scan time increases linearly.
    - **Correctness**: If the scan window is truncated for performance, we might miss a break of a very old level that is still technically "valid" structure.

### 2. CHoCH Detection (`_process_choch`)
- **Action**: Scans forward from `pivot_t` to find a breakout.
- **Logic**: 
    - Finds a breakout candle.
    - Searches for an "opposing extreme" between the pivot and the breakout to validate the CHoCH.
- **Risk**: Finding the "opposing extreme" requires iterating through `points` again. If points are re-labeled or repainted by ZigZagPro, the indices might become stale.

### 3. OB Creation (`_process_ob`)
- **Action**: Searches for the "Extreme Candle" (the peak/trough that caused the break).
- **Logic**: Scans candles in the range `[pivot_idx, breakout_idx]`.
- **Risk**: This is a candle-level search. If the range is large, it consumes significant CPU. It also relies on a `t_map` which is currently regenerated on every call.

### 4. Mitigation Verification (`_verify_mitigations`)
- **Action**: Checks if any "Active" OB has been touched by price.
- **Logic**: For every unmitigated OB, it scans candles from `t_breakout` to `latest_t`.
- **Risk**: 
    - Highly redundant. It re-scans historical candles for the same OB in every cycle.
    - **Proposed optimization in code (line 78)**: `search_df = df[df['t'] > t_breakout]`. This creates many DataFrame slices.

## Why Past "Optimizations" Failed (Hypothesis)
1. **State Staleness**: Optimizing by caching `t_map` or scan indices failed because `ZigZagPro` can "repaint" (adjust) the last few pivots. If a pivot moves, any result based on its previous index/time becomes invalid.
2. **Boundary Conditions**: Truncating the scan window often missed "Deep Retracements" that break structure after a long period of consolidation.
3. **Data Dependency**: `structure.py` relies on `state_obj` which is shared across signals. A change in `pivots.py` implementation (e.g., non-repainting mode) directly affects what `StructureSignal` sees.



## Benchmark Results (Baseline)
- **Golden Hash**: `3eb91697aa95539dfc5b8dec9e325f1e705068e0a00b11f92737543ee138e1dd`
- **Total Candles**: 10,000 (across 5 symbols)
- **Avg Latency**: ~1.43ms / candle (without profiling overhead)
- **Primary Bottleneck**: `pd.DataFrame` construction in `WindowManager.update` (~75% of cumulative time).
- **Secondary Bottleneck**: Signal logic itself is masked by data ingestion overhead but shows potential for optimization in historical scans.

## Quantitative Findings
1.  **Redundant Data Processing**: Re-creating the entire DataFrame for every tick is extremely expensive.
2.  **State Synchronization**: `state_obj` management is currently procedural and depends heavily on dictionary lookups.
