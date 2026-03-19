import pytest
from unittest.mock import AsyncMock, patch
from sync_worker import SyncWorker
from nautilus_trader.core.message import Event
from nautilus_trader.model.events import OrderEvent
from nautilus_trader.model.events import OrderEvent, OrderAccepted

@pytest.mark.asyncio
async def test_sync_worker_pushes_order_event():
    redis_mock = AsyncMock()
    worker = SyncWorker(redis_client=redis_mock)
    
    # We will use a mock OrderEvent since creating full Nautilus events in isolation can be complex.
    # In a real scenario we'd use a factory or captured event.
    class FakeOrderEvent:
        pass
    
    fake_event = FakeOrderEvent()
    # Mock the internal extraction
    with patch.object(worker, '_handle_order_event') as mock_handle:
        worker.on_order_event(fake_event)
        worker._running = True
        # trigger processing queue
        await worker._process_queue_once()
        assert mock_handle.called
