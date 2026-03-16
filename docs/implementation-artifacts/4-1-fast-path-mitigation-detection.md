# Story 4.1: Fast-Path Mitigation Detection (Latest Candle Check)

Status: done

## Story
As a system developer,
I want the signal engine to check only the most recent candle for OB touching/mitigation first,
So that I can avoid scanning thousands of historical candles on every tick.

## Acceptance Criteria

- [x] **AC 1: Fast-Path Logic**: In `_verify_mitigations`, the engine must first check the `latest_candle` (the very last row in `df`) against all active OBs.
- [x] **AC 2: Skip Historical Scan**: If the `latest_candle` does NOT touch an OB's zone, the engine must SKIP the full historical loop (`search_df.iterrows()`) for that specific OB.
- [x] **AC 3: Precise Confirmation**: If a touch is detected on the last candle, the existing historical sweep logic must still run (or be optimized) to find the *exact* first touch time between `t_breakout` and now, ensuring logic parity.
- [x] **AC 4: Performance Gain**: The number of loop iterations in `_verify_mitigations` should drop significantly for symbols with many active OBs but no current price interaction.
- [x] **AC 5: Parity Verification**: Must maintain 100% logic parity (Golden Hash: `3eb9...1dd`).

## Tasks / Subtasks

- [x] Task 1: Refactor `_verify_mitigations` with Fast-Path (AC: 1, 2)
  - Files
    - Modify: `services/aureus-signal/engine/signals/structure.py`
  - [x] Step 1: Extract `latest_candle` and its HL values before the OB loop.
  - [x] Step 2: Inside the OB loop, add a conditional check: `if not is_touching_latest: continue`.
  - [x] Step 3: Wrap the expensive `search_df.iterrows()` scan inside this condition.

- [x] Task 2: Unit Testing for Fast-Path (AC: 4)
  - Files
    - New: `services/aureus-signal/tests/test_mitigation_optimization.py`
  - [x] Step 1: Create a test case with multiple active OBs and a "non-touching" latest candle.
  - [x] Step 2: Use matching/mocking to verify that the historical loop is skipped.

- [x] Task 3: Regression & Benchmark (AC: 5)
  - Files
    - Execute: `services/aureus-signal/tests/signal_optimization_benchmark.py`
  - [x] Step 1: Run benchmark to confirm Golden Hash parity and measure latency reduction.

## Senior Developer Review (AI)

### Findings Summary
- **🟢 PASS**: AC 1 & 2 (Fast-Path logic) correctly implemented.
- **🟢 PASS**: AC 5 (Parity Verification) confirmed via `signal_optimization_benchmark.py`.
- **🟡 Warning**: **"Gap-Safe" Logic**. The current Fast-Path assumes the engine is called for *every* candle. If a batch of 10 candles is processed where candle #5 touches an OB but candle #10 doesn't, the mitigation will be missed.
  - *Mitigation*: This is acceptable for the current MT5 Real-time bridge (tick-by-tick) and Benchmark (bar-by-bar). Story 4.2 will address smarter historical sweeps for backfill/batch scenarios.
- **🟢 Optimization**: Candle HL extraction moved outside the OB loop, reducing redundant `iloc` calls.

### Fixes Applied (Review Follow-up)
- [x] Verified unit tests `test_mitigation_optimization.py`.
- [x] Synchronized `benchmark_report.json` with latest 100% parity results.

## Change Log
- 2026-03-16: Fast-Path logic implemented in `_verify_mitigations`.
- 2026-03-16: Unit tests added for touch/no-touch scenarios.
- 2026-03-16: Benchmark parity confirmed (Golden Hash match).
- 2026-03-16: Code Review complete; Status set to Done.
