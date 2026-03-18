# Nautilus-Native Execution & Monitoring Implementation Plan

> **For Antigravity:** REQUIRED WORKFLOW: Use `.agent/workflows/execute-plan.md` to execute this plan in single-flow mode.

**Goal:** Replace the current simulated execution feedback path with Nautilus-native lifecycle + position data so Aureus can monitor order status, entry, SL/TP, and PnL with a single source of truth.

**Architecture:** Keep Aureus as the signal producer and make Nautilus the execution authority. Extend the bridge contract to propagate execution + position fields, persist those fields in DB writer tables, and expose them through Prometheus/Grafana for operational and business monitoring.

**Tech Stack:** Python, Redis Streams, PostgreSQL/TimescaleDB, Docker Compose, Prometheus, Grafana.

## Status Update (2026-03-19 00:28 +07)

- ✅ **Task 1 complete**: execution contract v2 fields + bridge mapper/idempotency tests updated and passing.
- ✅ **Task 2 complete**: bridge supports `NAUTILUS_ADAPTER_MODE=simulated|stream`, lifecycle stream ingestion, and transition-safe idempotency.
- ✅ **Task 3 complete**: signal `ORDER_OPEN` payload includes `trace_id`, `entry_price`, `sl`, `tp`, `execution_mode`.
- ✅ **Task 4 complete**: compose/runbook stream-mode toggles wired and focused bridge verification passed.
- ✅ **Task 5 complete**: `aureus_position_snapshots` and `aureus_account_snapshots` schema tables added, stream insertion + idempotency implemented and verified.
- ✅ **Task 6-7 complete**: Prometheus exporter expanded to capture missing SL/TP and PnL metrics; alerts added; Grafana `aureus_nautilus_flow.json` updated with new panels.
- ✅ **Task 8-9 complete**: v2 E2E regression script `test_nautilus_redis_flow_v2.py` validates execution mode, positional snapshots, and end-to-end integration successfully.

**Plan fully executed and verified.**

---

## Scope and non-goals

- In scope:
  - Real Nautilus lifecycle ingestion in bridge output contract
  - End-to-end fields: `status`, `entry_price`, `sl`, `tp`, `realized_pnl`, `unrealized_pnl`
  - DB schema + writer support for execution and position/account snapshots
  - Monitoring exporter + Grafana dashboard updates
  - Staged rollout (`shadow` then controlled cutover)
- Out of scope (this plan):
  - Full multi-broker abstraction
  - Historical migration of old execution rows

---

### Task 1: Lock execution event contract (v2)

**Files:**
- Modify: `services/aureus-nautilus-bridge/mapper.py`
- Modify: `services/aureus-nautilus-bridge/reconciliation.py`
- Modify: `services/aureus-nautilus-bridge/tests/test_mapper.py`
- Modify: `services/aureus-nautilus-bridge/tests/test_bridge_idempotency.py`

**Step 1: Write failing contract tests for new fields**

Add assertions that mapped events include:
- `entry_price`
- `sl`
- `tp`
- `realized_pnl`
- `unrealized_pnl`
- `position_id`
- `event_version` = `2`

**Step 2: Run tests to confirm failures**

Run:
`wsl -d Ubuntu-24.04 -e bash -lc "cd /mnt/d/AIFramework/aureus && python services/aureus-nautilus-bridge/tests/test_mapper.py"`

Expected: FAIL on missing keys/defaults.

**Step 3: Implement minimal mapping updates**

Update `map_order_intent` and `build_execution_event` to:
- preserve `entry_price/sl/tp` from order payload
- accept PnL/position values from adapter report
- emit `event_version: 2`
- keep backwards-safe defaults for missing adapter fields

**Step 4: Add reconciliation transition tests with position context**

Ensure terminal transition rules still hold when same `trace_id` carries multiple lifecycle updates.

**Step 5: Re-run bridge tests**

Run:
- `wsl -d Ubuntu-24.04 -e bash -lc "cd /mnt/d/AIFramework/aureus && python services/aureus-nautilus-bridge/tests/test_mapper.py"`
- `wsl -d Ubuntu-24.04 -e bash -lc "cd /mnt/d/AIFramework/aureus && python services/aureus-nautilus-bridge/tests/test_bridge_idempotency.py"`

Expected: PASS.

**Step 6: Commit**

`git add services/aureus-nautilus-bridge/mapper.py services/aureus-nautilus-bridge/reconciliation.py services/aureus-nautilus-bridge/tests/test_mapper.py services/aureus-nautilus-bridge/tests/test_bridge_idempotency.py && git commit -m "feat(bridge): extend execution contract v2 with sl tp pnl fields"`

