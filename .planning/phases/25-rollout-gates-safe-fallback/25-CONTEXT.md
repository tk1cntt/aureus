# Phase 25: Rollout Gates & Safe Fallback - Context

**Gathered:** 2026-04-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Implement rollout gates and drift observability for TradingAgents integration. Ensure the system can evaluate TradingAgents output against the Redis baseline asynchronously without blocking the main event loop, and gracefully fallback via a Circuit Breaker if failure thresholds are exceeded.

</domain>

<decisions>
## Implementation Decisions

### Gate Evaluation
- **D-01:** Evaluate gate rules (lag, drift) asynchronously (Async/Observer pattern) to guarantee zero blocking on the primary Redis signal loop.

### Fallback Behavior 
- **D-02:** Implement a Circuit Breaker pattern. If TA fails or lags excessively beyond X thresholds, halt requests temporarily to protect API quota and system stability, rather than silently failing per-request.

### Drift Observability
- **D-03:** Persist shadow drift metrics to a TimescaleDB Event/Telemetry table. This ensures historical drift records are queryable for backtest validation and Grafana dashboard integration.

### the agent's Discretion
- Exact threshold durations and sizes for circuit breaker (e.g., 5 errors in 1 minute trips breaker for 5 mins).
- Specific SQL schema for the Drift telemetry table in TimescaleDB.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Prior Phase Requirements
- `.planning/phases/21-prerequisites-compatibility-validation/21-CONTEXT.md` 
- `.planning/phases/24-runtime-routing-shadow-integration/24-CONTEXT.md` — D-02 Async Execution requirement forms the basis of D-01 here.

### Architecture
- `.planning/codebase/ARCHITECTURE.md`
- `.planning/codebase/INTEGRATIONS.md`
</canonical_refs>

<specifics>
## Specific Ideas

No specific implementation details overridden. Ensure Circuit Breaker logs state transitions clearly to stdout/Prometheus so Dev/Ops knows when TA is disconnected.

</specifics>

<deferred>
## Deferred Ideas

None.
</deferred>
