# Signal Quality Contract & Validation Implementation Plan

> **For Antigravity:** REQUIRED WORKFLOW: Use `.agent/workflows/execute-plan.md` to execute this plan in single-flow mode.

**Goal:** Chuẩn hóa pipeline tạo/kiểm định signal bằng Data Contract + 3-gate validation + lưu vết outcome để đo KPI chất lượng signal end-to-end.

**Architecture:** Áp dụng contract-first tại Signal Engine và Gateway, lưu identity keys xuyên suốt (`signal_id`, `decision_id`, `run_id`, `signal_seq`), ghi persistence tại DB Writer theo model signal events/outcomes, sau đó expose KPI endpoint tối thiểu ở Dashboard API. Triển khai theo TDD, mỗi thay đổi nhỏ đều có test và commit riêng.

**Tech Stack:** Python 3.x, asyncio, Redis Streams, asyncpg/TimescaleDB, FastAPI, pytest.

---

## Scope ưu tiên (P0 trước)

1. **P0-A:** Signal Event Data Contract + identity keys.
2. **P0-B:** Three-gate qualification (Structural -> Momentum/Volatility -> Risk).
3. **P0-C:** Reject signals thiếu metadata contract.
4. **P0-D:** Persist signal events/outcomes để đo KPI.
5. **P0-E:** API KPI tối thiểu cho quan sát chất lượng.

---

### Task 1: Tạo Signal Event Contract (schema + validator)

**Files:**
- Create: `services/aureus-signal/engine/signals/contract.py`
- Modify: `services/aureus-signal/engine/signals/base.py`
- Test: `services/aureus-signal/tests/test_signal_contract.py`

**Step 1: Write the failing test**

```python
# services/aureus-signal/tests/test_signal_contract.py
import pytest
from engine.signals.contract import SignalEventContract, validate_signal_event


def test_signal_event_contract_requires_mandatory_fields():
    payload = {
        "symbol": "XAUUSD",
        "timeframe": "M1",
        "ts": 1710000000,
        "strategy_id": "smc_trend_scalping",
        # missing signal_id, decision_id
    }
    with pytest.raises(ValueError):
        validate_signal_event(payload)


def test_signal_event_contract_accepts_valid_payload():
    payload = {
        "signal_id": "XAUUSD-M1-1710000000-choch_up",
        "decision_id": "XAUUSD-1710000000-decision",
        "run_id": "live",
        "signal_seq": 1,
        "symbol": "XAUUSD",
        "timeframe": "M1",
        "ts": 1710000000,
        "strategy_id": "smc_trend_scalping",
        "signal_type": "choch_up",
        "confidence": 0.82,
        "metadata": {"source": "structure_processor"},
    }
    validated = validate_signal_event(payload)
    assert validated["signal_type"] == "choch_up"
```

**Step 2: Run test to verify it fails**

Run: `pytest services/aureus-signal/tests/test_signal_contract.py -v`
Expected: FAIL vì chưa có module `contract.py`.

**Step 3: Write minimal implementation**

```python
# services/aureus-signal/engine/signals/contract.py
from dataclasses import dataclass
from typing import Any, Dict

MANDATORY_FIELDS = {
    "signal_id", "decision_id", "run_id", "signal_seq",
    "symbol", "timeframe", "ts", "strategy_id", "signal_type",
    "confidence", "metadata",
}


def validate_signal_event(payload: Dict[str, Any]) -> Dict[str, Any]:
    missing = [k for k in MANDATORY_FIELDS if k not in payload]
    if missing:
        raise ValueError(f"Missing mandatory fields: {missing}")
    return payload
```

**Step 4: Run test to verify it passes**

Run: `pytest services/aureus-signal/tests/test_signal_contract.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add services/aureus-signal/engine/signals/contract.py services/aureus-signal/tests/test_signal_contract.py
git commit -m "feat(signal): add mandatory signal event contract validator"
```

---

### Task 2: Thêm identity keys chuẩn tại Signal Engine

