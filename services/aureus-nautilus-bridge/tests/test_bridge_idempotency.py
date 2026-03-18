import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from main import BridgeProcessor


class FakeAdapter:
    def __init__(self):
        self.calls = 0

    async def submit_order(self, intent):
        self.calls += 1
        return {
            "status": "ORDER_ACCEPTED",
            "event_time": intent["event_time"],
            "fill_price": intent.get("entry_price", 0.0),
            "quantity": intent.get("quantity", 1.0),
            "adapter_order_id": f"fake-{self.calls}",
        }


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def test_duplicate_trace_id_is_ignored_by_processor():
    adapter = FakeAdapter()
    processor = BridgeProcessor(adapter=adapter)

    order_payload = {
        "trace_id": "XAUUSD:7:1709300000",
        "symbol": "XAUUSD",
        "event_time": 1709300000,
        "side": "BUY",
        "type": "MARKET",
        "quantity": 1.0,
        "entry_price": 2001.0,
        "execution_mode": "nautilus",
    }

    first = run(processor.process_order_event("ORDER_OPEN", order_payload))
    second = run(processor.process_order_event("ORDER_OPEN", order_payload))

    assert first is not None
    assert second is None, "Duplicate trace_id should not emit a second event"
    assert adapter.calls == 2, "Adapter may still be called before reconciliation blocks duplicate status"


def test_non_order_open_events_are_skipped():
    processor = BridgeProcessor(adapter=FakeAdapter())
    order_payload = {
        "trace_id": "XAUUSD:8:1709300001",
        "symbol": "XAUUSD",
        "event_time": 1709300001,
    }

    result = run(processor.process_order_event("ORDER_PENDING", order_payload))
    assert result is None


if __name__ == "__main__":
    test_duplicate_trace_id_is_ignored_by_processor()
    test_non_order_open_events_are_skipped()
    print("All bridge idempotency tests passed")
