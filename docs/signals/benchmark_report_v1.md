# Signal Benchmark Report: Baseline (V1)

- **Date**: 2026-03-16
- **Status**: Completed (Baseline Established)
- **Hash**: `3eb91697aa95539dfc5b8dec9e325f1e705068e0a00b11f92737543ee138e1dd`

## Executive Summary
The baseline run confirms that the system is stable but hindered by high data-ingestion overhead. While individual signal calculation is fast, the management of the data window consumes the majority of resources.

## Performance Metrics
| Metric | Value |
| :--- | :--- |
| **Total Candles processed** | 10,000 |
| **Total Execution Time** | 14.26s |
| **Avg Latency (ms/candle)** | 1.43ms |
| **Throughput (candles/s)** | ~701 |

### Per-Symbol Breakdown
| Symbol | Candles | Latency (ms/candle) |
| :--- | :--- | :--- |
| XAUUSD | 2,000 | 1.60ms |
| BTCUSD | 2,000 | 1.37ms |
| ETHUSD | 2,000 | 1.38ms |
| EURUSD | 2,000 | 1.33ms |
| GBPUSD | 2,000 | 1.43ms |

## Top 5 Bottlenecks (Identified by cProfile)
1.  **`pd.DataFrame` construction** (21% tottime): Re-building DataFrames from lists of dicts in `WindowManager.update`.
2.  **`_list_of_dict_to_arrays`** (Pandas internal, 20% tottime): Overhead of dictionary iteration during DF creation.
3.  **`keys` selection** (6% tottime): Redundant dictionary key access during data normalization.
4.  **Signal Scan Loop**: (Masked by I/O but present in cumulative time).

## Conclusion & Next Steps
- **Critical Fix**: Need to transition `WindowManager` to use a more efficient data structure (e.g., pre-allocated Numpy arrays or incremental DataFrame appends).
- **Signal Logic**: Proceed with `t_map` caching and lazy mitigation sweeps once I/O is stabilized.
