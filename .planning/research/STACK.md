# STACK

## Scope
Research stack additions/changes needed for **v1.4 TradingAgents Market Data Integration** in Aureus.

## Existing Baseline
- `aureus-nautilus-node` currently ingests via Redis stream (`xread`) and publishes Nautilus-compatible bars.
- Runtime/config is Python-based with environment-driven settings.
- Rollout safety exists via `rollout_gates.py`.

## Recommended Stack Additions

### 1) Provider abstraction in-node (required)
- Add internal provider protocol/module in `services/aureus-nautilus-node`.
- Keep Redis provider as default implementation.
- Add TradingAgents provider as optional implementation.

### 2) TradingAgents dependency strategy
- Prefer **optional dependency** in node service (feature-flagged by provider mode).
- If package volatility/rate-limit constraints are high, allow migration path to sidecar service later.

### 3) Cache + throttle primitives
- Add in-adapter TTL cache (`AUREUS_TA_CACHE_TTL_SECONDS`) to avoid REST over-polling.
- Add lightweight backoff/fallback controls at adapter boundary.

### 4) Symbol mapping configuration
- Add `AUREUS_TRADINGAGENTS_SYMBOL_MAP` as JSON map (Aureus symbol → provider symbol).
- Validate required mappings on startup for configured symbol universe.

## Integration Constraints
- Maintain backward-compatible default mode: `redis`.
- Ensure shadow mode can run without changing existing live execution contracts.
- Keep output payload schema fixed: `open/high/low/close/volume/timestamp`.

## What Not To Add (now)
- No immediate cross-service architecture rewrite.
- No direct production cutover to TradingAgents before shadow drift gates pass.