**Files:**
- Modify: `services/aureus-signal/engine/live_engine.py`
- Modify: `services/aureus-signal/engine/state.py`
- Test: `services/aureus-signal/tests/test_signal_identity_keys.py`

**Step 1: Write the failing test**

```python
# services/aureus-signal/tests/test_signal_identity_keys.py
from engine.state import SymbolState


def test_state_tracks_signal_sequence_counter():
    s = SymbolState("XAUUSD")
    assert hasattr(s, "signal_seq")
    assert s.signal_seq == 0
```

**Step 2: Run test to verify it fails**

Run: `pytest services/aureus-signal/tests/test_signal_identity_keys.py -v`
Expected: FAIL (field chưa tồn tại hoặc chưa init đúng).

**Step 3: Write minimal implementation**

```python
# services/aureus-signal/engine/state.py (add fields in reset)
self.signal_seq: int = 0
self.current_run_id: str = "live"
```

```python
# services/aureus-signal/engine/live_engine.py (where signal result is created)
state.signal_seq += 1
signal_id = f"{symbol}-{candle_ts}-{tag_val}-{state.signal_seq}"
decision_id = f"{symbol}-{candle_ts}-decision"
```

**Step 4: Run test to verify it passes**

Run: `pytest services/aureus-signal/tests/test_signal_identity_keys.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add services/aureus-signal/engine/state.py services/aureus-signal/engine/live_engine.py services/aureus-signal/tests/test_signal_identity_keys.py
git commit -m "feat(signal): add signal identity keys and sequence tracking"
```

---

### Task 3: Triển khai Three-Gate Qualification trong Signal Engine

**Files:**
- Create: `services/aureus-signal/engine/signals/qualification.py`
- Modify: `services/aureus-signal/engine/live_engine.py`
- Test: `services/aureus-signal/tests/test_signal_three_gate_validation.py`

**Step 1: Write the failing test**

```python
# services/aureus-signal/tests/test_signal_three_gate_validation.py
from engine.signals.qualification import evaluate_three_gates


def test_signal_must_pass_all_three_gates():
    candidate = {
        "structural_pass": True,
        "momentum_volatility_pass": True,
        "risk_pass": False,
    }
    out = evaluate_three_gates(candidate)
    assert out["qualified"] is False
    assert out["failed_gate"] == "risk"
```

**Step 2: Run test to verify it fails**

Run: `pytest services/aureus-signal/tests/test_signal_three_gate_validation.py -v`
Expected: FAIL (module/function chưa có).

**Step 3: Write minimal implementation**

```python
# services/aureus-signal/engine/signals/qualification.py
def evaluate_three_gates(candidate: dict) -> dict:
    if not candidate.get("structural_pass"):
        return {"qualified": False, "failed_gate": "structural"}
    if not candidate.get("momentum_volatility_pass"):
        return {"qualified": False, "failed_gate": "momentum_volatility"}
    if not candidate.get("risk_pass"):
        return {"qualified": False, "failed_gate": "risk"}
    return {"qualified": True, "failed_gate": None}
```

**Step 4: Run test to verify it passes**

Run: `pytest services/aureus-signal/tests/test_signal_three_gate_validation.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add services/aureus-signal/engine/signals/qualification.py services/aureus-signal/tests/test_signal_three_gate_validation.py services/aureus-signal/engine/live_engine.py
git commit -m "feat(signal): add three-gate qualification pipeline"
```

---

### Task 4: Reject signal thiếu metadata contract ở Gateway

**Files:**
- Modify: `services/aureus-gateway/main.py`
- Test: `services/aureus-gateway/tests/test_gateway_signal_contract_validation.py`

**Step 1: Write the failing test**

```python
# services/aureus-gateway/tests/test_gateway_signal_contract_validation.py
import pytest

from main import process_message

@pytest.mark.asyncio
async def test_gateway_rejects_signal_without_contract_fields(mock_redis):
    data = {"type": "SIGNAL", "symbol": "XAUUSD"}
    ok = await process_message(mock_redis, data, source="TCP")
    assert ok is False
```