---

### Task 2: Replace simulated adapter path with Nautilus lifecycle ingestion

**Files:**
- Modify: `services/aureus-nautilus-bridge/main.py`
- Modify: `services/aureus-nautilus-bridge/reconciliation.py`
- Modify: `docker-compose.dev.yml`
- Modify: `RUN_SERVICES.md`

**Step 1: Add failing integration-oriented bridge test**

Create/extend test that feeds synthetic Nautilus lifecycle sequence:
`ORDER_ACCEPTED -> PARTIAL_FILL -> FILLED` and validates emitted stream sequence.

**Step 2: Run failing test**

Run:
`wsl -d Ubuntu-24.04 -e bash -lc "cd /mnt/d/AIFramework/aureus && python services/aureus-nautilus-bridge/tests/test_bridge_idempotency.py"`

Expected: FAIL due to current one-shot simulated response.

**Step 3: Implement adapter interface split**

In `main.py`:
- keep current simulated adapter behind feature flag (`NAUTILUS_ADAPTER_MODE=simulated`)
- add lifecycle ingestion mode (`NAUTILUS_ADAPTER_MODE=stream`) for Nautilus events
- ensure idempotency remains based on `trace_id` + status transition rules

**Step 4: Wire compose/runtime env**

Add env vars and runbook notes for adapter mode switching.

**Step 5: Re-run bridge tests**

Expected: PASS with both simulated and stream modes covered.

**Step 6: Commit**

`git add services/aureus-nautilus-bridge/main.py services/aureus-nautilus-bridge/reconciliation.py docker-compose.dev.yml RUN_SERVICES.md && git commit -m "feat(bridge): add nautilus lifecycle ingestion mode"`

---

### Task 3: Extend order intent payload to guarantee SL/TP propagation

**Files:**
- Modify: `services/aureus-signal/engine/orders.py`
- Modify: `services/aureus-signal/engine/live_engine.py`
- Modify: `services/aureus-signal/unittest/test_orders_events.py`

**Step 1: Write failing test for outbound ORDER_OPEN payload**

Assert outbound order payload includes stable keys:
`trace_id`, `entry_price`, `sl`, `tp`, `execution_mode`.

**Step 2: Run test and verify failure**

Run:
`wsl -d Ubuntu-24.04 -e bash -lc "cd /mnt/d/AIFramework/aureus/services/aureus-signal && python unittest/test_orders_events.py"`

Expected: FAIL on missing `sl/tp` fields.

**Step 3: Implement minimal payload changes**

Update `orders.py` to include `sl`/`tp` in emitted intent payloads (with explicit nullable defaults).

**Step 4: Preserve mode behavior**

Ensure `live_engine.py` still bypasses local simulated close logic when `execution_mode=nautilus`.

**Step 5: Re-run signal tests**

Run:
- `wsl -d Ubuntu-24.04 -e bash -lc "cd /mnt/d/AIFramework/aureus/services/aureus-signal && python unittest/test_orders_events.py"`
- `wsl -d Ubuntu-24.04 -e bash -lc "cd /mnt/d/AIFramework/aureus/services/aureus-signal && python unittest/test_trade_manager_events.py"`

Expected: PASS.

**Step 6: Commit**

`git add services/aureus-signal/engine/orders.py services/aureus-signal/engine/live_engine.py services/aureus-signal/unittest/test_orders_events.py && git commit -m "feat(signal): include sl tp in order intents for nautilus mode"`

---

### Task 4: Persist execution contract v2 in Timescale

**Files:**
- Modify: `services/aureus-db-writer/schema.sql`
- Modify: `services/aureus-db-writer/main.py`

**Step 1: Add failing writer parsing test or local assertion harness**

Validate DB writer can parse/store execution payload with v2 fields.

**Step 2: Update schema**

Add columns to `aureus_execution_events`:
- `entry_price DOUBLE PRECISION`
- `sl DOUBLE PRECISION`
- `tp DOUBLE PRECISION`
- `realized_pnl DOUBLE PRECISION`
- `unrealized_pnl DOUBLE PRECISION`
- `position_id TEXT`
- `event_version INTEGER NOT NULL DEFAULT 1`

Add `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` for migration safety.

**Step 3: Update insert path in DB writer**

Map and batch-insert the new fields from execution payload.

**Step 4: Re-run DB writer smoke**

Run:
`wsl -d Ubuntu-24.04 -e bash -lc "cd /mnt/d/AIFramework/aureus && python services/aureus-db-writer/main.py"`

