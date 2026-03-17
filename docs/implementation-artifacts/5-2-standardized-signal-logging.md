# Story 5.2: Standardized Signal Logging Refactor

Status: done

## Story
As a system maintainer,
I want all log messages in the signal services to follow a strict prefix-based format,
So that I can easily filter and monitor specific signal components in production logs.

## Acceptance Criteria

- [ ] **AC 1: Standardized Logger Names**: Use consistent logger naming convention: `aureus-signal.[component]` (e.g., `aureus-signal.structure`, `aureus-signal.pivots`).
- [ ] **AC 2: Consistent Message Prefixing**: Every log entry must start with `[t={timestamp}] [{symbol}] [method_name]`.
- [ ] **AC 3: Optimization Telemetry**: Log entries must exist for:
    - Lazy `t_map` cache hits/rebuilds.
    - Fast-Path mitigation hits/misses.
    - ZigZag engine parameter hot-updates vs re-initializations.
- [ ] **AC 4: Parity & Hash Checks**: Log the hash verification results if applicable in debugging sessions.

## Tasks / Subtasks

- [ ] Task 1: Refactor Loggers in Signal Files (AC: 1, 2)
  - Files
    - Modify: `services/aureus-signal/engine/signals/pivots.py`
    - Modify: `services/aureus-signal/engine/signals/structure.py`
    - Modify: `services/aureus-signal/engine/signals/base.py`
  - [ ] Step 1: Update logger definitions to follow `aureus-signal.*` pattern.
  - [ ] Step 2: Implement a helper for standardized prefix generation or apply it manually to critical logs.

- [ ] Task 2: Add Optimization Path Telemetry (AC: 3)
  - Files
    - Modify: `services/aureus-signal/engine/signals/structure.py` (Lazy t_map, Fast-Path)
    - Modify: `services/aureus-signal/engine/signals/pivots.py` (Engine stability)
  - [ ] Step 1: Add DEBUG or INFO logs for cache hits/misses in `t_map` logic.
  - [ ] Step 2: Add telemetry for `_verify_mitigations` fast-path evaluation.
  - [ ] Step 3: Add logs for ZigZag parameter stability (Hot update vs Re-init).

- [ ] Task 3: Regression Verification (AC: 4)
  - Files
    - Execute: `services/aureus-signal/tests/signal_optimization_benchmark.py`
  - [ ] Step 1: Run benchmark and verify logger output in logs/debug.log.

## Dev Notes
- We want to avoid excessive logging that could hurt performance, so use `logger.debug` for high-frequency path telemetry.
- Standardized prefixing helps enormously with `grep` and Kibana/Splunk style searching.
- Parity must be 100% maintained (Golden Hash).
