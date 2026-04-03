# FEATURES

## Milestone Focus
TradingAgents market data integration with zero-regression ingest behavior.

## Category 1: Provider Architecture
### Table stakes
- Provider interface for market data polling.
- Redis provider extracted from current implementation.
- Backward-compatible client construction path.

### Differentiators
- Provider-neutral ingestion path enabling future venues beyond TradingAgents.

## Category 2: TradingAgents Adapter
### Table stakes
- TradingAgents adapter returning canonical candle schema.
- Symbol mapping from Aureus symbols to provider symbols.
- Error handling taxonomy for malformed/rate-limited responses.

### Differentiators
- Built-in cache + vendor fallback controls for resilient pull-based operation.

## Category 3: Runtime Routing & Rollout Safety
### Table stakes
- Config-driven provider selection: `redis | shadow | tradingagents`.
- Shadow comparison path without affecting live Redis processing.
- Fail-safe fallback behavior to Redis mode.

### Differentiators
- Drift-aware rollout gates (quality + latency + mismatch monitoring).

## Category 4: Verification Coverage
### Table stakes
- Provider contract tests.
- Adapter normalization/mapping/cache tests.
- Gate behavior tests for shadow drift and error thresholds.

### Anti-features (Out of scope for this milestone)
- Full strategy/execution logic changes.
- Immediate production promotion of TradingAgents without shadow evidence.
- Multi-service orchestration redesign.
