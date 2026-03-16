# Story 4.2: Conditional Historical Sweep (Batch-Safe & Vectorized)

Status: done

## Story
As a robust system developer,
I want the mitigation check to be safe for data gaps and batch processing,
So that I never miss an OB touch while still avoiding inefficient historical loops.

## Acceptance Criteria

- [x] **AC 1: Gap-Safe Logic**: The engine must detect if multiple new candles have arrived since the last check. If `len(new_candles) > 1`, it must perform a sweep across *all* new candles, not just the latest.
- [x] **AC 2: Vectorized Sweep**: Replace the `search_df.iterrows()` loop with a vectorized Pandas/NumPy check (e.g., `search_df['l'].min() <= ob['top']`) to find if *any* candle in the range touched the OB.
- [x] **AC 3: First-Time Sweep Only**: A full historical sweep (from `t_breakout` to `now`) should ONLY occur once when an OB is first created or when the system detects a "state out-of-sync" condition.
- [x] **AC 4: Precise Mitigation Time**: If a vectorized touch is detected, use `search_df[search_df['l'] <= ob['top']].iloc[0]['t']` to find the exact first touch timestamp.
- [x] **AC 5: Parity & Performance**: Maintain 100% logic parity (Golden Hash: `3eb9...1dd`) and show latency reduction compared to Story 4.1.

## Tasks / Subtasks

- [x] Task 1: Implement Batch-Safe Detection (AC: 1, 3)
  - Files
    - Modify: `services/aureus-signal/engine/signals/structure.py`
  - [x] Step 1: Track the `last_processed_t` for each OB or for the signal state.
  - [x] Step 2: Update `is_latest_touch` to check the range `(last_processed_t, latest_t]`.

- [x] Task 2: Vectorize the Historical Sweep (AC: 2, 4)
  - Files
    - Modify: `services/aureus-signal/engine/signals/structure.py`
  - [x] Step 1: Replace `iterrows()` with vectorized Boolean indexing.
  - [x] Step 2: Ensure logging and event emissions (AI update requests) still work correctly for the first touch.

- [x] Task 3: Stress Test for Gaps (AC: 1, 5)
  - Files
    - Update: `services/aureus-signal/tests/test_mitigation_optimization.py`
  - [x] Step 1: Add a "Gap Test" where a touch happens in the middle of a 10-candle jump.
  - [x] Step 2: Verify the OB is correctly mitigated.

- [x] Task 4: Regression & Benchmark (AC: 5)
  - Files
    - Execute: `services/aureus-signal/tests/signal_optimization_benchmark.py`

## Dev Notes
- By combining Fast-Path (Story 4.1) with Vectorized Batch Checks (Story 4.2), we achieve O(1) for ticks and O(log N) or vectorized O(N) for gaps.
- This removes the last major Python-level loop in the signal calculation (excluding the OB loop itself).
