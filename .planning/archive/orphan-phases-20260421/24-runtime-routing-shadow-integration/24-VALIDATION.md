---
phase: 24
slug: runtime-routing-shadow-integration
date: 2026-04-04
status: draft
---

# Phase 24: Runtime Routing & Shadow Integration - Validation Strategy

## 1. Goal Backward Verification
The primary goal of this phase is "Add runtime provider mode routing and shadow integration with Redis as default." If this is achieved, we should be able to see the engine route decisions according to the `provider_mode` feature flag. We should also observe TradingAgents generating output without blocking the primary loop.

### 1.1 Critical Path Criteria
- The engine MUST default to `redis_primary` mode.
- The `provider_mode` flag MUST be configurable via `aureus:sys:config` pub/sub and picked up without restart.
- In `ta_shadow` mode, primary engine loop latency MUST NOT increase compared to `redis_primary`.
- In `ta_shadow` mode, AI signals MUST be written to `aureus:ai:shadow:{symbol}`.
- In `ta_primary` mode, the engine MUST use `get_decision()` output directly.

## 2. Technical Validation
- **Unit Tests**: Ensure `feature_flags.py` (or routing logic in `live_engine.py`) correctly interprets modes.
- **Integration Tests**: Verify background tasks spawned for shadow execution complete successfully without throwing unhandled exceptions in the main asyncio loop.
- **Performance Baseline**: A simulated lag of 2+ seconds in `TradingAgentsProvider.get_decision()` should NOT block the processing of the next candle when in `ta_shadow` mode.

## 3. Approval Requirements
- [ ] Unit tests pass.
- [ ] Shadow mode execution isolation is verified logically (e.g. `asyncio.create_task` or a background worker used).
- [ ] Redis output verifies isolation (`aureus:ai:latest` vs `aureus:ai:shadow`).
