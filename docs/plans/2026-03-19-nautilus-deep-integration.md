# Nautilus Deep Integration (Slice 2) Implementation Plan

> **For Antigravity:** REQUIRED WORKFLOW: Use `.agent/workflows/execute-plan.md` to execute this plan in single-flow mode.

**Goal:** Create a standalone Nautilus `LiveTradingNode` that receives live M1 candles from Redis, executes orders via an internal matching engine, and synchronizes positions/executions back to Redis for monitoring.

**Architecture:** A new service `aureus-nautilus-node` will enclose `LiveTradingNode` and plug in two custom clients: `AureusMarketDataClient` (Redis to Nautilus M1 OHLC) and `AureusExecutionClient` (Redis to Nautilus Portfolio).

**Tech Stack:** Python, Redis Streams, Nautilus Trader, pytest, docker-compose.

---

### Task 1: Nautilus Node Scaffold and Configuration

**Files:**
- Create: `services/aureus-nautilus-node/main.py`
- Create: `services/aureus-nautilus-node/config.py`
- Test: `services/aureus-nautilus-node/tests/test_node_setup.py`

**Step 1: Write the failing test**

```python
import pytest
from nautilus_trader.live.node import LiveTradingNode
from config import get_node_config

def test_node_configuration_creates_valid_clock():
    config = get_node_config()
    node = LiveTradingNode(config=config)
    assert node.clock is not None
```

**Step 2: Run test to verify it fails**

Run: `wsl -d Ubuntu-24.04 -e bash -lc "cd /mnt/d/AIFramework/aureus/services/aureus-nautilus-node && PYTHONPATH=. pytest tests/test_node_setup.py -v"`
Expected: FAIL with ModuleNotFoundError or similar

**Step 3: Write minimal implementation**

Create standard config and node initialization in `config.py` and `main.py`.

**Step 4: Run test to verify it passes**

Run: `wsl -d Ubuntu-24.04 -e bash -lc "cd /mnt/d/AIFramework/aureus/services/aureus-nautilus-node && PYTHONPATH=. pytest tests/test_node_setup.py -v"`
Expected: PASS

**Step 5: Commit**

```bash
git add services/aureus-nautilus-node/
git commit -m "feat(nautilus-node): scaffold LiveTradingNode configuration"
```

---

### Task 2: AureusMarketDataClient

**Files:**
- Create: `services/aureus-nautilus-node/data_client.py`
- Test: `services/aureus-nautilus-node/tests/test_data_client.py`

**Step 1: Write the failing test**

```python
import pytest
from unittest.mock import AsyncMock, patch
from data_client import AureusMarketDataClient

@pytest.mark.asyncio
async def test_market_data_client_parses_redis_candle():
    client = AureusMarketDataClient(redis_client=AsyncMock())
    # Mock redis xread to return 1 candle
    client.redis.xread.return_value = [
        [b"aureus:stream:XAUUSD:candle", [
            (b"1678888-0", {b"open": b"2000.0", b"high": b"2005.0", b"low": b"1995.0", b"close": b"2002.0", b"volume": b"100", b"timestamp": b"1678888000"})
        ]]
    ]
    with patch.object(client.msg_bus, 'publish') as mock_publish:
        await client._poll_market_data()
        assert mock_publish.called
        # Verify it published a Bar instance
```

**Step 2: Run test to verify it fails**

Run: `wsl -d Ubuntu-24.04 -e bash -lc "cd /mnt/d/AIFramework/aureus/services/aureus-nautilus-node && PYTHONPATH=. pytest tests/test_data_client.py -v"`
Expected: FAIL

**Step 3: Write minimal implementation**

Implement `AureusMarketDataClient` deriving from `LiveMarketDataClient`, polling continuous `xread` and mapping payload to Nautilus `Bar` types.

**Step 4: Run test to verify it passes**

Run: `wsl -d Ubuntu-24.04 -e bash -lc "cd /mnt/d/AIFramework/aureus/services/aureus-nautilus-node && PYTHONPATH=. pytest tests/test_data_client.py -v"`
Expected: PASS

**Step 5: Commit**

```bash
git add services/aureus-nautilus-node/
git commit -m "feat(nautilus-node): implement redis m1 candle market data client"
```

---

### Task 3: AureusExecutionClient (Order Router)

