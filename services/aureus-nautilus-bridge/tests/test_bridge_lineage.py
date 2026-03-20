import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from main import BridgeProcessor


class StaticAdapter:
    async def submit_order(self, intent):
        return {
            "status": "ORDER_ACCEPTED",
            "event_time": intent["event_time"],
            "fill_price": intent.get("entry_price", 0.0),
            "quantity": intent.get("quantity", 1.0),
            "adapter_order_id": "adapter-1",
        }


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _order_payload_with_lineage():
    return {
        "trace_id": "XAUUSD:9:1709300200",
        "correlation_id": "corr-xyz-001",
        "strategy_id": "strat-breakout",
        "strategy_version": "2.4.1",
        "symbol": "XAUUSD",
        "event_time": 1709300200,
        "side": "BUY",
        "type": "MARKET",
        "quantity": 1.0,
        "entry_price": 2003.0,
        "sl": 1998.0,
        "tp": 2015.0,
        "execution_mode": "nautilus",
    }


def test_process_order_event_propagates_lineage_fields_into_execution_event():
    processor = BridgeProcessor(adapter=StaticAdapter())

    event = run(processor.process_order_event("ORDER_OPEN", _order_payload_with_lineage()))

    assert event is not None
    assert event["trace_id"] == "XAUUSD:9:1709300200"
    assert event["correlation_id"] == "corr-xyz-001"
    assert event["strategy_id"] == "strat-breakout"
    assert event["strategy_version"] == "2.4.1"


def test_lifecycle_fallback_payload_carries_correlation_and_strategy_lineage():
    from main import AureusNautilusBridge

    bridge = AureusNautilusBridge()
    bridge.processor = BridgeProcessor(adapter=StaticAdapter())

    report = {
        "trace_id": "XAUUSD:10:1709300300",
        "correlation_id": "corr-lifecycle-1",
        "strategy_id": "strat-meanrev",
        "strategy_version": "1.9.0",
        "symbol": "XAUUSD",
        "status": "PARTIAL_FILL",
        "event_time": 1709300302,
        "quantity": 1.0,
        "fill_price": 2004.0,
    }

    event = run(bridge.processor.process_lifecycle_report(
        {
            "trace_id": report["trace_id"],
            "correlation_id": report["correlation_id"],
            "strategy_id": report["strategy_id"],
            "strategy_version": report["strategy_version"],
            "symbol": report["symbol"],
            "event_time": report["event_time"],
            "side": "BUY",
            "type": "MARKET",
            "quantity": report["quantity"],
            "entry_price": report["fill_price"],
            "execution_mode": "nautilus",
        },
        report,
    ))

    assert event is not None
    assert event["correlation_id"] == "corr-lifecycle-1"
    assert event["strategy_id"] == "strat-meanrev"
    assert event["strategy_version"] == "1.9.0"
