# Phase 25: Rollout Gates & Safe Fallback - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions captured in CONTEXT.md — this log preserves the analysis.

**Date:** 2026-04-05
**Phase:** 25-rollout-gates-safe-fallback
**Mode:** discuss

## Questions Asked

### Q1: Gate Evaluation Location
**Options presented:**
- A. Sync (Inline): Evaluate lag and drift immediately in `execute_signals_for_candle`.
- B. Async (Observer): Push to background queue and check async. (Recommended)
**User selection:** B. Async (Observer)
**Resulting Decision:** D-01

### Q2: Fallback Behavior
**Options presented:**
- A. Per-request silent: Fail silently on individual requests.
- B. Circuit Breaker: Halt connections if errors surpass threshold. (Recommended)
**User selection:** B. Circuit Breaker
**Resulting Decision:** D-02

### Q3: Drift Observability
**Options presented:**
- A. Prometheus Metrics: Use only histograms/counters.
- B. TimescaleDB Event/Telemetry table: Write to DB for deep historical analysis. (Recommended)
**User selection:** B. TimescaleDB
**Resulting Decision:** D-03
