# Brainstorming Session: Signal Optimization

- **Subject:** Optimizing `StructureSignal` and `PivotSignal` performance and reliability.
- **Context:** [Analysis](file:///d:/Aureus/docs/signals/signal_design_analysis.md) and [Initial Plan](file:///d:/Aureus/docs/signals/signal_optimization_plan.md).
- **Date:** 2026-03-16

## Techniques to Explore

### 1. SCAMPER (Structured)
- **Substitute**: What if we substitute Pandas DataFrames with something lighter for inner loops?
- **Combine**: Can we combine the Pivot labeling and CHoCH detection into a single pass?
- **Eliminate**: What parts of the historical scan are absolutely unnecessary?

### 2. Reversal Inversion (Creative)
- **Goal**: Make the performance as slow as possible.
- **Insight**: If we want to make it slow, we would lặp through every candle for every pivot. We are doing that. To reverse it, we should lặp through price levels instead of time, or only react to price crossing thresholds (Event-Driven).

### 3. First Principles Thinking (Creative)
- **Question**: What do we know for certain?
- **Truth**: A CHoCH can only happen if a High or Low is broken. If price is within the previous candle's range, No structure can change.

## Idea Log
*(To be populated during the session)*