**Files:**
- Create: `services/aureus-nautilus-node/execution_client.py`
- Test: `services/aureus-nautilus-node/tests/test_execution_client.py`

**Step 1: Write the failing test**

```python
import pytest
from unittest.mock import AsyncMock, patch
from execution_client import AureusExecutionClient

@pytest.mark.asyncio
async def test_execution_client_converts_order_intent():
    client = AureusExecutionClient(redis_client=AsyncMock())
    client.redis.xread.return_value = [
        [b"aureus:stream:XAUUSD:orders", [
            (b"1678888-0", {b"type": b"ORDER_OPEN", b"data": b'{"trace_id": "t1", "symbol": "XAUUSD", "side": "BUY", "qty": 1.0, "sl": 1990.0, "tp": 2020.0}'})
        ]]
    ]
    with patch.object(client, 'generate_order') as mock_gen:
        await client._poll_orders()
        assert mock_gen.called
        order = mock_gen.call_args[0][0]
        assert order.instrument_id.symbol.value == "XAUUSD"
        assert order.quantity.as_double() == 1.0
```

**Step 2: Run test to verify it fails**

Run: `wsl -d Ubuntu-24.04 -e bash -lc "cd /mnt/d/AIFramework/aureus/services/aureus-nautilus-node && PYTHONPATH=. pytest tests/test_execution_client.py -v"`
Expected: FAIL

**Step 3: Write minimal implementation**

Implement `AureusExecutionClient` to consume Redis intent, build `SubmitOrder` with OCO logic if SL/TP present, and call `generate_order()`.

**Step 4: Run test to verify it passes**

Run: `wsl -d Ubuntu-24.04 -e bash -lc "cd /mnt/d/AIFramework/aureus/services/aureus-nautilus-node && PYTHONPATH=. pytest tests/test_execution_client.py -v"`
Expected: PASS

**Step 5: Commit**

```bash
git add services/aureus-nautilus-node/
git commit -m "feat(nautilus-node): implement redis order ingestion and routing"
```

---

### Task 4: Sync Worker (Feedback Loop)

**Files:**
- Create: `services/aureus-nautilus-node/sync_worker.py`
- Test: `services/aureus-nautilus-node/tests/test_sync_worker.py`

**Step 1: Write the failing test**

```python
import pytest
from unittest.mock import AsyncMock
from sync_worker import SyncWorker
from nautilus_trader.core.message import Event

def test_sync_worker_pushes_order_event():
    redis_mock = AsyncMock()
    worker = SyncWorker(redis_client=redis_mock)
    # create fake OrderEvent
    worker.on_order_event(fake_order_event)
    redis_mock.xadd.assert_called()
```

**Step 2: Run test to verify it fails**

Run: `wsl -d Ubuntu-24.04 -e bash -lc "cd /mnt/d/AIFramework/aureus/services/aureus-nautilus-node && PYTHONPATH=. pytest tests/test_sync_worker.py -v"`
Expected: FAIL

**Step 3: Write minimal implementation**

Implement generic handlers connected to `msg_bus` that unpack `OrderEvent` and `PositionEvent` and XADD to `aureus:stream:*:execution` and `*:positions`.

**Step 4: Run test to verify it passes**

Run: `wsl -d Ubuntu-24.04 -e bash -lc "cd /mnt/d/AIFramework/aureus/services/aureus-nautilus-node && PYTHONPATH=. pytest tests/test_sync_worker.py -v"`
Expected: PASS

**Step 5: Commit**

```bash
git add services/aureus-nautilus-node/
git commit -m "feat(nautilus-node): sync internal portfolio events to redis streams"
```

---

### Task 5: Docker Compose Integration

**Files:**
- Modify: `docker-compose.dev.yml`
- Create: `services/aureus-nautilus-node/Dockerfile`

**Step 1: Add new service**
Define `aureus-nautilus-node` in compose file.

**Step 2: Remove old bridge mock (Optional)**
Disable or re-route `aureus-nautilus-bridge` mock from Slice 1 to avoid conflicts.

**Step 3: Verification**
```bash
wsl -e sh -lc "cd /mnt/d/AIFramework/aureus && docker compose -f docker-compose.dev.yml up --build -d aureus-nautilus-node"
```

**Step 4: Commit**

```bash
git add docker-compose.dev.yml services/aureus-nautilus-node/Dockerfile
git commit -m "feat(compose): switch to deep integrated nautilus node"
```
