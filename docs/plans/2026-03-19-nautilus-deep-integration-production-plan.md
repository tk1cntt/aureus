# Nautilus Deep Integration Production Hardening Implementation Plan

> **For Antigravity:** REQUIRED WORKFLOW: Use `.agent/workflows/execute-plan.md` to execute this plan in single-flow mode.

**Goal:** Upgrade all 5 Slice-2 tasks to production-ready quality for full multi-symbol rollout with strict risk controls (mandatory SL/TP, fail-safe = reject order).

**Architecture:** Keep the existing `aureus-nautilus-node` service but harden it through contract-first validation, deterministic lifecycle control, strict execution guards, and full observability. Roll out via shadow → canary → full production to preserve time-to-market while controlling risk.

**Tech Stack:** Python, Nautilus Trader, Redis Streams, Docker Compose, pytest, Prometheus/Grafana.

---

### Task 1: Runtime Stability + LiveTradingNode Entrypoint (Task 1 hardening)

**Files:**
- Create: `services/aureus-nautilus-node/main.py`
- Modify: `services/aureus-nautilus-node/nautilus_runner.py`
- Modify: `services/aureus-nautilus-node/config.py`
- Modify: `services/aureus-nautilus-node/Dockerfile`
- Modify: `services/aureus-nautilus-node/tests/test_node_setup.py`
- Create: `services/aureus-nautilus-node/tests/test_runtime_lifecycle.py`

**Step 1: Write the failing lifecycle test**

```python
def test_live_node_bootstrap_uses_live_trading_node_and_exposes_health_state():
    ...
```

**Step 2: Run test to verify it fails**

Run: `wsl -d Ubuntu-24.04 -e bash -lc "cd /mnt/d/AIFramework/aureus/services/aureus-nautilus-node && python3 -m pytest tests/test_node_setup.py tests/test_runtime_lifecycle.py -v"`
Expected: FAIL with missing `main.py` lifecycle wiring and/or health state attributes

**Step 3: Implement minimal production bootstrap**

- Add `main.py` as the single entrypoint.
- Construct `LiveTradingNode` from typed config.
- Add startup phases: `BOOTSTRAP -> WARMUP -> LIVE`.
- Add graceful shutdown path (`SIGTERM` / drain).

**Step 4: Update container entrypoint**

- Change Docker CMD to run `python main.py`.
- Keep `PYTHONUNBUFFERED=1` and fail-fast logging.

**Step 5: Run tests to verify pass**

Run: `wsl -d Ubuntu-24.04 -e bash -lc "cd /mnt/d/AIFramework/aureus/services/aureus-nautilus-node && python3 -m pytest tests/test_node_setup.py tests/test_runtime_lifecycle.py -v"`
Expected: PASS

**Step 6: Commit**

```bash
git add services/aureus-nautilus-node/main.py services/aureus-nautilus-node/nautilus_runner.py services/aureus-nautilus-node/config.py services/aureus-nautilus-node/Dockerfile services/aureus-nautilus-node/tests/test_node_setup.py services/aureus-nautilus-node/tests/test_runtime_lifecycle.py
git commit -m "feat(nautilus-node): harden live node bootstrap and lifecycle"
```

---

### Task 2: Production Config + Strict Risk Policy (Task 1 completion)

**Files:**
- Modify: `services/aureus-nautilus-node/config.py`
- Create: `services/aureus-nautilus-node/settings.py`
- Create: `services/aureus-nautilus-node/tests/test_config_validation.py`

**Step 1: Write failing config validation tests**

```python
def test_strict_mode_requires_sl_tp_enabled():
    ...

def test_invalid_symbol_whitelist_rejected():
    ...
```

**Step 2: Run tests to verify they fail**

Run: `wsl -d Ubuntu-24.04 -e bash -lc "cd /mnt/d/AIFramework/aureus/services/aureus-nautilus-node && python3 -m pytest tests/test_config_validation.py -v"`
Expected: FAIL due to missing typed settings + validation

**Step 3: Implement typed settings and validation**

- Add strongly-typed env-backed settings:
  - symbol whitelist
  - stream patterns
  - risk mode (`STRICT` only for production)
  - max position/order notional
  - poll/retry/backoff limits
- Reject startup if strict constraints are violated.

**Step 4: Run tests to verify pass**

Run: `wsl -d Ubuntu-24.04 -e bash -lc "cd /mnt/d/AIFramework/aureus/services/aureus-nautilus-node && python3 -m pytest tests/test_config_validation.py -v"`
Expected: PASS

