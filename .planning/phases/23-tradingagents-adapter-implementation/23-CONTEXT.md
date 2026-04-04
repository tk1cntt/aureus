# Phase 23: TradingAgents Adapter Implementation - Context

**Gathered:** 2026-04-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Implementation of the TradingAgents adapter to connect `aureus-trading-agents` with `aureus-signal`. Responsible for generating AI trading decisions securely and routing them back to the Aureus engine over HTTP, ensuring isolation and performance integrity through cache and fallback mechanisms.

</domain>

<decisions>
## Implementation Decisions

### Interface Target
- **D-01:** Implement `DecisionProvider` solely for TradingAgents integration rather than `MarketDataProvider`. OHLCV fetching remains exclusively on Redis as decided in Phase 21.

### Symbol Mapping Approach
- **D-02:** Use a static `symbols.json` file to map Aureus internal symbols (e.g. `XAUUSD`) to TradingAgents acceptable formats. Allows hot-swapping and easy configuration without code rebuilds.

### Cache & Backoff Strategy
- **D-03:** Employ an In-memory dict with TTL inside the adapter. It avoids unnecessary Redis IO latency for ephemeral state and resets naturally upon process restart.

### Error & Fallback Handling
- **D-04:** Silently yield `None` upon reaching rate limits or 500 errors. Acts as a "pass-through", letting the `aureus-signal` engine log the exception and fallback securely to native OHLCV behavior.

### the agent's Discretion
- Dict TTL duration specifics (e.g. 60 seconds vs 15 seconds based on TA polling intervals).
- Granular JSON schema design for `symbols.json`.
- Default fallback mapping behavior if a symbol is missing in JSON.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Prior Phase Requirements
- `.planning/phases/21-prerequisites-compatibility-validation/21-CONTEXT.md` — D-23 specifying exact pivot to DecisionProvider Option A.
- `.planning/phases/22-provider-abstraction-extraction/22-CONTEXT.md` — D-01 dual interface architecture specifications and interface definitions.

### Engine Architecture
- `services/aureus-signal/engine/providers/base.py` — Location of the `DecisionProvider` contract to implement.

</canonical_refs>

<code_context>
## Existing Code Insights

### Established Patterns
- TradingAgents wrapper should follow the interface blueprint present in `Engine/Providers`.

### Reusable Assets
- Existing `.json` configuration loader utilities if present inside `aureus-signal/utils`.

</code_context>

<specifics>
## Specific Ideas

No specific requirements beyond ensuring zero breakage to the primary Redis stream ingestion loop.

</specifics>

<deferred>
## Deferred Ideas

None — analysis stayed within phase scope.

</deferred>