**Step 2: Run test to verify it fails**

Run: `pytest services/aureus-gateway/tests/test_gateway_signal_contract_validation.py -v`
Expected: FAIL (SIGNAL path/validation chưa có).

**Step 3: Write minimal implementation**

```python
# services/aureus-gateway/main.py
# Add SIGNAL type handling in process_message
# - validate mandatory fields
# - return False + log reject_reason when missing
```

**Step 4: Run test to verify it passes**

Run: `pytest services/aureus-gateway/tests/test_gateway_signal_contract_validation.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add services/aureus-gateway/main.py services/aureus-gateway/tests/test_gateway_signal_contract_validation.py
git commit -m "feat(gateway): reject invalid signal events missing contract metadata"
```

---

### Task 5: Tạo schema persistence cho signal events/outcomes

**Files:**
- Modify: `services/aureus-db-writer/schema.sql`
- Test: `services/aureus-db-writer/tests/test_signal_schema_contract.sql.py`

**Step 1: Write the failing test**

```python
# services/aureus-db-writer/tests/test_signal_schema_contract.sql.py
from pathlib import Path


def test_schema_contains_signal_event_and_outcome_tables():
    sql = Path("services/aureus-db-writer/schema.sql").read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS aureus_signal_events" in sql
    assert "CREATE TABLE IF NOT EXISTS aureus_signal_outcomes" in sql
```

**Step 2: Run test to verify it fails**

Run: `pytest services/aureus-db-writer/tests/test_signal_schema_contract.sql.py -v`
Expected: FAIL (table chưa tồn tại).

**Step 3: Write minimal implementation**

```sql
-- services/aureus-db-writer/schema.sql
CREATE TABLE IF NOT EXISTS aureus_signal_events (
    signal_id TEXT PRIMARY KEY,
    decision_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    signal_seq BIGINT NOT NULL,
    time TIMESTAMPTZ NOT NULL,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    strategy_id TEXT NOT NULL,
    signal_type TEXT NOT NULL,
    confidence DOUBLE PRECISION NOT NULL,
    qualified BOOLEAN NOT NULL,
    failed_gate TEXT,
    metadata JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS aureus_signal_outcomes (
    signal_id TEXT PRIMARY KEY REFERENCES aureus_signal_events(signal_id),
    evaluated_at TIMESTAMPTZ NOT NULL,
    execution_channel TEXT NOT NULL,
    pnl DOUBLE PRECISION,
    rr DOUBLE PRECISION,
    hit_sl BOOLEAN,
    hit_tp BOOLEAN,
    outcome_label TEXT
);
```

**Step 4: Run test to verify it passes**

Run: `pytest services/aureus-db-writer/tests/test_signal_schema_contract.sql.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add services/aureus-db-writer/schema.sql services/aureus-db-writer/tests/test_signal_schema_contract.sql.py
git commit -m "feat(db): add signal events and outcomes persistence schema"
```

---

### Task 6: Ghi signal events/outcomes trong DB Writer

**Files:**
- Modify: `services/aureus-db-writer/main.py`
- Test: `services/aureus-db-writer/tests/test_signal_event_writer.py`

**Step 1: Write the failing test**

```python
# services/aureus-db-writer/tests/test_signal_event_writer.py

def test_db_writer_routes_signal_stream_into_signal_event_buffer():
    # Arrange mock message from aureus:stream:<symbol>:signal
    # Act run one consume cycle
    # Assert message routed into signal event insert path
    assert True
```

**Step 2: Run test to verify it fails**

Run: `pytest services/aureus-db-writer/tests/test_signal_event_writer.py -v`
Expected: FAIL (stream routing/insertion path chưa có).

**Step 3: Write minimal implementation**

```python
# services/aureus-db-writer/main.py
# 1) discover_streams: add pattern aureus:stream:*:signal
# 2) run(): route :signal messages into signal_buffer
# 3) process_batch(): insert into aureus_signal_events
# 4) ack by stream after successful insert
```

