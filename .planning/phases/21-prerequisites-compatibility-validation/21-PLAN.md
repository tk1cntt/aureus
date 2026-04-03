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

# Phase 21 Plan: TradingAgents Compatibility Validation (Docker on WSL)

## Objective

Validate TradingAgents compatibility with Aureus symbol universe in an isolated Docker-on-WSL environment. Produce a measurable compatibility report and apply hard-stop/pivot gate before any integration code.

## must_haves (goal-backward verification)

1. Docker test container runs TradingAgents successfully on WSL
2. Symbol compatibility tested for XAUUSD and BTCUSD
3. Latency measurements recorded (L1 upstream, L2 internal publish)
4. Rate-limit behavior documented under W1 and W2 workloads
5. Compatibility report produced with explicit PROCEED or PAUSE_AND_PIVOT decision
6. Integration option recommendation (decision provider vs data extraction vs direct API)

---

## Task 1: Create aureus-trading-agents service scaffold

<read_first>
- implementation_plan_tradingagents.md (SWOT analysis and original plan)
- .planning/phases/21-prerequisites-compatibility-validation/21-RESEARCH.md (research findings)
- .planning/phases/21-prerequisites-compatibility-validation/21-CONTEXT.md (locked decisions D-01 through D-22)
</read_first>

<action>
Create directory `services/aureus-trading-agents/` with:

1. `requirements.txt`:
```
tradingagents>=0.2.3
aiohttp>=3.9.0
```

2. `Dockerfile`:
```dockerfile
FROM python:3.13-slim

WORKDIR /app

# System deps for compilation
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
ALPHA_VANTAGE_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here
```

4. `README.md` with service purpose and usage instructions.
</action>

<acceptance_criteria>
- `services/aureus-trading-agents/` directory exists
- `services/aureus-trading-agents/Dockerfile` contains `FROM python:3.13-slim`
- `services/aureus-trading-agents/requirements.txt` contains `tradingagents`
- `services/aureus-trading-agents/.env.example` contains `ALPHA_VANTAGE_API_KEY`
</acceptance_criteria>

---

## Task 2: Create compatibility test script

<read_first>
- .planning/phases/21-prerequisites-compatibility-validation/21-RESEARCH.md (API surface, propagate() usage)
- .planning/phases/21-prerequisites-compatibility-validation/21-CONTEXT.md (D-06 through D-13 thresholds)
</read_first>

<action>
Create `services/aureus-trading-agents/test_compatibility.py` that:

1. **Test 1 — Import & Install Check:**
   - `import tradingagents`
   - Print version, installed path

2. **Test 2 — Symbol Compatibility (W1 baseline):**
   - Call `TradingAgentsGraph.propagate("XAUUSD", <today>)`
   - Call `TradingAgentsGraph.propagate("BTCUSD", <today>)`
   - Record: success/fail, error message if failed, response structure

3. **Test 3 — Data Tool Extraction:**
   - Attempt to access TradingAgents' internal data-fetching tools directly
   - Import from `tradingagents.dataflows` or equivalent module
   - Try to fetch raw OHLCV for XAUUSD, BTCUSD
   - Record: available endpoints, data format, fields present

4. **Test 4 — Latency Measurement:**
   - Time each `propagate()` call (L1 — upstream fetch latency)
   - Time data tool raw fetch separately if available
   - Run W1 workload: 2 symbols × poll every 60s × 30 minutes
   - Calculate: avg, p50, p95, p99 for each operation

5. **Test 5 — Rate-limit Behavior:**
   - Run W2 workload: 6 symbols × poll every 15s × 20 minutes
   - Count: total requests, 429 errors, throttle events, consecutive throttle bursts
   - Calculate: 429 rate, max consecutive burst, retry success rate

6. **Test 6 — Alpha Vantage Direct Comparison:**
   - Call Alpha Vantage API directly for XAUUSD (FX endpoint) and BTCUSD (crypto endpoint)
   - Record: OHLCV availability, latency, rate-limit behavior
   - Compare with TradingAgents wrapper results

7. **Output:** Write JSON results to `/app/output/results.json` with structure:
```json
{
  "timestamp": "ISO8601",
  "environment": {"python": "3.13", "tradingagents": "version", "docker": true},
  "symbol_compatibility": {"XAUUSD": {"status": "pass|fail", "error": null}, ...},
  "data_extraction": {"available": true|false, "ohlcv_fields": [...], "format": "..."},
  "latency": {"L1": {"avg_ms": N, "p50_ms": N, "p95_ms": N, "p99_ms": N}, "L2": {...}},
  "rate_limit": {"total_requests": N, "throttle_429": N, "rate_pct": N, "max_burst": N, "retry_success_rate": N},
  "alpha_vantage_direct": {"xauusd": {...}, "btcusd": {...}},
  "recommendation": "option_a|option_b|option_c|pivot",
  "decision": "PROCEED_TO_PHASE_22|PAUSE_AND_PIVOT"
}
```

