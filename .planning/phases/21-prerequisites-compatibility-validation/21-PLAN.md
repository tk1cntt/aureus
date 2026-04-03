---
phase: 21
wave: 1
depends_on: []
files_modified:
  - services/aureus-trading-agents/Dockerfile
  - services/aureus-trading-agents/test_compatibility.py
  - services/aureus-trading-agents/requirements.txt
  - .planning/phases/21-prerequisites-compatibility-validation/21-COMPATIBILITY-REPORT.md
autonomous: true
requirements_addressed: [PREP-01, PREP-02]
---

# Phase 21 Plan: TradingAgents Decision Provider Validation (Docker on WSL)

## Objective

Validate TradingAgents as a **decision provider** (Option A) for Aureus in an isolated Docker-on-WSL environment. Test whether `propagate(ticker, date)` returns valid Buy/Sell/Hold decisions for `XAUUSD` and `BTCUSD`. Produce a compatibility report and apply hard-stop/pivot gate.

**Scope:** Only Option A (AI decision signals). NOT testing OHLCV data extraction or direct Alpha Vantage API.

## must_haves (goal-backward verification)

1. Docker test container runs TradingAgents successfully on WSL
2. `propagate("XAUUSD", date)` returns a valid trading decision
3. `propagate("BTCUSD", date)` returns a valid trading decision
4. Decision latency measured and documented
5. Rate-limit behavior under Alpha Vantage free tier documented
6. LLM cost estimate per decision call documented
7. Compatibility report produced with explicit PROCEED or PAUSE_AND_PIVOT decision

---

## Task 1: Create aureus-trading-agents service scaffold

<read_first>
- .planning/phases/21-prerequisites-compatibility-validation/21-RESEARCH.md
- .planning/phases/21-prerequisites-compatibility-validation/21-CONTEXT.md (D-01 through D-05, D-23)
</read_first>

<action>
Create directory `services/aureus-trading-agents/` with:

1. `requirements.txt`:
```
tradingagents>=0.2.3
```

2. `Dockerfile`:
```dockerfile
FROM python:3.13-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ git && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "test_compatibility.py"]
```

3. `.env.example`:
```
# Required: LLM provider (at least one)
OPENAI_API_KEY=your_key_here
# GOOGLE_API_KEY=your_key_here
# ANTHROPIC_API_KEY=your_key_here

# Required: Market data backend
ALPHA_VANTAGE_API_KEY=your_key_here
```

4. `README.md` explaining this is the Phase 21 validation container for TradingAgents decision provider compatibility.
</action>

<acceptance_criteria>
- `services/aureus-trading-agents/` directory exists
- `services/aureus-trading-agents/Dockerfile` contains `FROM python:3.13-slim`
- `services/aureus-trading-agents/requirements.txt` contains `tradingagents`
- `services/aureus-trading-agents/.env.example` contains `OPENAI_API_KEY` and `ALPHA_VANTAGE_API_KEY`
</acceptance_criteria>

---

## Task 2: Create decision provider compatibility test script

<read_first>
- .planning/phases/21-prerequisites-compatibility-validation/21-RESEARCH.md (propagate() API, TradingAgentsGraph usage)
- .planning/phases/21-prerequisites-compatibility-validation/21-CONTEXT.md (D-06 through D-13 thresholds, D-23 Option A)
</read_first>

<action>
Create `services/aureus-trading-agents/test_compatibility.py`:

1. **Test 1 — Import & Install Check:**
   - `from tradingagents.graph.trading_graph import TradingAgentsGraph`
   - `from tradingagents.default_config import DEFAULT_CONFIG`
   - Print version, confirm import success

2. **Test 2 — XAUUSD Decision (HARD GATE):**
   - `config = DEFAULT_CONFIG.copy()`
   - `ta = TradingAgentsGraph(debug=True, config=config)`
   - `_, decision = ta.propagate("XAUUSD", "<yesterday_date>")`
   - Record: success/fail, decision content (buy/sell/hold), reasoning text, elapsed time

3. **Test 3 — BTCUSD Decision (HARD GATE):**
   - Same as Test 2 but with `"BTCUSD"`
   - Record same metrics

4. **Test 4 — Decision Quality Check:**
   - Validate decision contains actionable signal (buy/sell/hold keyword)
   - Validate reasoning text is non-empty
   - Check response structure completeness

5. **Test 5 — Latency Profile:**
   - Run 3 decision calls per symbol (6 total)
   - Measure wall-clock time per call
   - Calculate: avg, min, max, p95

6. **Test 6 — Rate-limit & Cost Estimation:**
   - Count Alpha Vantage API calls triggered by each `propagate()` (monitor stderr/logs)
   - Document any 429 errors
   - Estimate LLM token usage and cost per decision

