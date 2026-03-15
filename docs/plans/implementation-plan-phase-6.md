# Aureus Implementation Plan - Phase 6: Strategy Pro & Indicators (SMC)

This phase implements the high-fidelity Smart Money Concepts (SMC) indicators that differentiate Aureus.

## User Review Required

> [!IMPORTANT]
> - **Indicator Definitions**: Ensure the mathematical definitions for Order Blocks (OB) and Fair Value Gaps (FVG) used match your trading style (e.g., mitigation rules, threshold percentages).
> - **Compute Cost**: Calculating multiple timeframes (HTF/LTF) simultaneously increases CPU load.

## Proposed Changes

### Strategic Indicators

#### [NEW] [services/aureus-signal/strategies/smc_pro.py](file:///e:/Openclaw/aureus/workspace/aureus/services/aureus-signal/strategies/smc_pro.py)
- Implement **Order Block (OB)** detection: Identify the last candle before a strong reversal.
- Implement **Fair Value Gap (FVG)** detection: Identify imbalances in 3-candle sequences.
- Implement **Change of Character (CHoCH)** vs. **Break of Structure (BOS)** logic.

#### [MODIFY] [services/aureus-signal/engine/factory.py](file:///e:/Openclaw/aureus/workspace/aureus/services/aureus-signal/engine/factory.py)
- Update the factory to load and initialize `SMCProStrategy` alongside current indicators.

## Verification Plan

### Automated Tests
- **Historical Analysis**: Run the SMC logic against 1 month of historical chart data and verify that pivots and blocks are correctly labeled against a manual baseline.
- **Overlapping Indicators**: Ensure that multiple strategies (ZigZag + SMC) do not create state conflicts.

### Manual Verification
- Visual check on the Dashboard (once Phase 7 is partially ready) to see if OB/FVG zones are rendered correctly.
