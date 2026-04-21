# Phase 22: Provider Abstraction Extraction - Context

**Gathered:** 2026-04-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Introduce provider abstraction into `aureus-signal` engine while preserving Redis behavior as default baseline. This phase creates the **interface contracts only** — no TradingAgents adapter implementation (that's Phase 23).

Deliverables:
1. Two abstract base classes: `MarketDataProvider` (candle OHLCV) and `DecisionProvider` (AI signal BUY/SELL/HOLD).
2. Extract existing Redis candle ingestion into a `RedisMarketDataProvider` implementation.
3. Backward-compatible construction path so existing tests and runtime continue working without config changes.
</domain>

<decisions>
## Implementation Decisions

### D-01: Dual Interface Architecture (Locked)
Create 2 separate provider interfaces, NOT a single unified one:
- `MarketDataProvider` → outputs `CandleRecord` (OHLCV data)
- `DecisionProvider` → outputs `DecisionSignal` (BUY/SELL/HOLD + reasoning)

Rationale: TradingAgents returns decisions, not candle data. Forcing both into one contract would corrupt the abstraction.

### D-02: Provider Location (Locked)
Place provider interfaces inside `services/aureus-signal/engine/providers/`:
```
services/aureus-signal/engine/providers/
├── __init__.py
├── base.py              # ABC: MarketDataProvider, DecisionProvider
├── redis_provider.py    # Extract from live_engine.py
```
Do NOT create a shared `libs/` package yet. Extract later if a second consumer emerges.

### D-03: TradingAgents as Separate Docker Microservice (Locked)
`aureus-trading-agents` remains a standalone Docker service exposing a REST API (FastAPI).
`aureus-signal` calls it via HTTP — does NOT import TradingAgents in-process.

Rationale: Heavy dependency tree, multi-minute LLM execution time, daily cadence (not per-tick).

### Agent's Discretion
- Exact ABC method signatures for `MarketDataProvider` and `DecisionProvider`
- How to extract Redis logic from `live_engine.py` without regression
- `DecisionSignal` dataclass field names
- Whether to use `abc.ABC` or `typing.Protocol`
</decisions>

<canonical_refs>
## Canonical References

### Signal Engine Core
- `services/aureus-signal/engine/state.py` — `CandleRecord` dataclass (the canonical candle contract)
- `services/aureus-signal/engine/live_engine.py` — `execute_signals_for_candle()` (current Redis consumption point)
- `services/aureus-signal/engine/ai_validator.py` — `AIValidator`, `ContextBuilder` (downstream signal consumers)

### TradingAgents Framework
- `services/aureus-trading-agents/TradingAgents/tradingagents/graph/trading_graph.py` — `propagate()` returns `(final_state, processed_signal)`
- `services/aureus-trading-agents/TradingAgents/tradingagents/graph/signal_processing.py` — `SignalProcessor.process_signal()` extracts core decision

### Phase 21 Artifacts
- `.planning/phases/21-prerequisites-compatibility-validation/21-COMPATIBILITY-REPORT.md` — Compatibility validation results
</canonical_refs>

<specifics>
## Specific Ideas
- `DecisionSignal` should include: `action` (BUY/SELL/HOLD), `confidence` (float), `reasoning` (str), `timestamp`, `symbol`, `source` (provider name)
- `MarketDataProvider.get_candle()` should return `Optional[CandleRecord]` to handle missing data gracefully
- Redis provider extraction should be a pure refactor — zero behavior change, verified by existing test suite
</specifics>

<deferred>
## Deferred Ideas
- Shared `libs/aureus-providers/` package (extract when second consumer exists)
- `WebSocketProvider` for real-time streaming (v2)
- Multi-provider aggregation/voting (v2)
</deferred>

---

*Phase: 22-provider-abstraction-extraction*
*Context gathered: 2026-04-03 via interactive discussion*