8. **Apply go/no-go logic** from D-08 through D-15:
   - Symbol hard gate: XAUUSD and BTCUSD must succeed in W1
   - Rate-limit gate: 429 rate ≤ 1%, no burst > 3
   - Latency gate: L1 avg ≤ 800ms, p95 ≤ 1500ms
   - Auto-determine recommendation based on test results
</action>

<acceptance_criteria>
- `services/aureus-trading-agents/test_compatibility.py` exists
- Script imports `tradingagents` and handles ImportError gracefully
- Script tests both XAUUSD and BTCUSD symbols
- Script measures and reports latency (avg, p95)
- Script counts rate-limit events (429 errors)
- Script outputs JSON to `/app/output/results.json`
- Script prints PROCEED_TO_PHASE_22 or PAUSE_AND_PIVOT at end
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
# Build the test container
cd services/aureus-trading-agents
docker build -t aureus-ta-validation:test .

# Create .env from .env.example with actual API keys
cp .env.example .env
# (user fills in ALPHA_VANTAGE_API_KEY and OPENAI_API_KEY)

# Run the validation
docker run --rm \
  --env-file .env \
  -v $(pwd)/output:/app/output \
  aureus-ta-validation:test

# Check results
cat output/results.json | python -m json.tool
```

Note: This task requires user to provide API keys. The script must handle missing keys gracefully and report which tests were skipped.
</action>

<acceptance_criteria>
- Docker image builds successfully (`aureus-ta-validation:test`)
- Container runs without crash
- `output/results.json` is produced with all required sections
- Script handles missing API keys by skipping relevant tests and reporting them
</acceptance_criteria>

---

## Task 4: Generate compatibility report

<read_first>
- services/aureus-trading-agents/output/results.json (test output)
- .planning/phases/21-prerequisites-compatibility-validation/21-CONTEXT.md (D-20, D-21, D-22 — report structure)
</read_first>

<action>
Parse `results.json` and generate `.planning/phases/21-prerequisites-compatibility-validation/21-COMPATIBILITY-REPORT.md` with required sections:

1. **Environment** — Docker version, Python version, TradingAgents version, WSL distro
2. **Test Matrix** — symbols tested, cadence, duration for W1/W2
3. **Latency Results** — table with avg/p50/p95/p99 for L1 and L2
4. **Rate-limit Results** — total requests, 429 count, burst max, retry success rate
5. **Symbol Compatibility** — per-symbol pass/fail with error details
6. **Integration Option Analysis** — viability assessment for Option A (decision provider), Option B (data extraction), Option C (direct API)
7. **Decision** — `PROCEED_TO_PHASE_22` or `PAUSE_AND_PIVOT` with justification
8. **Pivot Recommendation** (if fail) — alternative provider + impact assessment
</action>

<acceptance_criteria>
- `21-COMPATIBILITY-REPORT.md` exists in phase directory
- Report contains all 8 sections from D-21
- Decision field is explicitly `PROCEED_TO_PHASE_22` or `PAUSE_AND_PIVOT`
- Report references actual measured values from results.json, not placeholder estimates
</acceptance_criteria>

---

## Verification

```bash
# 1. Verify scaffold exists
test -d services/aureus-trading-agents && echo "PASS: service dir exists"
test -f services/aureus-trading-agents/Dockerfile && echo "PASS: Dockerfile exists"
test -f services/aureus-trading-agents/test_compatibility.py && echo "PASS: test script exists"
test -f services/aureus-trading-agents/requirements.txt && echo "PASS: requirements exists"

# 2. Verify Docker build (on WSL)
docker build -t aureus-ta-validation:test services/aureus-trading-agents/ && echo "PASS: Docker build"

# 3. Verify report
test -f .planning/phases/21-prerequisites-compatibility-validation/21-COMPATIBILITY-REPORT.md && echo "PASS: report exists"
grep -q "PROCEED_TO_PHASE_22\|PAUSE_AND_PIVOT" .planning/phases/21-prerequisites-compatibility-validation/21-COMPATIBILITY-REPORT.md && echo "PASS: decision present"
```

---

*Phase: 21-prerequisites-compatibility-validation*
*Plan created: 2026-04-03*
