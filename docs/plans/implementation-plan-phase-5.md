# Phase 5: Architectural Hardening & Performance

This phase implements the critical refinements identified in Methods #9 to #20 of the architecture elicitation process. We focus on system stability, performance optimization, and operational safety.

## Proposed Changes

### 1. Performance Optimization ([clean-code], [performance])
- **[MODIFY] [live_engine.py](file:///e:/Openclaw/aureus/workspace/aureus/services/aureus-signal/engine/live_engine.py)**
    - Replace `json` with `orjson` for high-speed serialization.
    - Transition `swing_points` management to `collections.deque` (O(1) pops).
    - Refactor `process_logic` into smaller service-oriented methods (Ingestion, Calculation, Publication).
- **[MODIFY] [common](file:///e:/Openclaw/aureus/workspace/aureus/shared/aureus-common/serialization.py)**
    - Ensure `aureus-common` supports `orjson` if applicable.

### 2. Hardening & Security ([security], [resilience])
- **[MODIFY] [main.py (Gateway)](file:///e:/Openclaw/aureus/workspace/aureus/services/aureus-gateway/main.py)**
    - Implement a simple `RateLimiter` (token bucket) per symbol/connection.
    - Add basic input sanitization (Price > 0, reasonable Volume).
- **[MODIFY] [orders.py](file:///e:/Openclaw/aureus/workspace/aureus/services/aureus-signal/engine/orders.py)**
    - Add `expiry` support to orders (Step #18).
    - Implement `signed_command` validation placeholder.

### 3. Logic & Operational Visibility ([analytics])
- **[MODIFY] [live_engine.py](file:///e:/Openclaw/aureus/workspace/aureus/services/aureus-signal/engine/live_engine.py)**
    - Implement **Fallback Scoring**: 7/10 (SMC only) vs 8/10 (AI Required).
    - Add `latency_ms` tracking for tick-to-state processing.
    - Implement **MT4 Heartbeat** mechanism (publish to Redis heartbeat stream).
- **[MODIFY] [main.py (Dashboard)](file:///e:/Openclaw/aureus/workspace/aureus/services/aureus-dashboard/api/main.py)**
    - Expose `latency_ms` and MT4 connection status (Heartbeat).
- **[MODIFY] [schema.sql](file:///e:/Openclaw/aureus/workspace/aureus/services/aureus-db-writer/schema.sql)**
    - Update `aureus_ai_analysis` or `aureus_signals` to include `ai_reasoning` and `ai_confidence` (Step #44).

## Verification Plan

### Automated Tests
- Benchmark `orjson` vs `json` performance.
- Unit tests for `RateLimiter` at the Gateway levels.
- Simulation of "Bad AI Health" to trigger Fallback Scoring.
- Verify Msgpack serialization/deserialization across streams.

### Manual Verification
- Flooding the Gateway with rác data to see if Rate Limit kicks in.
- Checking Dashboard for latency warnings and Heartbeat status.