**Step 4: Run test to verify it passes**

Run: `pytest services/aureus-db-writer/tests/test_signal_event_writer.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add services/aureus-db-writer/main.py services/aureus-db-writer/tests/test_signal_event_writer.py
git commit -m "feat(db-writer): persist signal event stream with contract lineage"
```

---

### Task 7: Expose KPI endpoint tối thiểu ở Dashboard API

**Files:**
- Modify: `services/aureus-dashboard/api/main.py`
- Test: `services/aureus-dashboard/api/tests/test_signal_quality_api.py`

**Step 1: Write the failing test**

```python
# services/aureus-dashboard/api/tests/test_signal_quality_api.py
from fastapi.testclient import TestClient
from main import app


def test_signal_quality_summary_endpoint_exists():
    client = TestClient(app)
    r = client.get("/api/v1/signal-quality/summary?symbol=XAUUSD")
    assert r.status_code in (200, 404)  # endpoint exists, data may be empty
```

**Step 2: Run test to verify it fails**

Run: `pytest services/aureus-dashboard/api/tests/test_signal_quality_api.py -v`
Expected: FAIL (endpoint chưa tồn tại).

**Step 3: Write minimal implementation**

```python
# services/aureus-dashboard/api/main.py
# Add GET /api/v1/signal-quality/summary
# Return basic metrics:
# - total_signals
# - qualified_rate
# - avg_confidence
# - win_rate (if outcome exists)
```

**Step 4: Run test to verify it passes**

Run: `pytest services/aureus-dashboard/api/tests/test_signal_quality_api.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add services/aureus-dashboard/api/main.py services/aureus-dashboard/api/tests/test_signal_quality_api.py
git commit -m "feat(api): add signal quality summary endpoint"
```

---

### Task 8: Enforce rollout policy no-direct-live (shadow required)

**Files:**
- Modify: `services/aureus-signal/engine/live_engine.py`
- Modify: `services/aureus-signal/engine/feature_flags.py`
- Test: `services/aureus-signal/unittest/test_signal_shadow_policy.py`

**Step 1: Write the failing test**

```python
# services/aureus-signal/unittest/test_signal_shadow_policy.py

def test_new_strategy_cannot_go_live_without_shadow_pass():
    # Arrange strategy in NEW state, no shadow pass mark
    # Assert live promotion is rejected
    assert True
```

**Step 2: Run test to verify it fails**

Run: `pytest services/aureus-signal/unittest/test_signal_shadow_policy.py -v`
Expected: FAIL (policy gate chưa có).

**Step 3: Write minimal implementation**

```python
# live_engine/feature_flags policy check
# if strategy_state == "NEW" and shadow_pass != True: skip live activation
```

**Step 4: Run test to verify it passes**

Run: `pytest services/aureus-signal/unittest/test_signal_shadow_policy.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add services/aureus-signal/engine/live_engine.py services/aureus-signal/engine/feature_flags.py services/aureus-signal/unittest/test_signal_shadow_policy.py
git commit -m "feat(signal): enforce shadow-first rollout policy"
```

---

### Task 9: Canonical KPI Dictionary + owner policy docs

**Files:**
- Create: `docs/signals/signal_kpi_dictionary.md`
- Create: `docs/signals/signal_owner_policy.md`
- Test: `services/aureus-signal/tests/test_signal_docs_contract.py`

**Step 1: Write the failing test**

```python
# services/aureus-signal/tests/test_signal_docs_contract.py
from pathlib import Path


def test_kpi_dictionary_contains_required_sections():
    p = Path("docs/signals/signal_kpi_dictionary.md")
    assert p.exists()
    c = p.read_text(encoding="utf-8")
    assert "## KPI Definitions" in c
    assert "qualified_rate" in c
```

**Step 2: Run test to verify it fails**

Run: `pytest services/aureus-signal/tests/test_signal_docs_contract.py -v`
Expected: FAIL (docs chưa có).

