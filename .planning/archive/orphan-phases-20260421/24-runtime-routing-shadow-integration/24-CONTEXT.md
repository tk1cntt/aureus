# Phase 24: Runtime Routing & Shadow Integration - Context

**Gathered:** 2026-04-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Implementing runtime provider mode routing (`redis`, `shadow`, `tradingagents`) for the new DecisionProvider in `aureus-signal`. Ensuring shadow mode safely isolates AI signals and reports metrics without disrupting the primary engine loop.

</domain>

<decisions>
## Implementation Decisions

### Configuration Strategy
- **D-01:** Feature mode configuration (`redis_primary`, `ta_shadow`, `ta_primary`) must be dynamically hot-swappable via Redis channel `aureus:sys:config`. Do not rely solely on reboot-requiring environment variables to switch modes.

### Shadow Execution Model
- **D-02:** TA shadow execution must run asynchronously (e.g. background tasks or fire-and-forget events) and MUST NOT block the primary Redis tick loop, preventing engine lag from long LLM response times.

### Shadow State Isolation
- **D-03:** AI shadow decisions must be isolated into a dedicated Redis namespace (e.g., `aureus:ai:shadow:{symbol}`) to cleanly separate them from live signals (`aureus:ai:latest:{symbol}`) that existing UI dashboards consume.

### Drift and Validation Baseline
- **D-04:** For the baseline comparison and drift analysis, write shadow output to telemetry (TimescaleDB / Prometheus) for offline PnL and drift analysis, rather than performing synchronous live comparisons that block engine flow.

### Accumulated Prior Decisions
- **D-23 (Ph21):** TradingAgents acts exclusively as a decision provider (BUY/SELL/HOLD), not a data provider. Redis maintains OHLCV.
- **D-18 (Ph21):** Default provider mode is `redis_primary`.
- **D-01 (Ph22):** Provider interface consists of MarketDataProvider and DecisionProvider.
- **D-04 (Ph23):** Adapters must silently yield `None` to pass through errors and allow the engine to fallback seamlessly.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Prior Phase Requirements
- `.planning/phases/21-prerequisites-compatibility-validation/21-CONTEXT.md` — Provider strategy (Option A, Provider isolation).
- `.planning/phases/22-provider-abstraction-extraction/22-CONTEXT.md` — Dual Interface specifications.
- `.planning/phases/23-tradingagents-adapter-implementation/23-CONTEXT.md` — Adapter fallback configurations.

### Architecture
- `.planning/codebase/ARCHITECTURE.md` — Signal processing layer specifications.
- `.planning/codebase/INTEGRATIONS.md` — Redis pub/sub config integration guidelines.
</canonical_refs>

<deferred>
## Deferred Ideas

- Không có ý tưởng nào bị trì hoãn.

</deferred>
