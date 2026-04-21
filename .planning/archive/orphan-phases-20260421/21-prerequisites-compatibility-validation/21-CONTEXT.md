# Phase 21: Prerequisites & Compatibility Validation - Context

**Gathered:** 2026-04-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Validate TradingAgents as a **decision provider** (Option A — AI trading signals, NOT raw OHLCV data) in an isolated Docker-on-WSL environment before any integration code begins. Produce a compatibility report covering symbol support, decision quality, latency, and rate-limit behavior. Apply hard-stop/pivot gate based on measurable criteria.

</domain>

<decisions>
## Implementation Decisions

### Service Architecture (LOCKED)
- **D-01:** TradingAgents runs as a **separate service** `aureus-trading-agents` (own container/repo directory).
- **D-02:** Integration target is `services/aureus-signal`, **NOT** `services/aureus-nautilus-node`.
- **D-03:** Communication contract from `aureus-trading-agents` → `aureus-signal` will be determined after validation passes (likely Redis stream canonical format for minimal code change).

### Integration Approach (LOCKED)
- **D-23:** Use TradingAgents exclusively as a **decision provider** (Option A). The `propagate(ticker, date)` API returns Buy/Sell/Hold decisions with AI reasoning — these are published as supplementary AI signals to `aureus-signal`. Aureus keeps Redis stream as the sole source for OHLCV candle data. OHLCV extraction (Option B) and direct Alpha Vantage API (Option C) are **out of scope**.

### LLM Configuration (LOCKED)
- **D-24:** LLM calls route through local proxy at `http://localhost:20128/v1` (OpenAI-compatible endpoint). Model: `cx/gpt-5.4`. TradingAgents config must set `llm_provider: "openai"`, `OPENAI_API_BASE=http://localhost:20128/v1`, and model names to `cx/gpt-5.4`. Docker container must use `--network host` or equivalent to reach the host proxy.

### Validation Environment
- **D-04:** All validation runs inside **Docker on WSL**. No local virtualenv.
- **D-05:** Single Dockerfile for test container. No docker-compose needed for Phase 21 (validation-only, no integration).

### Workload Definition
- **D-06 (W1 — baseline):** `XAUUSD` + `BTCUSD`, poll every 60s, run 30 minutes.
- **D-07 (W2 — stress):** 6 symbols (2 core + 4 from universe), poll every 15s, run 20 minutes.

### Pass/Fail Thresholds (Go/No-Go)
- **D-08 (Symbol — HARD GATE):** `propagate("XAUUSD", date)` and `propagate("BTCUSD", date)` must return a valid decision (not error) 100% in W1.
- **D-09 (Latency — decision round-trip):** avg ≤ 30s, p95 ≤ 60s (LLM inference is expected to be slow; this is acceptable for batch decision signals).
- **D-10 (Decision quality):** Response must contain actionable signal (buy/sell/hold) with reasoning text.
- **D-11 (Rate-limit):** Alpha Vantage 429/throttle events ≤ 1% of total underlying API calls. No burst of >3 consecutive throttles.
- **D-12 (Retry success):** ≥ 99% of retried requests succeed.
- **D-13 (LLM cost estimate):** Document estimated cost per decision call for budgeting.

### Decision Rule
- **D-14:** Fail any hard gate (D-08, D-11 burst) → **STOP + PIVOT** immediately.
- **D-15:** Soft gate fail (latency slightly over) → allow 1 tuning round (adjust cache/retry), re-test once. Fail again → STOP.

### Dependency Strategy (Post-Validation)
- **D-16:** `aureus-trading-agents` is a sidecar service. TradingAgents dependency is isolated to this container only.
- **D-17:** `aureus-signal` receives data via contract (Redis stream or REST — to be finalized in Phase 22).
- **D-18:** Feature flag in `aureus-signal`: `redis_primary | ta_shadow | ta_primary`. Default: `redis_primary`.
- **D-19:** Rollback: disable `aureus-trading-agents` container → `aureus-signal` stays on Redis primary. Zero code change needed.

### Evidence Report Structure
- **D-20:** Report file: `21-COMPATIBILITY-REPORT.md` in phase directory.
- **D-21:** Required sections: Environment, Test Matrix, Latency Results (L1/L2 avg/p95/p99), Rate-limit Results (total/429/burst/retry), Symbol Compatibility (per-symbol pass/fail), Decision (`PROCEED_TO_PHASE_22` or `PAUSE_AND_PIVOT`), Pivot Recommendation (if fail).
- **D-22:** Hard-stop policy: if decision ≠ `PROCEED_TO_PHASE_22`, no implementation phase may open.

### Agent's Discretion
- Docker base image choice (python:3.11-slim or similar)
- Test script implementation details (async/sync, logging format)
- Cache TTL tuning values during stress test
- Report formatting details beyond required sections

</decisions>

<specifics>
## Specific Ideas

- User wants this to feel like a "quality gate" — measurable, not subjective.
- Must be reproducible: anyone can re-run the Docker test and get comparable results.
- If TradingAgents doesn't support FX/metal symbols at all, stop immediately — don't try workarounds.
- **Option A only:** TradingAgents supplements aureus-signal with AI decisions. It does NOT replace the existing Redis OHLCV data pipeline.

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase requirements
- `.planning/REQUIREMENTS.md` — PREP-01 (Docker-on-WSL validation) and PREP-02 (hard stop/pivot criteria)
- `.planning/ROADMAP.md` §Phase 21 — Success criteria and phase goal

### Architecture context
- `implementation_plan_tradingagents.md` — SWOT analysis, original integration plan, Phase 0 prerequisites
- `.planning/codebase/ARCHITECTURE.md` — Current service topology
- `.planning/codebase/INTEGRATIONS.md` — Existing integration points

### Target integration surface
- `services/aureus-signal/` — Integration target (NOT aureus-nautilus-node)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `aureus-nautilus-node/data_client.py` — `REQUIRED_FIELDS` shows existing candle schema. Not directly relevant for Option A (decision provider), but useful as reference for understanding Aureus data contract.
- Existing Docker infrastructure in project (docker-compose files, WSL setup) for reference.

### Established Patterns
- Redis stream pattern: `aureus:stream:{symbol}:candle` — existing convention for candle delivery.
- Metric naming convention: `duplicates_total`, `malformed_payload_total`, etc.

### Integration Points
- `aureus-signal` engine — `aureus-trading-agents` will publish AI decision signals here (Phase 22+).
- For Phase 21, no integration needed — validation is standalone.

</code_context>

<deferred>
## Deferred Ideas

- Provider abstraction refactor in `aureus-nautilus-node` — Phase 22 scope (and now redirected to aureus-signal integration)
- Shadow mode comparison — Phase 24 scope
- Multi-provider routing — v2 extension

</deferred>

---

*Phase: 21-prerequisites-compatibility-validation*
*Context gathered: 2026-04-03*
