#!/usr/bin/env python3
"""Manual E2E checklist runner for Aureus ↔ Nautilus bridge flow.

Checklist:
1) Publish one ORDER_OPEN with a generated trace_id.
2) Wait for execution event on aureus:stream:{symbol}:execution.
3) Replay same ORDER_OPEN with identical trace_id.
4) Ensure execution stream count for trace_id does not increase unexpectedly.
5) Query DB table aureus_execution_events for the trace_id.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
import uuid
from typing import Any

import redis


DEFAULT_SYMBOL = "XAUUSD"
DEFAULT_REDIS_HOST = "127.0.0.1"
DEFAULT_REDIS_PORT = 6380
DEFAULT_TIMEOUT = 30


def _decode(value: Any) -> Any:
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return value


def _decode_map(data: dict[Any, Any]) -> dict[str, Any]:
    return {str(_decode(k)): _decode(v) for k, v in data.items()}


def build_order_payload(trace_id: str, symbol: str) -> dict[str, Any]:
    now = int(time.time())
    return {
        "trace_id": trace_id,
        "symbol": symbol,
        "event_time": now,
        "side": "BUY",
        "type": "MARKET",
        "quantity": 1.0,
        "entry_price": 3000.0,
        "sl": 2995.0,
        "tp": 3010.0,
        "strategy_id": "manual-e2e-checklist",
        "execution_mode": "nautilus",
    }


def publish_order(client: redis.Redis, order_stream: str, payload: dict[str, Any]) -> str:
    message_id = client.xadd(
        order_stream,
        {
            "type": "ORDER_OPEN",
            "data": json.dumps(payload),
        },
    )
    return str(_decode(message_id))


def collect_trace_events(
    client: redis.Redis,
    execution_stream: str,
    trace_id: str,
    timeout: int,
) -> list[tuple[str, dict[str, Any]]]:
    deadline = time.time() + timeout
    while time.time() < deadline:
        entries = client.xrevrange(execution_stream, count=200)
        matches: list[tuple[str, dict[str, Any]]] = []
        for entry_id, fields in entries:
            decoded_fields = _decode_map(fields)
            raw_data = decoded_fields.get("data")
            if not raw_data:
                continue
            try:
                event = json.loads(raw_data)
            except Exception:
                continue
            if event.get("trace_id") == trace_id:
                matches.append((str(_decode(entry_id)), event))
        if matches:
            return matches
        time.sleep(1)
    return []


def query_db_rows(trace_id: str) -> tuple[int, str]:
    sql = (
        "SELECT trace_id,status,event_time,side,quantity,fill_price,execution_mode "
        "FROM aureus_execution_events "
        f"WHERE trace_id = '{trace_id}' ORDER BY event_time ASC;"
    )
    cmd = [
        "wsl",
        "-d",
        "Ubuntu-24.04",
        "-u",
        "root",
        "bash",
        "-lc",
        (
            "docker exec aureus_timescaledb_dev "
            "psql -U aureus -d aureus -t -A -F '|' "
            f"-c \"{sql}\""
        ),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    output = (proc.stdout or "").strip()
    if proc.returncode != 0:
        return 0, f"[DB-ERROR] return_code={proc.returncode} stderr={proc.stderr.strip()}"
    lines = [line for line in output.splitlines() if line.strip()]
    return len(lines), "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run manual E2E checklist")
    parser.add_argument("--redis-host", default=DEFAULT_REDIS_HOST)
    parser.add_argument("--redis-port", type=int, default=DEFAULT_REDIS_PORT)
    parser.add_argument("--symbol", default=DEFAULT_SYMBOL)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    args = parser.parse_args()

    trace_id = f"manual-e2e:{args.symbol}:{int(time.time())}:{uuid.uuid4().hex[:8]}"
    order_stream = f"aureus:stream:{args.symbol}:orders"
    execution_stream = f"aureus:stream:{args.symbol}:execution"

    print(f"[INFO] Redis: {args.redis_host}:{args.redis_port}")
    print(f"[INFO] Symbol: {args.symbol}")
    print(f"[INFO] Trace ID: {trace_id}")

    client = redis.Redis(host=args.redis_host, port=args.redis_port, decode_responses=False)
    client.ping()

    payload = build_order_payload(trace_id, args.symbol)

    msg1 = publish_order(client, order_stream, payload)
    print(f"[STEP 1] Published first ORDER_OPEN id={msg1}")

    events_after_first = collect_trace_events(client, execution_stream, trace_id, args.timeout)
    if not events_after_first:
        print("[FAIL] No execution event received after first publish")
        return 1

    print(f"[STEP 2] Execution events after first publish: {len(events_after_first)}")
    first_statuses = [e[1].get("status") for e in events_after_first]
    print(f"[STEP 2] Statuses: {first_statuses}")

    msg2 = publish_order(client, order_stream, payload)
    print(f"[STEP 3] Replayed same trace_id ORDER_OPEN id={msg2}")

    time.sleep(3)
    events_after_replay = collect_trace_events(client, execution_stream, trace_id, args.timeout)
    replay_count = len(events_after_replay)
    print(f"[STEP 4] Execution events after replay: {replay_count}")

    if replay_count > len(events_after_first):
        print(
            "[WARN] Execution events increased after replay. "
            "This may be valid only if lifecycle transition occurred; investigate statuses."
        )
    else:
        print("[PASS] No additional execution events created by duplicate replay")

    db_count, db_output = query_db_rows(trace_id)
    print(f"[STEP 5] DB rows for trace_id: {db_count}")
    if db_output:
        print("[STEP 5] DB rows detail:")
        print(db_output)

    if db_count == 0:
        print("[FAIL] No persisted execution row found in aureus_execution_events")
        return 1

    print("[PASS] Manual E2E checklist completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
