# ROADMAP

## Archived Milestones

| Version | Name | Phases | Status |
|---------|------|--------|--------|
| v1.1 | Signal Optimization | 07-13 | ✅ Shipped 2026-03-22 |
| v1.2 | Strategy Sequence Engine | 14-15 | ✅ Shipped 2026-03-22 |
| v1.3 | Backtesting & Measurement Engine | 15.5-20 | ✅ Closed 2026-04-03 (known gaps logged) |

---

## Current Milestone: v1.4 TradingAgents Market Data Integration

**Goal:** Integrate TradingAgents market data through a provider abstraction and shadow-gated rollout without breaking the Redis-first ingest pipeline.

**Phases:** 6

| Phase | Name | Requirements | Status |
|---|---|---|---|
| 21 | Prerequisites & Compatibility Validation | PREP-01→02 | PLANNED |
| 22 | Provider Abstraction Extraction | PROV-01→03 | PLANNED |
| 23 | TradingAgents Adapter Implementation | ADPT-01→04 | PLANNED |
| 24 | Runtime Routing & Shadow Integration | ROUT-01→02 | PLANNED |
| 25 | Rollout Gates & Safe Fallback | ROUT-03→04 | PLANNED |
| 26 | Verification & Readiness Evidence | TEST-01→04 | PLANNED |

---

## Phase 21: Prerequisites & Compatibility Validation

**Requirements:** PREP-01, PREP-02
**Goal:** Confirm TradingAgents compatibility, symbol mapping feasibility, and dependency strategy before implementation.

**Success Criteria:**
1. Compatibility report from isolated Docker-on-WSL test documents symbol support (`XAUUSD`, `BTCUSD`, configured universe), average API latency, and observed free-tier rate limits.
2. Dependency strategy is chosen and documented with rollback path.
3. If FX/metal compatibility fails acceptance criteria, milestone is explicitly paused and provider pivot recommendation is documented before any implementation phase starts.

---

## Phase 22: Provider Abstraction Extraction

**Requirements:** PROV-01, PROV-02, PROV-03
**Goal:** Introduce provider abstraction while preserving Redis behavior as default baseline.

**Success Criteria:**
1. Market data provider interface exists with canonical candle contract.
2. Redis implementation is extracted without behavior regression.
3. Backward-compatible client construction path remains available.

---

## Phase 23: TradingAgents Adapter Implementation

**Requirements:** ADPT-01, ADPT-02, ADPT-03, ADPT-04
**Goal:** Add TradingAgents adapter with symbol mapping, normalization, caching, and error observability.

**Success Criteria:**
1. Adapter emits canonical candle payloads for mapped symbols.
2. Cache/backoff controls reduce rate-limit risk under configured cadence.
3. Error taxonomy is emitted for malformed/rate-limit/fallback scenarios.
4. Adapter behavior is isolated behind provider abstraction.

---

## Phase 24: Runtime Routing & Shadow Integration

**Requirements:** ROUT-01, ROUT-02
**Goal:** Add runtime provider mode routing and shadow integration with Redis as default.

**Success Criteria:**
1. Runtime mode selection (`redis|shadow|tradingagents`) is config-driven and validated.
2. Shadow mode performs comparison without disrupting Redis primary flow.
3. Runtime logs/metrics expose source attribution for troubleshooting.

---

## Phase 25: Rollout Gates & Safe Fallback

**Requirements:** ROUT-03, ROUT-04
**Goal:** Enforce drift/lag/error gates and automatic safety fallback.

**Success Criteria:**
1. Gate thresholds are codified for malformed payloads, fallback bursts, lag, and drift.
2. Gate failure path prevents unsafe TradingAgents promotion.
3. Redis fallback behavior is deterministic and observable.

---

## Phase 26: Verification & Readiness Evidence

**Requirements:** TEST-01, TEST-02, TEST-03, TEST-04
**Goal:** Deliver automated and manual verification evidence for milestone acceptance.

**Success Criteria:**
1. Provider, adapter, and gate tests are implemented and passing.
2. Shadow validation checklist can be executed end-to-end.
3. Milestone readiness summary includes evidence for/against primary promotion.

---

## Next Up

**Phase 21: Prerequisites & Compatibility Validation** — establish feasibility constraints before code-level integration.

`/gsd-discuss-phase 21`

<sub>`/clear` first → fresh context window</sub>
