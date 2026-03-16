# Signal Optimization: Benchmark Methodology

This document outlines the methodology used to verify performance and correctness during the optimization of the Aureus Signal Engine.

## Objectives
1.  **Correctness (Parity)**: Ensure 100% parity with the original MQL5-transitioned logic using a "Golden Hash" mechanism.
2.  **Performance Visualization**: Identify the precise line-level bottlenecks using Python's `cProfile`.
3.  **Metrics**: Track Latency (ms/candle), Throughput (candles/sec), and Memory stability.

## Components

### 1. Golden Dataset (`benchmark_data_golden.json`)
- **Source**: Extracted from PostgreSQL (`aureus_candles` table) via WSL.
- **Content**: 2,000 candles per symbol for 5 major symbols (XAUUSD, BTCUSD, ETHUSD, EURUSD, GBPUSD).
- **Diversity**: Includes trending markets, high-volatility spikes, and complex consolidation periods to stress-test ZigZag/Structure logic.

### 2. Golden Hash Verification
The benchmark script generates a SHA256 hash from the following signal outputs:
- **Swing Points**: Time, Type, and Index of all confirmed ZZ pivots.
- **Active Order Blocks**: Type, Start Time, and Price Boundaries (Top/Bottom) for all unmitigated zones.

**Rule**: Any optimization that changes this hash is automatically rejected as a regression.

### 3. Profiling Tools
- **cProfile**: Used to capture cumulative/internal time for all function calls.
- **pstats**: Sorts findings by `tottime` (time spent in the function itself) to find "leaf" bottlenecks.

## Execution Flow
1.  Reset `WindowManager` state.
2.  Iterate through the JSON dataset.
3.  Feed candles one-by-one into the engine (simulating live feed).
4.  Capture final signal states.
5.  Generate Hash and Report.