Expected: Starts without SQL/parse errors.

**Step 5: Verify in DB**

Run inside DB container:
`SELECT trace_id,status,entry_price,sl,tp,realized_pnl,unrealized_pnl,event_version FROM aureus_execution_events ORDER BY event_time DESC LIMIT 20;`

Expected: non-null business fields for new v2 events.

**Step 6: Commit**

`git add services/aureus-db-writer/schema.sql services/aureus-db-writer/main.py && git commit -m "feat(db): persist nautilus execution v2 fields"`

---

### Task 5: Add position/account snapshot persistence (PnL source of truth)

**Files:**
- Modify: `services/aureus-db-writer/schema.sql`
- Modify: `services/aureus-db-writer/main.py`
- Create: `services/aureus-db-writer/tests/test_position_account_ingest.py`

**Step 1: Write failing tests for new streams**

Cover ingestion for:
- `aureus:stream:*:positions`
- `aureus:stream:*:account`

**Step 2: Add schema tables**

Create tables:
- `aureus_position_snapshots`
- `aureus_account_snapshots`

Minimum columns:
- position: `event_time,symbol,position_id,side,qty,avg_entry_price,mark_price,unrealized_pnl,realized_pnl,payload`
- account: `event_time,account_id,equity,balance,margin_used,margin_free,unrealized_pnl,realized_pnl,payload`

**Step 3: Implement stream discovery + buffering**

Extend writer discovery and flush paths for new stream suffixes.

**Step 4: Run tests**

Run:
`wsl -d Ubuntu-24.04 -e bash -lc "cd /mnt/d/AIFramework/aureus && python -m pytest services/aureus-db-writer/tests -q"`

Expected: PASS.

**Step 5: Commit**

`git add services/aureus-db-writer/schema.sql services/aureus-db-writer/main.py services/aureus-db-writer/tests/test_position_account_ingest.py && git commit -m "feat(db): ingest position and account snapshot streams"`

---

### Task 6: Upgrade metrics exporter for business observability

**Files:**
- Modify: `services/aureus-bridge-metrics-exporter/main.py`
- Modify: `services/aureus-bridge-metrics-exporter/requirements.txt`
- Modify: `monitoring/prometheus/alerts.yml`

**Step 1: Write failing metric assertions**

Add tests/smoke assertions for new metrics names:
- `aureus_bridge_sl_tp_coverage_ratio`
- `aureus_bridge_realized_pnl_total`
- `aureus_bridge_unrealized_pnl`
- `aureus_bridge_open_positions`

**Step 2: Implement metric collection**

Compute from execution + position/account streams:
- SL/TP coverage: ratio of active/open orders with both `sl` and `tp`
- Realized PnL total per symbol
- Unrealized PnL gauge per symbol
- Open positions count

**Step 3: Add alerts**

Prometheus rules:
- low SL/TP coverage below threshold
- sudden realized PnL drawdown
- stale position updates

**Step 4: Rebuild and verify metrics endpoint**

Run:
`wsl -e sh -lc "cd /mnt/d/AIFramework/aureus && docker compose -f docker-compose.dev.yml up --build -d aureus-bridge-metrics-dev prometheus-dev"`

Verify:
`wsl -e sh -lc "docker exec aureus-bridge-metrics-dev wget -qO- http://localhost:9108/metrics | head -n 120"`

Expected: new metric names present.

**Step 5: Commit**

`git add services/aureus-bridge-metrics-exporter/main.py services/aureus-bridge-metrics-exporter/requirements.txt monitoring/prometheus/alerts.yml && git commit -m "feat(monitoring): add sl tp pnl business metrics and alerts"`

---

### Task 7: Extend Grafana dashboard for status + SL/TP + PnL views

**Files:**
- Modify: `monitoring/grafana/dashboards/aureus_nautilus_flow.json`
- Modify: `monitoring/grafana/provisioning/dashboards/dashboards.yml`

**Step 1: Add dashboard panels**

Add/adjust panels:
- Order status distribution (`accepted/partial/filled/canceled/rejected`)
- SL/TP coverage ratio
- Realized PnL cumulative by symbol
- Unrealized PnL current by symbol
- Open positions count

**Step 2: Validate dashboard JSON**

Run local JSON validation command (or load into Grafana and inspect parsing).

**Step 3: Manual visual verification**

Open `http://localhost:13555` and confirm panels populate after flow script runs.

**Step 4: Commit**

`git add monitoring/grafana/dashboards/aureus_nautilus_flow.json monitoring/grafana/provisioning/dashboards/dashboards.yml && git commit -m "feat(grafana): add nautilus business monitoring panels"`