7. **Output:** Write JSON results to `/app/output/results.json`:
```json
{
  "timestamp": "ISO8601",
  "environment": {"python": "3.13", "tradingagents": "version"},
  "symbol_tests": {
    "XAUUSD": {"status": "pass|fail", "decision": "buy|sell|hold", "reasoning_length": N, "error": null},
    "BTCUSD": {"status": "pass|fail", "decision": "buy|sell|hold", "reasoning_length": N, "error": null}
  },
  "latency": {"avg_s": N, "min_s": N, "max_s": N, "p95_s": N, "per_call": [...]},
  "rate_limit": {"total_av_calls": N, "throttle_429": N, "max_burst": N},
  "cost_estimate": {"llm_tokens_per_call": N, "estimated_cost_usd_per_call": N},
  "decision": "PROCEED_TO_PHASE_22|PAUSE_AND_PIVOT",
  "decision_reason": "..."
}
```

8. **Apply go/no-go logic** from D-08 through D-13:
   - XAUUSD and BTCUSD must return valid decisions (D-08)
   - Latency avg ≤ 30s, p95 ≤ 60s (D-09)
   - Decision contains actionable signal (D-10)
   - Rate-limit ≤ 1%, no burst > 3 (D-11)
</action>

<acceptance_criteria>
- `services/aureus-trading-agents/test_compatibility.py` exists
- Script imports `TradingAgentsGraph` and handles ImportError
- Script calls `propagate("XAUUSD", date)` and `propagate("BTCUSD", date)`
- Script measures and reports latency per call
- Script outputs JSON to `/app/output/results.json`
- Script prints `PROCEED_TO_PHASE_22` or `PAUSE_AND_PIVOT` at end
</acceptance_criteria>

---

## Task 3: Build and run Docker validation on WSL

<read_first>
- services/aureus-trading-agents/Dockerfile
- services/aureus-trading-agents/test_compatibility.py
- .planning/phases/21-prerequisites-compatibility-validation/21-CONTEXT.md (D-04, D-05)
</read_first>

<action>
On WSL, execute:

```bash
cd services/aureus-trading-agents

# Build
docker build -t aureus-ta-validation:test .

# Prepare env
cp .env.example .env
# User fills: OPENAI_API_KEY, ALPHA_VANTAGE_API_KEY

# Run
mkdir -p output
docker run --rm \
  --env-file .env \
  -v $(pwd)/output:/app/output \
  aureus-ta-validation:test

# Check
cat output/results.json | python3 -m json.tool
```

**Note:** Requires user-provided API keys. Script handles missing keys gracefully.
</action>

<acceptance_criteria>
- Docker image `aureus-ta-validation:test` builds successfully
- Container runs without crash
- `output/results.json` is produced
- Script reports missing API keys instead of crashing if keys absent
</acceptance_criteria>

---

## Task 4: Generate compatibility report

<read_first>
- services/aureus-trading-agents/output/results.json
- .planning/phases/21-prerequisites-compatibility-validation/21-CONTEXT.md (D-20, D-21, D-22)
</read_first>

<action>
Parse `results.json` and generate `21-COMPATIBILITY-REPORT.md` in phase directory:

1. **Environment** — Docker, Python, TradingAgents version, LLM provider used
2. **Test Matrix** — symbols tested, number of calls, test duration
3. **Symbol Compatibility** — per-symbol pass/fail with decision content
4. **Decision Quality** — signal type (buy/sell/hold), reasoning quality assessment
5. **Latency Results** — avg/min/max/p95 per `propagate()` call
6. **Rate-limit Results** — Alpha Vantage call count, 429 events, burst behavior
7. **Cost Estimate** — LLM tokens/cost per decision, projected monthly cost at target cadence
8. **Decision** — `PROCEED_TO_PHASE_22` or `PAUSE_AND_PIVOT`
9. **Pivot Recommendation** (if fail) — alternative approach + impact
</action>

<acceptance_criteria>
- `21-COMPATIBILITY-REPORT.md` exists in phase directory
- Report contains all 8+ sections from D-21
- Decision field is `PROCEED_TO_PHASE_22` or `PAUSE_AND_PIVOT`
- Report uses actual measured values, not placeholders
</acceptance_criteria>

---

## Verification

```bash
# 1. Scaffold
test -d services/aureus-trading-agents && echo "PASS: service dir"
test -f services/aureus-trading-agents/Dockerfile && echo "PASS: Dockerfile"
test -f services/aureus-trading-agents/test_compatibility.py && echo "PASS: test script"

# 2. Docker build (WSL)
docker build -t aureus-ta-validation:test services/aureus-trading-agents/ && echo "PASS: build"

# 3. Report
test -f .planning/phases/21-prerequisites-compatibility-validation/21-COMPATIBILITY-REPORT.md && echo "PASS: report"
grep -q "PROCEED_TO_PHASE_22\|PAUSE_AND_PIVOT" .planning/phases/21-prerequisites-compatibility-validation/21-COMPATIBILITY-REPORT.md && echo "PASS: decision"
```

---

*Phase: 21-prerequisites-compatibility-validation*
*Plan created: 2026-04-03 (revised: Option A only)*