**Step 5: Commit**

```bash
git add services/aureus-nautilus-node/config.py services/aureus-nautilus-node/settings.py services/aureus-nautilus-node/tests/test_config_validation.py
git commit -m "feat(nautilus-node): enforce typed production config and strict risk settings"
```

---

### Task 3: Harden `AureusMarketDataClient` for live reliability (Task 2 hardening)

**Files:**
- Modify: `services/aureus-nautilus-node/data_client.py`
- Modify: `services/aureus-nautilus-node/tests/test_data_client.py`
- Create: `services/aureus-nautilus-node/tests/test_data_client_resilience.py`

**Step 1: Write failing resilience tests**

```python
@pytest.mark.asyncio
async def test_market_data_client_deduplicates_by_stream_id():
    ...

@pytest.mark.asyncio
async def test_market_data_client_marks_gap_metric_when_sequence_skips():
    ...
```

**Step 2: Run tests to verify fail**

Run: `wsl -d Ubuntu-24.04 -e bash -lc "cd /mnt/d/AIFramework/aureus/services/aureus-nautilus-node && python3 -m pytest tests/test_data_client.py tests/test_data_client_resilience.py -v"`
Expected: FAIL with missing idempotency/gap handling

**Step 3: Implement production safeguards**

- Enforce payload schema validation before Bar creation.
- Track stream watermark and ignore duplicates.
- Detect stream/candle gaps and emit metric/log alerts.
- Add retry with jitter around `xread` failures.

**Step 4: Run tests to verify pass**

Run: `wsl -d Ubuntu-24.04 -e bash -lc "cd /mnt/d/AIFramework/aureus/services/aureus-nautilus-node && python3 -m pytest tests/test_data_client.py tests/test_data_client_resilience.py -v"`
Expected: PASS

**Step 5: Commit**

```bash
git add services/aureus-nautilus-node/data_client.py services/aureus-nautilus-node/tests/test_data_client.py services/aureus-nautilus-node/tests/test_data_client_resilience.py
git commit -m "feat(nautilus-node): harden market data ingestion with schema, dedupe, and gap detection"
```

---

### Task 4: Strict `AureusExecutionClient` + OCO/Idempotency (Task 3 hardening)

**Files:**
- Modify: `services/aureus-nautilus-node/execution_client.py`
- Modify: `services/aureus-nautilus-node/tests/test_execution_client.py`
- Create: `services/aureus-nautilus-node/tests/test_execution_risk_controls.py`

**Step 1: Write failing strict-risk tests**

```python
@pytest.mark.asyncio
async def test_order_without_sl_tp_is_rejected_in_strict_mode():
    ...

@pytest.mark.asyncio
async def test_duplicate_trace_id_is_ignored():
    ...

@pytest.mark.asyncio
async def test_valid_order_generates_entry_plus_sl_tp_contingents():
    ...
```

**Step 2: Run tests to verify fail**

Run: `wsl -d Ubuntu-24.04 -e bash -lc "cd /mnt/d/AIFramework/aureus/services/aureus-nautilus-node && python3 -m pytest tests/test_execution_client.py tests/test_execution_risk_controls.py -v"`
Expected: FAIL due to missing strict validation and contingent orders

**Step 3: Implement execution hardening**

- Add pre-trade checks (symbol allowlist, qty/notional limits, SL/TP mandatory, side-consistency).
- Enforce `trace_id` idempotency cache.
- Build bracket/OCO order set for valid `ORDER_OPEN`.
- Reject invalid intents with explicit reason codes and metrics.

**Step 4: Run tests to verify pass**

Run: `wsl -d Ubuntu-24.04 -e bash -lc "cd /mnt/d/AIFramework/aureus/services/aureus-nautilus-node && python3 -m pytest tests/test_execution_client.py tests/test_execution_risk_controls.py -v"`
Expected: PASS

**Step 5: Commit**

```bash
git add services/aureus-nautilus-node/execution_client.py services/aureus-nautilus-node/tests/test_execution_client.py services/aureus-nautilus-node/tests/test_execution_risk_controls.py
git commit -m "feat(nautilus-node): enforce strict execution risk gates and contingent order routing"
```

---

### Task 5: `SyncWorker` event contract + DLQ (Task 4 hardening)

