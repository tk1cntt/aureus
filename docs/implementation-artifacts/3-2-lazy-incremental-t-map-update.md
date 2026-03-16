# Story 3.2: Lazy Incremental t_map Update

Status: done

## Story

As a system developer,
I want the `StructureSignal` to only update the `t_map` for new candles,
So that the overhead of full dictionary construction is eliminated for every tick.

## Acceptance Criteria

1. **Incremental Update**: When `calculate` is called with a new tick (live candle), only the last entry is added to `state_obj.t_map`.
2. **Backfill Support**: When multiple new candles are added (e.g., after a connection gap), the map is updated for all new entries.
3. **Cache Invalidation (Sliding Window)**: If the sliding window shifts (oldest candles removed), the `t_map` is correctly detected as stale and rebuilt to match the new `df` indices.
4. **Performance**: Per-tick overhead for `t_map` construction is reduced from O(N) to O(1) for stable windows.

## Tasks / Subtasks

- [x] Task 1: Refactor `StructureSignal.calculate` to use persistent `t_map` (AC: 1, 2, 4)
  - Files
    - Modify: `services/aureus-signal/engine/signals/structure.py`
    - Test: `services/aureus-signal/tests/test_incremental_t_map.py` (New)
  - [x] Step 1: Create a test that verifies `calculate` populates `state_obj.t_map`.
  - [x] Step 2: Implement logic in `calculate`:
    - Check if `state_obj.t_map` exists and its first entry matches `df.iloc[0]['t']`.
    - If mismatch or empty: rebuild fully.
    - If match: scan from `len(state_obj.t_map)` to `len(df)` and add new entries.
    - Use `state_obj.t_map` instead of local `t_map`.
  - [x] Step 3: Run test to verify `t_map` persistence across calls.

- [x] Task 2: Implement Sliding Window Detection (AC: 3)
  - Files
    - Modify: `services/aureus-signal/engine/signals/structure.py`
  - [x] Step 1: Add a check in `calculate`: if `len(state_obj.t_map) > len(df)` or the first timestamp doesn't match, clear and rebuild.
  - [x] Step 2: Create a test case where `df` shifts (removes first row) and verify `t_map` correctly reflects new indices.

- [x] Task 3: Performance Benchmarking (Internal) (AC: 4)
  - Files
    - Test: `services/aureus-signal/tests/test_incremental_t_map.py`
  - [x] Step 1: Add a benchmark test comparing execution time of 1000 updates between the old "full rebuild" and new "incremental" logic.

## Dev Notes

- **Stale Detection**: The simplest way to detect a sliding window is:
  ```python
  if not state_obj.t_map or df.iloc[0]['t'] not in state_obj.t_map or state_obj.t_map[df.iloc[0]['t']] != 0:
      state_obj.t_map = {int(t): i for i, t in enumerate(df['t'].values)}
  ```
- **Positional Mapping**: Remember that `t_map` maps `timestamp -> integer positional index in current df`. When `WindowManager` slides the window, index 0 points to a NEW timestamp.
- **Reference**: Ensure `_process_choch` and `_process_ob` pass `state_obj.t_map` correctly.

### Project Structure Notes
- Logic resides in `services/aureus-signal/engine/signals/structure.py`.

### References
- [Story 3.1: Persistent Storage Implementation](file:///d:/Aureus/docs/implementation-artifacts/3-1-persistent-time-map-storage.md)
- [Benchmark Report: Bottleneck ID](file:///d:/Aureus/docs/signals/benchmark_report_v1.md#primary-bottlenecks)

## Senior Developer Review (AI)

### Findings Summary
- **🔴 HIGH**: Type mismatch in `t_map` serialization (int vs string keys) prevented effective caching after reload.
- **🟡 MEDIUM**: Untracked test files in the repository.
- **🟡 MEDIUM**: Loop inefficiency in `calculate` due to redundant `int()` calls.

### Fixes Applied
- [x] Implemented integer key conversion in `SymbolState.from_dict`.
- [x] Optimized `t_map` update loop using `astype(int)` on numpy array.
- [x] Removed "magic number" buffer in stale check for exact match logic.
- [x] Committed `tests/test_incremental_t_map.py` to git.

## Change Log
- 2026-03-16: Story created and implemented.
- 2026-03-16: Code review performed; identified serialization bug and loop inefficiencies.
- 2026-03-16: Automatic fixes applied; logic parity verified (Golden Hash: `3eb9...1dd`).

## File List
- `services/aureus-signal/engine/signals/structure.py`
- `services/aureus-signal/engine/state.py`
- `services/aureus-signal/tests/test_incremental_t_map.py`
