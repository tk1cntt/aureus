from __future__ import annotations

import argparse
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List

import redis


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay candle data into Redis with duplicate/stale scenario support")
    parser.add_argument("--redis-host", default="localhost")
    parser.add_argument("--redis-port", type=int, default=6379)
    parser.add_argument("--symbol", default="XAUUSD")
    parser.add_argument("--stream", default="candle")
    parser.add_argument("--log-path", default=str(Path(__file__).resolve().parent / "gateway.log"))
    parser.add_argument("--scenario", choices=["normal", "duplicate", "stale"], default="normal")
    parser.add_argument("--clear-stream", action="store_true")
    parser.add_argument("--max-events", type=int, default=0, help="0 means replay all parsed events")
    return parser.parse_args()


def _parse_gateway_lines(log_path: Path, symbol: str) -> List[dict[str, str]]:
    if not log_path.exists():
        raise FileNotFoundError(f"Gateway log not found: {log_path}")

    pattern = re.compile(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) @ ([\d.]+)")
    candles: List[dict[str, str]] = []

    for line in log_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if "BACKFILL candle" not in line:
            continue

        match = pattern.search(line)
        if not match:
            continue

        dt_str, price = match.group(1), match.group(2)
        dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        ts_ms = int(dt.timestamp() * 1000)

        candles.append(
            {
                "type": "CANDLE",
                "symbol": symbol,
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "volume": "100",
                "timestamp": str(ts_ms),
                "tf": "M1",
            }
        )

    return candles


def _apply_scenario(events: List[dict[str, str]], scenario: str) -> List[dict[str, str]]:
    if scenario == "normal" or not events:
        return events

    updated = list(events)

    if scenario == "duplicate":
        duplicate_count = min(5, len(events))
        updated.extend(events[:duplicate_count])
        return updated

    # scenario == "stale": create stale business-timestamp samples
    stale_count = min(5, len(events))
    for event in events[:stale_count]:
        stale_event = dict(event)
        stale_event["timestamp"] = str(max(0, int(event["timestamp"]) - 300_000))
        updated.append(stale_event)
    return updated


def _iter_limited(events: List[dict[str, str]], max_events: int) -> Iterable[dict[str, str]]:
    if max_events <= 0:
        return events
    return events[:max_events]


def replay() -> None:
    args = _parse_args()
    redis_client = redis.Redis(host=args.redis_host, port=args.redis_port, decode_responses=True)
    stream_key = f"aureus:stream:{args.symbol}:{args.stream}"

    if args.clear_stream:
        redis_client.delete(stream_key)
        print(f"Cleared stream: {stream_key}")

    parsed_events = _parse_gateway_lines(Path(args.log_path), args.symbol)
    scenario_events = _apply_scenario(parsed_events, args.scenario)

    replayed = 0
    for event in _iter_limited(scenario_events, args.max_events):
        redis_client.xadd(stream_key, event, maxlen=5000)
        replayed += 1

    print(f"Replayed {replayed} events to {stream_key} using scenario={args.scenario}")
    redis_client.close()


if __name__ == "__main__":
    replay()