---

### Task 8: Build end-to-end regression script for v2 contract

**Files:**
- Modify: `scripts/test_nautilus_redis_flow.py`
- Create: `scripts/test_nautilus_redis_flow_v2.py`

**Step 1: Add failing checks for new fields**

Assert returned execution event contains `entry_price/sl/tp/event_version` and at least one PnL-related field.

**Step 2: Implement v2 script**

Create script variant that:
- sends order with `sl/tp`
- polls execution stream
- fails if v2 fields absent

**Step 3: Run script against compose stack**

Run:
`wsl -e sh -lc "cd /mnt/d/AIFramework/aureus && python scripts/test_nautilus_redis_flow_v2.py --redis-host 127.0.0.1 --redis-port 6380 --symbol XAUUSD --timeout 30"`

Expected: PASS with v2 fields printed.

**Step 4: Commit**

`git add scripts/test_nautilus_redis_flow.py scripts/test_nautilus_redis_flow_v2.py && git commit -m "test(flow): add v2 execution contract e2e check"`

---

### Task 9: Rollout controls and cutover playbook

**Files:**
- Modify: `docker-compose.dev.yml`
- Modify: `RUN_SERVICES.md`
- Modify: `services/aureus-signal/engine/live_engine.py`

**Step 1: Add symbol-level guardrails**

Add env-driven allowlist for `execution_mode=nautilus` symbols.

**Step 2: Add shadow mode switch**

Define three modes:
- `simulated`
- `shadow` (compare only)
- `nautilus` (authoritative execution)

**Step 3: Add runbook checklist**

Document:
- pre-cutover checks
- cutover procedure per symbol
- rollback procedure in < 5 minutes

**Step 4: Smoke test mode toggles**

Validate service starts and logs selected mode correctly.

**Step 5: Commit**

`git add docker-compose.dev.yml RUN_SERVICES.md services/aureus-signal/engine/live_engine.py && git commit -m "chore(rollout): add shadow and cutover controls for nautilus execution"`

---

## Final verification gate

Run full verification set:

1. Bridge tests
- `wsl -d Ubuntu-24.04 -e bash -lc "cd /mnt/d/AIFramework/aureus && python services/aureus-nautilus-bridge/tests/test_mapper.py"`
- `wsl -d Ubuntu-24.04 -e bash -lc "cd /mnt/d/AIFramework/aureus && python services/aureus-nautilus-bridge/tests/test_bridge_idempotency.py"`

2. Signal tests
- `wsl -d Ubuntu-24.04 -e bash -lc "cd /mnt/d/AIFramework/aureus/services/aureus-signal && python unittest/test_orders_events.py"`
- `wsl -d Ubuntu-24.04 -e bash -lc "cd /mnt/d/AIFramework/aureus/services/aureus-signal && python unittest/test_trade_manager_events.py"`

3. DB writer tests/smoke
- `wsl -d Ubuntu-24.04 -e bash -lc "cd /mnt/d/AIFramework/aureus && python -m pytest services/aureus-db-writer/tests -q"`

4. Monitoring runtime checks
- `wsl -e sh -lc "cd /mnt/d/AIFramework/aureus && docker compose -f docker-compose.dev.yml up --build -d"`
- `wsl -e sh -lc "docker exec prometheus-dev wget -qO- http://localhost:9090/api/v1/targets"`
- `wsl -e sh -lc "docker exec aureus-bridge-metrics-dev wget -qO- http://localhost:9108/metrics | head -n 120"`

5. E2E flow check
- `wsl -e sh -lc "cd /mnt/d/AIFramework/aureus && python scripts/test_nautilus_redis_flow_v2.py --redis-host 127.0.0.1 --redis-port 6380 --symbol XAUUSD --timeout 30"`

Success criteria:
- v2 execution fields present end-to-end
- position/account snapshot tables populated
- Grafana PnL and SL/TP panels non-empty
- no duplicate lifecycle transitions per `trace_id`

---

## Suggested execution order

1. Task 1 → Task 3 (contract + signal payload)
2. Task 2 (real lifecycle path)
3. Task 4 → Task 5 (DB persistence)
4. Task 6 → Task 7 (monitoring)
5. Task 8 (e2e regression)
6. Task 9 (rollout controls)

---

**Plan complete and saved to `docs/plans/2026-03-18-nautilus-native-execution-monitoring.md`.**
**Next step: run `.agent/workflows/execute-plan.md` to execute this plan task-by-task in single-flow mode.**