**Files:**
- Modify: `services/aureus-nautilus-node/sync_worker.py`
- Modify: `services/aureus-nautilus-node/tests/test_sync_worker.py`
- Create: `services/aureus-nautilus-node/tests/test_sync_worker_contract.py`

**Step 1: Write failing contract tests**

```python
@pytest.mark.asyncio
async def test_sync_worker_emits_versioned_execution_envelope():
    ...

@pytest.mark.asyncio
async def test_sync_worker_routes_bad_event_to_dlq():
    ...
```

**Step 2: Run tests to verify fail**

Run: `wsl -d Ubuntu-24.04 -e bash -lc "cd /mnt/d/AIFramework/aureus/services/aureus-nautilus-node && python3 -m pytest tests/test_sync_worker.py tests/test_sync_worker_contract.py -v"`
Expected: FAIL due to missing versioned envelope/DLQ

**Step 3: Implement contract hardening**

- Emit versioned event envelope (`schema_ver`, `event_id`, `trace_id`, `ts_event`).
- Guarantee deterministic stream names for execution/positions.
- Route mapping/serialization failures to DLQ stream with diagnostics.

**Step 4: Run tests to verify pass**

Run: `wsl -d Ubuntu-24.04 -e bash -lc "cd /mnt/d/AIFramework/aureus/services/aureus-nautilus-node && python3 -m pytest tests/test_sync_worker.py tests/test_sync_worker_contract.py -v"`
Expected: PASS

**Step 5: Commit**

```bash
git add services/aureus-nautilus-node/sync_worker.py services/aureus-nautilus-node/tests/test_sync_worker.py services/aureus-nautilus-node/tests/test_sync_worker_contract.py
git commit -m "feat(nautilus-node): version sync contracts and add DLQ for failed event mappings"
```

---

### Task 6: Compose Production Profiles + Health Gates (Task 5 hardening)

**Files:**
- Modify: `docker-compose.dev.yml`
- Create: `docker-compose.prod.yml`
- Modify: `services/aureus-nautilus-node/Dockerfile`
- Create: `monitoring/prometheus/rules/nautilus-alerts.yml`

**Step 1: Write failing integration checklist test (script-based)**

- Create a smoke script asserting:
  - node health endpoint responds
  - restart count stays flat for 5 minutes
  - metrics endpoint exports strict-risk gauges

**Step 2: Run smoke check and capture baseline failure**

Run: `wsl -d Ubuntu-24.04 -e bash -lc "cd /mnt/d/AIFramework/aureus && docker compose -f docker-compose.dev.yml up -d --build aureus-nautilus-node-dev && docker inspect -f '{{.RestartCount}}' aureus-nautilus-node-dev"`
Expected: restart count unstable before hardening

**Step 3: Implement compose/profile hardening**

- Add production compose profile with resource limits and healthcheck.
- Set restart policy to controlled failure mode with backoff.
- Wire alert rules for restart spikes, missing SL/TP, stale PnL streams.

**Step 4: Run integration verification**

Run: `wsl -d Ubuntu-24.04 -e bash -lc "cd /mnt/d/AIFramework/aureus && docker compose -f docker-compose.prod.yml up -d --build"`
Run: `wsl -d Ubuntu-24.04 -e bash -lc "cd /mnt/d/AIFramework/aureus && docker compose -f docker-compose.prod.yml ps"`
Run: `wsl -d Ubuntu-24.04 -e bash -lc "curl -s http://localhost:19158/metrics | grep -Ei 'missing_sl|missing_tp|pnl'"`
Expected: all services healthy, strict-risk metrics visible

**Step 5: Commit**

```bash
git add docker-compose.dev.yml docker-compose.prod.yml services/aureus-nautilus-node/Dockerfile monitoring/prometheus/rules/nautilus-alerts.yml
git commit -m "feat(compose): add production profile health gates and strict-risk observability"
```

---

### Task 7: End-to-End Verification + Rollout Gates (shadow → canary → full)

**Files:**
- Create: `docs/runbooks/nautilus-production-rollout.md`
- Create: `docs/runbooks/nautilus-rollback.md`
- Create: `services/aureus-nautilus-node/tests/test_shadow_canary_flow.py`

**Step 1: Write failing rollout-gate test definitions**

```python
def test_rollout_gate_blocks_if_missing_sl_tp_metric_non_zero():
    ...

def test_rollout_gate_blocks_if_restart_rate_exceeds_threshold():
    ...
```

**Step 2: Run tests to verify fail**