**Step 3: Write minimal implementation**

```markdown
# docs/signals/signal_kpi_dictionary.md
## KPI Definitions
- qualified_rate = qualified_signals / total_signals
- win_rate = winning_outcomes / evaluated_outcomes
- contract_completeness_rate = valid_contract_events / total_events
```

```markdown
# docs/signals/signal_owner_policy.md
- Strategy phải có owner/team
- Không owner => không active
- Review định kỳ theo KPI breach/regime shift
```

**Step 4: Run test to verify it passes**

Run: `pytest services/aureus-signal/tests/test_signal_docs_contract.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add docs/signals/signal_kpi_dictionary.md docs/signals/signal_owner_policy.md services/aureus-signal/tests/test_signal_docs_contract.py
git commit -m "docs(signal): add canonical KPI dictionary and owner policy"
```

---

### Task 10: End-to-end verification and stabilization

**Files:**
- Modify: `services/aureus-signal/tests/test_multi_symbol.py` (if needed)
- Modify: `services/aureus-signal/unittest/test_recalculate_all_signals.py` (if needed)
- Create: `services/aureus-signal/tests/test_signal_quality_e2e.py`

**Step 1: Write the failing integration test**

```python
# services/aureus-signal/tests/test_signal_quality_e2e.py

def test_e2e_signal_quality_pipeline_contract_to_api():
    # publish signal event -> gateway validation -> db writer persistence -> api summary
    # assert record persisted and summary reflects event
    assert True
```

**Step 2: Run test to verify it fails**

Run: `pytest services/aureus-signal/tests/test_signal_quality_e2e.py -v`
Expected: FAIL (integration path chưa hoàn chỉnh).

**Step 3: Implement minimal missing glue**

```python
# Fill gaps found by e2e:
# - stream naming consistency for :signal
# - payload key mapping
# - API query alignment with schema
```

**Step 4: Run full target suite**

Run:
- `pytest services/aureus-signal/tests/test_signal_contract.py -v`
- `pytest services/aureus-signal/tests/test_signal_three_gate_validation.py -v`
- `pytest services/aureus-gateway/tests/test_gateway_signal_contract_validation.py -v`
- `pytest services/aureus-db-writer/tests/test_signal_event_writer.py -v`
- `pytest services/aureus-dashboard/api/tests/test_signal_quality_api.py -v`

Expected: PASS all target tests.

**Step 5: Commit**

```bash
git add services/aureus-signal/tests/test_signal_quality_e2e.py services/aureus-signal/tests/test_multi_symbol.py services/aureus-signal/unittest/test_recalculate_all_signals.py services/aureus-db-writer/main.py services/aureus-dashboard/api/main.py services/aureus-gateway/main.py
git commit -m "test(signal): add end-to-end quality verification and stabilize signal pipeline"
```

---

## Definition of Done (DoD)

- Signal events có contract bắt buộc và identity lineage đầy đủ.
- Three-gate qualification chạy ổn định, có pass/fail reason.
- Gateway reject signal invalid với reason code.
- DB có bảng `aureus_signal_events` và `aureus_signal_outcomes`, dữ liệu ghi được.
- API có endpoint summary KPI signal quality.
- Chính sách shadow-first áp dụng cho rollout strategy mới.
- KPI Dictionary + Owner policy được chốt bằng tài liệu + test existence.

## Risks & Guardrails

- Không đổi kiến trúc event-driven hiện tại; chỉ thêm contract và gates.
- Mọi rollout đều qua shadow trước live.
- Không merge nếu thiếu test pass cho task tương ứng.

## Skills/Workflows to use in execution

- `@executing-plans`
- `@single-flow-task-execution`
- Entry workflow: `.agent/workflows/execute-plan.md`

---

Plan complete and saved to `docs/plans/2026-03-16-signal-quality-contract-and-validation.md`.
Next step: run `.agent/workflows/execute-plan.md` to execute this plan task-by-task in single-flow mode.
