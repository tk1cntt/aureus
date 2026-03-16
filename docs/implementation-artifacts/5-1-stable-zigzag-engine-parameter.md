# Story 5.1: Stable ZigZag Engine Parameter

Status: done

## Story
As a lead architect,
I want to standardize the selection of the ZigZag engine via a unified parameter/config,
So that I can eventually switch between different ZigZag implementations (e.g., NumPy vs pure Python) without refactoring multiple signal files.

## Acceptance Criteria

- [x] **AC 1: Centralized Configuration**: The signal engine should accept a `zigzag_engine` parameter (defaulting to "pro2") in its initialization or calculate method.
- [x] **AC 2: Factory Pattern Implementation**: Implement a basic factory or mapping in `PivotSignal` that selects the correct ZigZag module based on the parameter.
- [x] **AC 3: Removal of Hardcoded Imports**: Replace direct `from engine.common.zigzag_pro2 import ...` with dynamic loading or dependency injection if feasible, or at least a standardized internal wrapper.
- [x] **AC 4: No Performance Regression**: Total signal calculation time must not increase due to the abstraction layer.
- [x] **AC 5: Parity Verification**: Must maintain 100% logic parity (Golden Hash: `3eb91697aa95539dfc5b8dec9e325f1e705068e0a00b11f92737543ee138e1dd`).

## Tasks / Subtasks

- [x] Task 1: Design Internal Engine Switch (AC: 1, 2)
  - Files
    - Modify: `services/aureus-signal/engine/signals/pivots.py`
  - [x] Step 1: Add a mapping of engine names to implementation functions.
  - [x] Step 2: Update `calculate` to handle the `zigzag_engine` keyword.

- [x] Task 2: Standardize Imports (AC: 3)
  - Files
    - Modify: `services/aureus-signal/engine/signals/pivots.py`
  - [x] Step 1: Move implementations to a registry or use a unified entry point.

- [x] Task 3: Parity & Regression Test (AC: 4, 5)
  - Files
    - Execute: `services/aureus-signal/tests/signal_optimization_benchmark.py`

## Dev Notes
- We currently use `zigzag_pro2` exclusively. This story prepares the ground for a potential `zigzag_numpy` (Cython/Numba) optimized engine in Phase 3.
- The change should be transparent to existing tests.

## Senior Developer Review (AI)
### [2026-03-16] - Post-Fix Review
- **Architecture**: The decision to implement the factory in `pivots.py` is correct as it centralizes engine ownership and avoids tight coupling with `structure.py`.
- **Stability**: Verified that `zigzag_engine` and `zigzag_config` are handled stably across multiple calls, supporting hot-updates of parameters.
- **Parity**: 100% logic parity maintained.
- **Result**: **APPROVED** ✅
