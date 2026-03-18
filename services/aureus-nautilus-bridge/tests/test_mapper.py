import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mapper import build_execution_event, map_order_intent, map_status


def test_map_order_intent_normalizes_fields():
    payload = {
        "trace_id": "XAUUSD:42:1709300000",
        "symbol": "XAUUSD",
        "event_time": "1709300000",
        "side": "buy",
        "type": "market",
        "quantity": "2",
        "entry_price": "2010.5",
    }

    intent = map_order_intent(payload)

    assert intent["trace_id"] == "XAUUSD:42:1709300000"
    assert intent["symbol"] == "XAUUSD"
    assert intent["event_time"] == 1709300000
    assert intent["side"] == "BUY"
    assert intent["type"] == "MARKET"
    assert intent["quantity"] == 2.0
    assert intent["entry_price"] == 2010.5


def test_map_order_intent_requires_trace_id_symbol_event_time():
    bad_payload = {"symbol": "XAUUSD", "event_time": 1709300000}
    try:
        map_order_intent(bad_payload)
        raise AssertionError("Expected ValueError for missing trace_id")
    except ValueError as exc:
        assert "trace_id" in str(exc)


def test_build_execution_event_maps_status_and_preserves_required_fields():
    intent = {
        "trace_id": "XAUUSD:99:1709300000",
        "symbol": "XAUUSD",
        "event_time": 1709300000,
        "side": "SELL",
        "type": "MARKET",
        "quantity": 1.0,
        "entry_price": 2000.0,
        "execution_mode": "nautilus",
    }

    adapter_report = {
        "status": "PARTIALLY_FILLED",
        "event_time": 1709300010,
        "fill_price": 1999.8,
        "quantity": 0.4,
        "adapter_order_id": "nt-001",
    }

    event = build_execution_event(intent, adapter_report)

    assert event["trace_id"] == intent["trace_id"]
    assert event["symbol"] == intent["symbol"]
    assert event["event_time"] == 1709300010
    assert event["status"] == "PARTIAL_FILL"
    assert event["fill_price"] == 1999.8
    assert event["adapter_order_id"] == "nt-001"


def test_map_status_defaults_to_rejected_for_unknown_values():
    assert map_status("not_a_real_status") == "REJECTED"


if __name__ == "__main__":
    test_map_order_intent_normalizes_fields()
    test_map_order_intent_requires_trace_id_symbol_event_time()
    test_build_execution_event_maps_status_and_preserves_required_fields()
    test_map_status_defaults_to_rejected_for_unknown_values()
    print("All mapper tests passed")
