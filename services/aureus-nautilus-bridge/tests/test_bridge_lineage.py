import asyncio
import os
import sys
from unittest.mock import AsyncMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from main import AureusNautilusBridge


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _lifecycle_payload(report):
    return {
        "type": "NAUTILUS_EXECUTION_REPORT",
        "data": report,
    }


def test_lifecycle_keeps_strategy_and_correlation_from_pending_intent():
    bridge = AureusNautilusBridge()
    bridge._publish_execution_event = AsyncMock()

    trace_id = "EURUSD:11:1709300400"
    bridge.pending_intents[trace_id] = {
        "trace_id": trace_id,
        "symbol": "EURUSD",
        "event_time": 1709300400,
        "side": "BUY",
        "type": "MARKET",
        "quantity": 0.5,
        "entry_price": 1.081,
        "strategy_id": "strat-eur-breakout",
        "strategy_name": "EUR Breakout",
        "correlation_id": "corr-eur-11",
        "execution_mode": "nautilus",
    }

    report = {
        "trace_id": trace_id,
        "symbol": "EURUSD",
        "status": "PARTIAL_FILL",
        "event_time": 1709300402,
        "quantity": 0.5,
        "fill_price": 1.0812,
    }

    run(bridge._handle_lifecycle_message("1-0", _lifecycle_payload(report)))

    event = bridge._publish_execution_event.await_args.args[0]
    assert event["strategy_id"] == "strat-eur-breakout"
    assert event["strategy_name"] == "EUR Breakout"
    assert event["correlation_id"] == "corr-eur-11"


def test_lifecycle_fallback_synthesizes_minimal_valid_intent_when_missing_pending():
    bridge = AureusNautilusBridge()
    bridge._publish_execution_event = AsyncMock()

    report = {
        "trace_id": "GBPUSD:12:1709300500",
        "symbol": "GBPUSD",
        "status": "ORDER_ACCEPTED",
        "event_time": 1709300501,
        "side": "SELL",
        "type": "LIMIT",
        "qty": 0.2,
        "fill_price": 1.262,
    }

    run(bridge._handle_lifecycle_message("2-0", _lifecycle_payload(report)))

    event = bridge._publish_execution_event.await_args.args[0]
    assert event["trace_id"] == report["trace_id"]
    assert event["symbol"] == report["symbol"]
    assert event["side"] == "SELL"
    assert event["type"] == "LIMIT"
    assert event["quantity"] == 0.2
