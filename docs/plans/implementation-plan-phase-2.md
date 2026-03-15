# Aureus Implementation Plan - Phase 2: Signal Engine Logic & Recalculation

This phase focuses on the core intelligence of the Signal Engine, ensuring it can process data in real-time and recover gracefully from gaps.

## User Review Required

> [!WARNING]
> - **State Resets**: Implementing recalculation logic means the engine will perform fresh calculations on startup or after large gaps, which might temporarily increase CPU usage.
> - **Backfill Coordination**: The Gateway must be ready to provide historical data when the Signal Engine detects a gap.

## Proposed Changes

### Signal Engine (Core Logic)

#### [MODIFY] [services/aureus-signal/engine/live_engine.py](file:///e:/Openclaw/aureus/workspace/aureus/services/aureus-signal/engine/live_engine.py)
- Refactor the main loop to separate **Indicator Calculation** from **Strategy Evaluation**.
- Implement a **Gap Detection** mechanism that monitors incoming candle timestamps.
- Add a **Recalculation Trigger**: If a gap > `recalc_threshold` is detected, request backfill from Redis or Database.

#### [MODIFY] [services/aureus-signal/engine/state.py](file:///e:/Openclaw/aureus/workspace/aureus/services/aureus-signal/engine/state.py)
- Finalize the `SymbolState` object to store:
    - Swing Points (Highs/Lows) for ZigZag.
    - Active Order Blocks.
    - Indicator history (for convergence/divergence checks).
- Implement serialization with `orjson` and `deque` (as completed in Phase 5 but strictly defined here).

#### [NEW] [services/aureus-signal/strategies/base.py](file:///e:/Openclaw/aureus/workspace/aureus/services/aureus-signal/strategies/base.py)
- Create a base class for all trading strategies to ensure consistent interfaces for `evaluate()` and `on_new_candle()`.

## Verification Plan

### Automated Tests
- **Unit Tests**: Test gap detection logic with mock streams.
- **Integration Tests**: Simulate a service restart and verify that the Signal Engine correctly requests and processes backfill data to rebuild its state.

### Manual Verification
- Stop the Gateway for 5 minutes, then restart and verify the Signal Engine's "Recalculating..." logs and state alignment.
