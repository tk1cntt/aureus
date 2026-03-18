import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from main import BridgeProcessor


class SequencedAdapter:
    def __init__(self, reports):
        self._reports = reports
        self.calls = 0

    async def submit_order(self, intent):
        self.calls += 1
        index = min(self.calls - 1, len(self._reports) - 1)
        base = {
            "event_time": intent["event_time"],
            "fill_price": intent.get("entry_price", 0.0),
            "quantity": intent.get("quantity", 1.0),
            "adapter_order_id": f"fake-{self.calls}",
        }
        base.update(self._reports[index])
        return base


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _base_order_payload():
    return {
        "trace_id": "XAUUSD:7:1709300000",
        "symbol": "XAUUSD",
        "event_time": 1709300000,
        "side": "BUY",
        "type": "MARKET",
        "quantity": 1.0,
        "entry_price": 2001.0,
        "sl": 1995.0,
        "tp": 2012.0,
        "execution_mode": "nautilus",
    }


def test_duplicate_same_status_is_suppressed_after_first_emit():
    adapter = SequencedAdapter([
        {"status": "ORDER_ACCEPTED"},
        {"status": "ORDER_ACCEPTED"},
    ])
    processor = BridgeProcessor(adapter=adapter)

    first = run(processor.process_order_event("ORDER_OPEN", _base_order_payload()))
    second = run(processor.process_order_event("ORDER_OPEN", _base_order_payload()))

    assert first is not None
    assert second is None, "Duplicate trace_id with unchanged status should not emit a second event"
    assert adapter.calls == 2


def test_status_transition_emits_next_event_with_v2_fields():
    adapter = SequencedAdapter([
        {"status": "ORDER_ACCEPTED", "position_id": "pos-1", "realized_pnl": 0.0, "unrealized_pnl": 0.0},
        {"status": "PARTIAL_FILL", "position_id": "pos-1", "realized_pnl": 1.2, "unrealized_pnl": 3.4},
    ])
    processor = BridgeProcessor(adapter=adapter)

    accepted = run(processor.process_order_event("ORDER_OPEN", _base_order_payload()))
    partial = run(processor.process_order_event("ORDER_OPEN", _base_order_payload()))

    assert accepted is not None
    assert partial is not None
    assert partial["status"] == "PARTIAL_FILL"
    assert partial["entry_price"] == 2001.0
    assert partial["sl"] == 1995.0
    assert partial["tp"] == 2012.0
    assert partial["position_id"] == "pos-1"
    assert partial["realized_pnl"] == 1.2
    assert partial["unrealized_pnl"] == 3.4
    assert partial["event_version"] == 2


def test_non_order_open_events_are_skipped():
    processor = BridgeProcessor(adapter=SequencedAdapter([{"status": "ORDER_ACCEPTED"}]))
    order_payload = {
        "trace_id": "XAUUSD:8:1709300001",
        "symbol": "XAUUSD",
        "event_time": 1709300001,
    }

    result = run(processor.process_order_event("ORDER_PENDING", order_payload))
    assert result is None


if __name__ == "__main__":
    test_duplicate_same_status_is_suppressed_after_first_emit()
    test_status_transition_emits_next_event_with_v2_fields()
    test_non_order_open_events_are_skipped()
    print("All bridge idempotency tests passed")
