# Phase 25: Rollout Gates & Safe Fallback - Research

## Architectural Assessment

1. **Gate Evaluation (Async/Observer)**
   The Aureus signal loop is a high-frequency ticker. Polling external systems (like TradingAgents) for lag or evaluating drift synchronously would block the main thread. 
   - **Pattern needed:** A background `asyncio` task or an explicit observer thread inside `TradingAgentsProvider` (or a dedicated `Observer` class) that periodically compares TA output vs Redis baseline.
   - **Metrics required:** Request latency (lag) and output signal divergence (drift).

2. **Circuit Breaker Pattern**
   - My codebase scan confirmed there is no prominent `CircuitBreaker` utility existing in `aureus-signal`.
   - **Pattern needed:** A lightweight finite state machine with three states:
     - `CLOSED`: Normal operations, TA requests flow through.
     - `OPEN`: Tripped due to errors/lag exceeding threshold. Requests to TA fast-fail and system falls back to Redis primary.
     - `HALF-OPEN`: After a cool-down timeout, allows 1 test request. If it succeeds -> `CLOSED`; if fails -> `OPEN`.
   - **Location:** Recommend placing this inside `services/aureus-signal/common/circuit_breaker.py`.

3. **Drift Observability (TimescaleDB / Prometheus)**
   - Need to persist raw drift telemetry so that we can evaluate TradingAgents accuracy over time in Grafana.
   - If TimescaleDB is used natively in `aureus-signal`, we need a telemetry table payload. However, standard observability in Aureus often uses Prometheus counters/gauges for real-time lag/errors.
   - **Action for Planner:** Decide whether to emit Prometheus metrics (e.g. `aureus_ta_drift_count`) and let a scraper handle it, OR directly write SQL to TimescaleDB (e.g. via asyncpg). Wait, D-03 explicitly says: "Persist shadow drift metrics to a TimescaleDB Event/Telemetry table". So we need an `asyncpg` insertion loop or a batch writer.

## Required Modifications Map
To plan this phase well, the planner must address:
1. `circuit_breaker.py` (NEW): The state machine and configuration (error threshold, timeout).
2. `tradingagents_provider.py` (MODIFY):
   - Wrap upstream API calls in the `CircuitBreaker`.
   - Implement the Async Observer that runs periodically.
3. `telemetry_db.py` (NEW/MODIFY):
   - TimescaleDB connection logic / `INSERT` statement for telemetry drift data.
4. `config/settings.py` (MODIFY): Add threshold configs (e.g., `TA_CIRCUIT_BREAKER_ERRORS=5`, `TA_CIRCUIT_BREAKER_TIMEOUT=60s`).

## Validation Architecture
- **Unit Tests:** `test_circuit_breaker.py` to ensure state transitions work. `test_tradingagents_provider_fallback.py` to verify Redis gracefully takes over when CB is OPEN.
- **Integration Tests:** A mock TA setup that intentionally delays responses to trip the Circuit Breaker and verifies the fallback behavior.

## RESEARCH COMPLETE
