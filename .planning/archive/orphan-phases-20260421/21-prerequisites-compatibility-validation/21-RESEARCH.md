# Phase 21: Prerequisites & Compatibility Validation — Research

**Researched:** 2026-04-03
**Status:** RESEARCH COMPLETE

## Executive Summary

TradingAgents is a **multi-agent LLM framework** for financial research and trading decision-making — it is **NOT** a direct market data provider. Its architecture fundamentally differs from what was initially assumed.

## Key Findings

### 1. TradingAgents Architecture

- **Framework type:** LLM-powered multi-agent system (LangGraph-based)
- **Primary function:** Collaborative AI agents (fundamental analyst, sentiment analyst, technical analyst, trader, risk manager) evaluate market conditions and produce trading **decisions**
- **API surface:** `TradingAgentsGraph.propagate(ticker, date)` → returns a `decision` object, NOT raw OHLCV candle data
- **Data layer:** Delegates to Alpha Vantage / Finnhub for raw market data internally
- **LLM dependency:** Requires LLM API keys (OpenAI, Google, Anthropic, xAI, OpenRouter, or Ollama)

### 2. Symbol Support (Critical for Aureus)

| Symbol | Provider | Support Status |
|--------|----------|----------------|
| XAUUSD | Alpha Vantage FX endpoint | Likely supported (AV has `CURRENCY_EXCHANGE_RATE` for XAU/USD) |
| BTCUSD | Alpha Vantage Crypto endpoint | Likely supported (AV has `DIGITAL_CURRENCY_DAILY`) |
| Equities (NVDA, AAPL) | Alpha Vantage / Finnhub | Confirmed supported (default use case) |

**⚠ Key risk:** TradingAgents passes ticker strings directly to Alpha Vantage. FX/metal tickers may require different API endpoints than equities. Must validate during Docker test.

### 3. Data Flow Mismatch

| Aspect | Aureus Current | TradingAgents |
|--------|---------------|---------------|
| Data format | OHLCV candle stream (real-time) | AI trading decision (batch) |
| Latency | 100ms poll interval | Seconds-to-minutes (LLM inference) |
| Output | `open/high/low/close/volume/timestamp` | Buy/Sell/Hold decision with reasoning |
| Trigger | Continuous stream | On-demand per ticker+date |

### 4. Integration Implications

**Option A — Use TradingAgents as a decision provider (NOT data provider):**
- Aureus keeps Redis stream for candle data
- TradingAgents provides supplementary AI-driven trading signals/decisions
- `aureus-trading-agents` service calls `propagate()` and publishes decisions to `aureus-signal`

**Option B — Extract TradingAgents' data tools directly:**
- Bypass the LLM agent layer
- Use only TradingAgents' internal data-fetching tools (Alpha Vantage wrappers)
- Get raw OHLCV data without LLM overhead

**Option C — Use underlying providers directly (Alpha Vantage / Finnhub):**
- Skip TradingAgents entirely
- Call Alpha Vantage / Finnhub APIs directly from `aureus-trading-agents`
- Simpler, fewer dependencies, more control

### 5. Alpha Vantage Rate Limits (Free Tier)

- **25 requests/day** (free tier as of 2025+)
- **5 requests/minute** (some plans)
- Premium plans: 75-1200 requests/minute
- **Impact:** With 100ms poll interval and multiple symbols, free tier is completely unusable for real-time data

### 6. Dependencies

- Python 3.13 required
- Large dependency tree: LangGraph, LangChain, OpenAI/Anthropic/Google SDKs
- Docker image will be substantial (~2-3GB with all deps)

## Validation Architecture

### What to Validate in Docker Test

1. **Installation feasibility** — Can TradingAgents install cleanly in Docker?
2. **Symbol compatibility** — Does `propagate("XAUUSD", date)` work? Does `propagate("BTCUSD", date)` work?
3. **Data extraction** — Can we access raw OHLCV from TradingAgents' internal tools?
4. **Latency profile** — How long does a full `propagate()` call take? How long does raw data extraction take?
5. **Rate-limit behavior** — How many API calls does one `propagate()` trigger to Alpha Vantage?
6. **Error handling** — What happens with unsupported symbols? Rate-limit errors?

### Critical Decision Point

The validation must answer: **Which integration option (A, B, or C) is viable for Aureus?**

- If Option A (decision provider) works → TradingAgents adds AI signals to complement existing data pipeline
- If Option B (data extraction) works → TradingAgents serves as an alternative data source
- If neither A nor B viable → Option C (direct Alpha Vantage) or pivot to different provider entirely

## Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| TradingAgents doesn't support FX/metal symbols | HIGH | Test in Docker first; have Alpha Vantage direct as fallback |
| Free-tier rate limit makes real-time impossible | HIGH | Validate rate-limit behavior; consider premium tier cost |
| LLM latency too high for real-time decisions | MEDIUM | Measure actual latency; may need async/batch mode |
| Large Docker image slows deployment | LOW | Multi-stage build; cache layers |
| Python 3.13 requirement conflicts with Aureus stack | MEDIUM | Sidecar isolation handles this |

---

*Phase: 21-prerequisites-compatibility-validation*
*Research completed: 2026-04-03*
