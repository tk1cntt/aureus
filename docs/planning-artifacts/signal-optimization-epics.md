---
stepsCompleted: [1, 2, 3, 4]
inputDocuments: ["docs/planning-artifacts/architecture.md", "docs/signals/signal_design_analysis.md", "docs/signals/signal_optimization_plan.md", "docs/signals/benchmark_report_v1.md"]
---

# Signal Optimization Phase 2 - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for Signal Optimization Phase 2, decomposing the requirements from the Signal Design Analysis, Optimization Plan, and Baseline Benchmark into implementable stories.

## Requirements Inventory

### Functional Requirements

FR1: Implement Lazy `t_map` in `StructureSignal` to avoid per-cycle regeneration.
FR2: Store and incrementally update `t_map` within the `SymbolState` object.
FR3: Implement Micro-caching for `_verify_mitigations` to check current candle touch before full historical sweep.
FR4: Ensure `zigzag_engine` parameters in `pivots.py` are updated only on actual change.
FR5: Maintain 100% parity with MQL5 logic, verified by the Golden Hash `3eb9...1dd`.

### NonFunctional Requirements

NFR1: Performance: Target a measurable reduction in `avg_latency_ms` (Baseline: 1.43ms).
NFR2: Reliability: No regression in signal accuracy (Golden Hash must remain identical).
NFR3: Scalability: System must handle 2,000+ candles per symbol across 5+ symbols simultaneously.
NFR4: Maintainability: Code must follow standardized logging format `aureus-signal.structure - INFO - ...`.

### Additional Requirements

- **In-Memory State**: Use `SymbolState` as the primary source of truth for transient data.
- **Incrementalism**: Architecture requires all updates to be additive/incremental to support high-frequency ticks.
- **Numpy/Vectorization**: Prefer Numpy-based operations over row-by-row iteration for candle scans.
- **Deduplication**: Avoid duplicate OB/signal creation in the state object.

### UX Design Requirements

(No UI changes requested for this backend optimization phase).

### FR Coverage Map

FR1: Epic 3 - Lazy `t_map` avoids per-tick overhead.
FR2: Epic 3 - `SymbolState` persistence for time-data.
FR3: Epic 4 - Only scan current candle for mitigation unless hit.
FR4: Epic 5 - Pivot engine parameter change detection.
FR5: All Epics - Regression testing via Golden Hash.

## Epic List

### Epic 3: Optimized Time Management (Latency Reduction)
Users will experience faster tick-to-signal execution by eliminating the O(N) cost of rebuilding time maps on every data update.
**FRs covered:** FR1, FR2, FR5.

### Epic 4: High-Performance Mitigation Tracking (Scalability)
Users can monitor a higher number of symbols and timeframes simultaneously by transitioning from a global historical scan to a micro-cached mitigation check.
**FRs covered:** FR3, FR5.

### Epic 5: Foundation Stability & Consistency (Maintenance)
Ensures a stable calculation environment by preventing redundant engine re-initializations and standardizing system feedback.
**FRs covered:** FR4, FR5, NFR4.

## Epic 3: Optimized Time Management (Latency Reduction)

Users will experience faster tick-to-signal execution by eliminating the O(N) cost of rebuilding time maps on every data update.

### Story 3.1: Persistent Time-Map Storage in SymbolState
As a system developer,
I want the `SymbolState` to maintain a persistent mapping of timestamps to indices,
So that I don't have to rebuild this map on every market update.

**Acceptance Criteria:**

**Given** a new instance of `SymbolState` for a symbol
**When** initialization occurs
**Then** it must include an empty `t_map` dictionary in its internal state.

**Given** a pre-existing `SymbolState`
**When** the `WindowManager` updates the session
**Then** the `t_map` should be accessible and capable of storing incremental updates.

### Story 3.2: Lazy Incremental t_map Update
As a system developer,
I want the `StructureSignal` to only update the `t_map` for new candles,
So that the overhead of full dictionary construction is eliminated for every tick.

**Acceptance Criteria:**

**Given** a `t_map` in the `SymbolState`
**When** `calculate` is called on a new tick (live candle)
**Then** only the timestamp of the last candle should be added/updated in the map.

**Given** a backfill operation
**When** multiple candles are added simultaneously
**Then** the `t_map` should be updated only for the newly ingested range.

