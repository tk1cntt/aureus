# Live Trading V1 Spec Implementation Plan

> **For Antigravity:** REQUIRED WORKFLOW: Use `.agent/workflows/execute-plan.md` to execute this plan in single-flow mode.

**Goal:** Implement deterministic, backfill-gated, trace-complete live decision flow aligned to approved V1 specs.

**Architecture:** Harden gating in `aureus-signal` before strategy execution, then refactor strategy contract flow into intent → validation → order-plan phases. Extend decision trace persistence and propagate lineage through execution/bridge services so rollout promotion can be evaluated from explicit evidence.

**Tech Stack:** Python, asyncio, Redis streams, pytest.

**Test Coverage Rule:** Every implemented function/feature in this plan must be covered by testcases with minimum **>= 80% coverage**. Any phase is considered incomplete if coverage is below this threshold.

## Phase Grouping Views

### A) Group by Technical Domain
- **Signal Engine:** Phase 1, 2, 3, 4, 5
- **Strategy Contract:** Phase 6, 7, 8
- **Decision Trace:** Phase 9, 10
- **Execution Controls:** Phase 11, 12
- **Bridge & Lineage:** Phase 13
- **Global Verification:** Phase 14

### B) Group by Risk Priority
- **Wave 1 — Core Safety Gates (highest risk):** Phase 1, 2, 3
- **Wave 2 — Contract Correctness:** Phase 6, 7, 8
- **Wave 3 — Trace Integrity & Auditability:** Phase 4, 5, 9, 10
- **Wave 4 — Runtime Rollout Safety:** Phase 11, 12
- **Wave 5 — Integration Lineage & Final Validation:** Phase 13, 14

---

### Phase 1: Closed-candle gate

**Files:**
- Modify: `services/aureus-signal/engine/live_engine.py`
- Test: `services/aureus-signal/tests/test_live_engine_gates.py`

1. Write failing test for "reject when bar not closed".
2. Run: `pytest services/aureus-signal/tests/test_live_engine_gates.py -q` (Expected FAIL).
3. Implement minimal closed-candle gate.
4. Re-run same test (Expected PASS).
5. Commit.

### Phase 2: Backfill readiness gate

**Files:**
- Modify: `services/aureus-signal/engine/live_engine.py`
- Modify: `services/aureus-signal/engine/manager.py`
- Test: `services/aureus-signal/tests/test_live_engine_gates.py`

1. Write failing test for "reject when backfill not READY".
2. Implement `WindowManager` backfill readiness metadata/API.
3. Wire gate usage in `live_engine.py`.
4. Re-run test file (Expected PASS).
5. Commit.

### Phase 3: Window integrity gate

**Files:**
- Modify: `services/aureus-signal/engine/manager.py`
- Modify: `services/aureus-signal/engine/live_engine.py`
- Test: `services/aureus-signal/tests/test_live_engine_gates.py`

1. Write failing test for invalid contiguous window.
2. Implement integrity metadata (`window_start/end/hash`, integrity flag).
3. Enforce fail-closed in `live_engine.py`.
4. Re-run test file (Expected PASS).
5. Commit.

### Phase 4: Signal normalization

**Files:**
- Modify: `services/aureus-signal/engine/signal_factory.py`
- Test: `services/aureus-signal/tests/test_signal_contract_normalization.py`

1. Write failing tests for required normalized keys (`zigzag_state`, `ob_state`, `choch_state`, `fvg_state`, `trend_filter_state`).
2. Implement normalized snapshot builder.
3. Re-run test file (Expected PASS).
4. Commit.

### Phase 5: Decision version metadata

**Files:**
- Modify: `services/aureus-signal/engine/live_engine.py`
- Test: `services/aureus-signal/tests/test_signal_contract_normalization.py`

1. Add failing assertions for `spec_version`, `strategy_version`, `engine_version`.
2. Implement metadata injection in decision payload.
3. Re-run test file (Expected PASS).
4. Commit.

### Phase 6: Strategy base contract split

**Files:**
- Modify: `services/aureus-signal/engine/strategies/base.py`
- Test: `services/aureus-signal/tests/test_strategy_contract_v1.py`

1. Write failing tests for required metadata and phased interface.
2. Add contract methods (`on_bar_close`, `validate_entry`, `build_order_plan`) + metadata requirements.
3. Add compatibility adapter for legacy `evaluate(...)`.
4. Re-run test file (Expected PASS).
5. Commit.

