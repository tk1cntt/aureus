#!/usr/bin/env python3
"""End-to-end Redis flow test for Aureus Nautilus bridge path.

This script publishes one synthetic ORDER_OPEN event to:
  aureus:stream:{symbol}:orders
Then polls:
  aureus:stream:{symbol}:execution
for a matching trace_id execution event.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from typing import Any, Dict

import redis


DEFAULT_SYMBOL = "XAUUSD"


def _decode(value: Any) -> Any:
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return value


def _decode_map(data: Dict[Any, Any]) -> Dict[str, Any]:
    return {str(_decode(k)): _decode(v) for k, v in data.items()}


def build_order_payload(trace_id: str, symbol: str) -> Dict[str, Any]:
    now = int(time.time())
    return {
        "trace_id": trace_id,
        "symbol": symbol,
        "event_time": now,
        "side": "BUY",
        "type": "MARKET",
        "quantity": 1.0,
        "entry_price": 3000.0,
        "strategy_id": "nautilus-flow-test",
        "execution_mode": "nautilus",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Test Redis order->execution flow")
    parser.add_argument("--redis-host", default=os.getenv("REDIS_HOST", "redis-dev"))
    parser.add_argument("--redis-port", type=int, default=int(os.getenv("REDIS_PORT", "6379")))
    parser.add_argument("--symbol", default=DEFAULT_SYMBOL)
    parser.add_argument("--timeout", type=int, default=25)
    args = parser.parse_args()

    order_stream = f"aureus:stream:{args.symbol}:orders"
    execution_stream = f"aureus:stream:{args.symbol}:execution"

    trace_id = f"flowtest:{args.symbol}:{int(time.time())}:{uuid.uuid4().hex[:8]}"
    order_payload = build_order_payload(trace_id, args.symbol)

    print(f"[INFO] Connecting Redis: {args.redis_host}:{args.redis_port}")
    client = redis.Redis(host=args.redis_host, port=args.redis_port, decode_responses=False)
    client.ping()

    before_last = client.xrevrange(execution_stream, count=1)
    before_last_id = _decode(before_last[0][0]) if before_last else "0-0"
    print(f"[INFO] execution stream last id before publish: {before_last_id}")

    order_event = {
        "type": "ORDER_OPEN",
        "data": json.dumps(order_payload),
    }
    message_id = client.xadd(order_stream, order_event)
    print(f"[INFO] Published ORDER_OPEN to {order_stream} msg_id={_decode(message_id)} trace_id={trace_id}")

    deadline = time.time() + args.timeout
    while time.time() < deadline:
        entries = client.xrevrange(execution_stream, count=30)
        for entry_id, fields in entries:
            decoded_fields = _decode_map(fields)
            raw_data = decoded_fields.get("data")
            if not raw_data:
                continue
            try:
                event = json.loads(raw_data)
            except Exception:
                continue
            if event.get("trace_id") != trace_id:
                continue

            print(f"[PASS] Found execution event id={_decode(entry_id)} for trace_id={trace_id}")
            print(f"[PASS] status={event.get('status')} adapter_order_id={event.get('adapter_order_id')}")
            print(
                "[NOTE] Current Slice 1 bridge uses simulated adapter contract; "
                "this verifies Redis->bridge->execution flow."
            )
            return 0
        time.sleep(1)

    print(
        f"[FAIL] Timeout after {args.timeout}s: no execution event for trace_id={trace_id} "
        f"on {execution_stream}",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
