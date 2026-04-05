# Phase 24: Runtime Routing & Shadow Integration - Research

## 1. Domain Investigation
The goal is to introduce runtime provider routing (`redis_primary`, `ta_shadow`, `ta_primary`) within `aureus-signal`. By default, the system remains on `redis_primary`. We need to dynamically toggle this mode using Redis pub/sub (configured on `aureus:sys:config`) without requiring a service reboot. 

Furthermore, `shadow_mode` (or `ta_shadow`) allows us to run TradingAgents as a background task out-of-band so it does not block the real-time Redis tick loop. The AI signals generated in shadow mode are persisted in a separate Redis namespace (`aureus:ai:shadow:{symbol}`) and later sent to TimescaleDB for baseline/drift analysis.

## 2. Codebase Context
- **Live Engine (`live_engine.py`)**: 
  - Subscribes to `aureus:sys:config` for global configuration using `global_command_stream_listener`. 
  - Can implement hot-swappable modes for providers here.
  - Currently, `FeatureFlag` class (`feature_flags.py`) provides an easy way to cache and poll Redis-backed config keys.
- **Provider Interfaces (`providers/base.py`)**:
  - `DecisionProvider` is already implemented by `TradingAgentsProvider`.
- **TradingAgents Adapter (`providers/tradingagents.py`)**:
  - Exposes `get_decision()`. It already caches and performs external API calls. However, in shadow mode, we shouldn't block the candle calculation thread with these calls.
- **AI Pulse worker (`live_engine.py`)**: 
  - We already use `brain_worker`, `queue_periodic_ai_analysis`, and `execute_pulse` to offload standard LLM insights into an AI PriorityQueue. 
  - The TradingAgents shadow executor could reuse a similar asynchronous Queue pattern to prevent blocking the `live_engine`.

## 3. Implementation Requirements
- **ROUT-01 (Routing)**: Implement a feature flag `aureus:config:provider_mode` taking values `redis_primary`, `ta_shadow`, and `ta_primary`. Modify `live_engine.py` (or `strategy_executor.py` / `signal_computer.py`) to determine whose decisions are fed into actual evaluation.
- **ROUT-02 (Shadow Execution)**: If the mode is `ta_shadow`, we still process `redis` as primary. Meanwhile, an asynchronous async wrapper (`asyncio.create_task` or a dedicated queue) triggers `TradingAgentsProvider.get_decision()` in the background. The result is written to `aureus:ai:shadow:{symbol}` and metrics/logs are emitted.

## 4. Dependencies & Impact
- **Dependencies**: TimescaleDB for saving shadow results, Redis for `feature_flags`.
- **Impact Risks**: Spawning unbounded background tasks per tick/candle could exhaust limits or rate limits. We must ensure rate limiting (via `cache_ttl` in the adapter) applies effectively in shadow mode.

## Validation Architecture
To prove this feature works:
- **Unit testing `live_engine.py` / `feature_flags.py`**: Validate the behavior toggles correctly upon receiving `provider_mode` updates.
- **Shadow Mode Isolation Test**: Guarantee that slow `get_decision()` calls in shadow mode drop 0 frames/ticks on the primary pipeline.
- **Telemetry Validation**: Prove `aureus:ai:shadow:{symbol}` keys are emitted successfully.

## RESEARCH COMPLETE