### Story 3.3: Performance & Parity Validation for Time Management
As a quantify analyst,
I want to verify that the lazy time-map update reduces latency without changing signal output,
So that I can confidently deploy the optimization to production.

**Acceptance Criteria:**

**Given** the optimized `t_map` logic
**When** running the `signal_optimization_benchmark.py`
**Then** the optimized `t_map` logic should be used.
**And** the generated Golden Hash must match `3eb9...1dd` and `avg_latency_ms` must be lower than the baseline.

## Epic 4: High-Performance Mitigation Tracking (Scalability)

Users can monitor a higher number of symbols and timeframes simultaneously by transitioning from a global historical scan to a micro-cached mitigation check.

### Story 4.1: Fast-Path Mitigation Detection (Latest Candle Check)
As a system developer,
I want the signal engine to check only the most recent candle for OB touching/mitigation first,
So that I can avoid scanning thousands of historical candles on every tick.

**Acceptance Criteria:**

**Given** a list of "Active" Order Blocks in the `SymbolState`
**When** a new tick arrives
**Then** the engine should first perform a high/low comparison against only the last candle.

**Given** the last candle does NOT touch an OB
**When** the check completes
**Then** no further historical scanning should be performed for that OB in that cycle.

### Story 4.2: Conditional Historical Sweep
As a system developer,
I want the full historical sweep for an OB to occur only when the fast-path check is triggered or an OB is newly created,
So that I minimize redundant CPU cycles.

**Acceptance Criteria:**

**Given** the fast-path check detects a touch on an OB
**When** the condition is met
**Then** a precise historical sweep (`t_breakout` to `latest_t`) should be executed only once to confirm the exact mitigation point.

**Given** a newly created OB
**When** it is added to the state
**Then** it should undergo an initial full sweep until the current time to set its initial mitigation status.

### Story 4.3: Scalability Verification for Mitigation Tracking
As a quantify analyst,
I want to verify that the optimized mitigation tracking handles 5+ symbols with 2000+ candles each without exceeding 5ms total latency,
So that the system remains responsive under heavy market load.

**Acceptance Criteria:**

**Given** the micro-caching mitigation logic
**When** running the `signal_optimization_benchmark.py` with multi-symbol data
**Then** the Golden Hash must match `3eb9...1dd` and average latency should decrease significantly as more active OBs are present.

## Epic 5: Foundation Stability & Consistency (Maintenance)

Ensures a stable calculation environment by preventing redundant engine re-initializations and standardizing system feedback.

### Story 5.1: Stable ZigZag Engine Parameter Management
As a system developer,
I want the signal engine in `pivots.py` to compare incoming parameters with the current `zigzag_engine` configuration,
So that I don't trigger expensive engine re-initializations on every tick if the parameters haven't changed.

**Acceptance Criteria:**

**Given** an existing `zigzag_engine` instance in the `SymbolState`
**When** new parameters (depth, deviation, backstep) are provided
**Then** the engine should only be re-initialized IF at least one parameter value differs from the previous state.

**Given** no parameter changes
**When** an update is requested
**Then** the existing engine instance should be reused.

### Story 5.2: Standardized Signal Logging Refactor
As a system maintainer,
I want all log messages in the signal services to follow a strict prefix-based format,
So that I can easily filter and monitor specific signal components in production logs.

**Acceptance Criteria:**

**Given** a log event in `structure.py` or `pivots.py`
**When** messages are emitted to `stdout` or log file
**Then** they must be prefixed with `aureus-signal.[component_name] - [LEVEL] - [SYMBOL]`.

**Given** a multi-agent debugging session
**When** reviewing logs
**Then** all optimized logic paths should include clear entries documenting cache hits/misses and hash verification status.

### Story 5.3: Final Phase 2 Integration & Benchmark
As a quantify analyst,
I want to run a complete benchmark of all Phase 2 optimizations combined,
So that I can verify the cumulative performance gain and guarantee 100% logic parity.

**Acceptance Criteria:**

**Given** all stories from Epics 3, 4, and 5 are implemented
**When** running `signal_optimization_benchmark.py`
**Then** the Golden Hash must match `3eb9...1dd`.
**And** the cumulative `avg_latency_ms` must show a significant improvement over the baseline (target > 50% reduction).