### Phase 7: Template strategy phased output

**Files:**
- Modify: `services/aureus-signal/engine/strategies/template.py`
- Test: `services/aureus-signal/tests/test_strategy_contract_v1.py`

1. Write failing test for intent/validation/order-plan structured outputs.
2. Implement deterministic reason codes + structured artifacts.
3. Re-run test file (Expected PASS).
4. Commit.

### Phase 8: Registry compatibility + orchestration

**Files:**
- Modify: `services/aureus-signal/engine/strategies/registry.py`
- Test: `services/aureus-signal/tests/test_strategy_contract_v1.py`

1. Write failing test for incompatible strategy rejection.
2. Implement metadata compatibility checks and phased orchestration.
3. Capture phase-level rejection reasons.
4. Re-run test file (Expected PASS).
5. Commit.

### Phase 9: Trace schema builders

**Files:**
- Modify: `services/aureus-signal/engine/snapshot_utils.py`
- Test: `services/aureus-signal/tests/test_decision_trace_schema.py`

1. Write failing tests for required trace blocks (ACCEPTED + REJECTED).
2. Implement required-key validator and schema block builder.
3. Re-run test file (Expected PASS).
4. Commit.

### Phase 10: Order/state trace persistence

**Files:**
- Modify: `services/aureus-signal/engine/orders.py`
- Modify: `services/aureus-signal/engine/state.py`
- Test: `services/aureus-signal/tests/test_decision_trace_schema.py`

1. Add failing tests for order-plan completeness checks and rejection persistence.
2. Implement completeness validation and persistent rejection reasons in `orders.py`.
3. Implement lifecycle/validator ledger in `state.py`.
4. Re-run test file (Expected PASS).
5. Commit.

### Phase 11: Execution policy validation

**Files:**
- Modify: `services/aureus-nautilus-node/execution_client.py`
- Test: `services/aureus-nautilus-node/tests/test_execution_client_policy.py`

1. Write failing tests for full order-plan policy rejections.
2. Implement validation + metrics expansion in `execution_client.py`.
3. Re-run test file (Expected PASS).
4. Commit.

### Phase 12: Rollout gate thresholds

**Files:**
- Modify: `services/aureus-nautilus-node/rollout_gates.py`
- Test: `services/aureus-nautilus-node/tests/test_rollout_gates.py`

1. Write failing tests for `SHADOW -> PAPER` and `PAPER -> LIVE` thresholds.
2. Implement stage-aware gate evaluation + evidence fields.
3. Re-run test file (Expected PASS).
4. Commit.

### Phase 13: Bridge lineage propagation

**Files:**
- Modify: `services/aureus-nautilus-bridge/main.py`
- Test: `services/aureus-nautilus-bridge/tests/test_bridge_idempotency.py`
- Test: `services/aureus-nautilus-bridge/tests/test_mapper.py`

1. Write failing tests for `trace_id`/`correlation_id` propagation.
2. Implement lineage propagation in order/lifecycle publish paths.
3. Re-run bridge test suite (Expected PASS).
4. Commit.

### Phase 14: Final regression + coverage gate

**Files:**
- Modify (if needed): `services/aureus-signal/tests/*`
- Modify (if needed): `services/aureus-nautilus-node/tests/*`
- Modify (if needed): `services/aureus-nautilus-bridge/tests/*`

1. Run: `pytest services/aureus-signal/tests -q`
2. Run: `pytest services/aureus-nautilus-node/tests -q`
3. Run: `pytest services/aureus-nautilus-bridge/tests -q`
4. Run coverage gates:
   - `pytest services/aureus-signal/tests --cov=services/aureus-signal/engine --cov-report=term-missing --cov-fail-under=80 -q`
   - `pytest services/aureus-nautilus-node/tests --cov=services/aureus-nautilus-node --cov-report=term-missing --cov-fail-under=80 -q`
   - `pytest services/aureus-nautilus-bridge/tests --cov=services/aureus-nautilus-bridge --cov-report=term-missing --cov-fail-under=80 -q`
5. Replay same dataset twice and compare status/reason/hash outputs.
6. Inject backfill/window-gap scenario and verify fail-closed behavior.
7. Commit verification-only adjustments (if required).

Plan complete and saved to `docs/plans/2026-03-20-live-trading-v1.md`.
Next step: run `.agent/workflows/execute-plan.md` to execute this plan task-by-task in single-flow mode.
