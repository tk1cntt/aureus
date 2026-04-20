import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mapper import map_order_intent


def test_map_order_intent_accepts_qty_alias_when_quantity_missing():
    payload = {
        "trace_id": "EURUSD:42:1709300000",
        "symbol": "EURUSD",
        "event_time": "1709300000",
        "side": "buy",
        "type": "limit",
        "qty": "0.25",
        "entry_price": "1.08123",
    }

    intent = map_order_intent(payload)

    assert intent["quantity"] == 0.25
    assert intent["type"] == "LIMIT"
    assert intent["event_time"] == 1709300000