Run: `wsl -d Ubuntu-24.04 -e bash -lc "cd /mnt/d/AIFramework/aureus/services/aureus-nautilus-node && python3 -m pytest tests/test_shadow_canary_flow.py -v"`
Expected: FAIL until rollout gate evaluator exists

**Step 3: Implement rollout gates + runbooks**

- Define SLO thresholds for promotion:
  - `missing_sl_total == 0`
  - `missing_tp_total == 0`
  - restart/hour == 0 (excluding deploy)
  - duplicate trace id == 0
- Document exact promotion and rollback commands.

**Step 4: Run verification suite**

Run: `wsl -d Ubuntu-24.04 -e bash -lc "cd /mnt/d/AIFramework/aureus/services/aureus-nautilus-node && python3 -m pytest -q"`
Run: `wsl -d Ubuntu-24.04 -e bash -lc "cd /mnt/d/AIFramework/aureus && docker compose -f docker-compose.prod.yml ps"`
Expected: PASS tests, healthy services, rollout gate criteria measurable

**Step 5: Commit**

```bash
git add docs/runbooks/nautilus-production-rollout.md docs/runbooks/nautilus-rollback.md services/aureus-nautilus-node/tests/test_shadow_canary_flow.py
git commit -m "docs(nautilus): add production rollout and rollback gates for strict-risk deployment"
```

---

## Verification Plan

### Automated Tests
1. `wsl -d Ubuntu-24.04 -e bash -lc "cd /mnt/d/AIFramework/aureus/services/aureus-nautilus-node && python3 -m pytest tests/test_node_setup.py tests/test_runtime_lifecycle.py -v"`
2. `wsl -d Ubuntu-24.04 -e bash -lc "cd /mnt/d/AIFramework/aureus/services/aureus-nautilus-node && python3 -m pytest tests/test_config_validation.py -v"`
3. `wsl -d Ubuntu-24.04 -e bash -lc "cd /mnt/d/AIFramework/aureus/services/aureus-nautilus-node && python3 -m pytest tests/test_data_client.py tests/test_data_client_resilience.py -v"`
4. `wsl -d Ubuntu-24.04 -e bash -lc "cd /mnt/d/AIFramework/aureus/services/aureus-nautilus-node && python3 -m pytest tests/test_execution_client.py tests/test_execution_risk_controls.py -v"`
5. `wsl -d Ubuntu-24.04 -e bash -lc "cd /mnt/d/AIFramework/aureus/services/aureus-nautilus-node && python3 -m pytest tests/test_sync_worker.py tests/test_sync_worker_contract.py -v"`
6. `wsl -d Ubuntu-24.04 -e bash -lc "cd /mnt/d/AIFramework/aureus/services/aureus-nautilus-node && python3 -m pytest tests/test_shadow_canary_flow.py -v"`
7. `wsl -d Ubuntu-24.04 -e bash -lc "cd /mnt/d/AIFramework/aureus/services/aureus-nautilus-node && python3 -m pytest -q"`

### Runtime / Integration Verification
1. `wsl -d Ubuntu-24.04 -e bash -lc "cd /mnt/d/AIFramework/aureus && docker compose -f docker-compose.prod.yml up -d --build"`
2. `wsl -d Ubuntu-24.04 -e bash -lc "cd /mnt/d/AIFramework/aureus && docker compose -f docker-compose.prod.yml ps"`
3. `wsl -d Ubuntu-24.04 -e bash -lc "cd /mnt/d/AIFramework/aureus && docker inspect -f '{{.Name}}|{{.State.Status}}|restarts={{.RestartCount}}' aureus-nautilus-node-dev"`
4. `wsl -d Ubuntu-24.04 -e bash -lc "curl -s http://localhost:19158/metrics | grep -Ei 'missing_sl|missing_tp|unrealized_pnl|realized_pnl'"`

### Manual Verification
1. Publish a valid `ORDER_OPEN` intent (with SL/TP) and confirm order accepted + sync stream emission.
2. Publish an invalid `ORDER_OPEN` intent (missing SL or TP) and confirm order is rejected with explicit reason.
3. Run shadow mode 30 minutes with live feeds and confirm no order submission side effects.
4. Run canary mode on one symbol with low size and confirm SLO gates remain green before enabling full symbols.

---

Plan complete and saved to `docs/plans/2026-03-19-nautilus-deep-integration-production-plan.md`.
Next step: run `.agent/workflows/execute-plan.md` to execute this plan task-by-task in single-flow mode.
