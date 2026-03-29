"""Standalone CLI to test pulse prompt/context from log_signal_normalize JSON.

Usage examples:
  python scripts/pulse_prompt_cli.py --input-json tests/fixtures/pulse_log_signal_normalize.json --symbol BTCUSD --trigger PERIODIC_PULSE
  python scripts/pulse_prompt_cli.py --input-json /tmp/pulse.json --symbol BTCUSD --request-llm --model meta-llama/Llama-3.2-3B-Instruct
"""

import argparse
import asyncio
import json
import os
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Sequence

import pandas as pd

# Add parent directory so engine imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine.ai_validator import AIBrainClient, ContextBuilder


@dataclass
class PulseStateAdapter:
    symbol: str
    signal_history_normalized: List[Dict[str, Any]]
    last_candle: Dict[str, Any]
    swing_points: List[Dict[str, Any]] = field(default_factory=list)
    signal_history: List[Dict[str, Any]] = field(default_factory=list)
    obs: List[Dict[str, Any]] = field(default_factory=list)
    candle_actors: Dict[str, Any] = field(default_factory=dict)


def extract_log_signal_records(payload: Any) -> List[Dict[str, Any]]:
    """Accept payload as raw list or object containing log-signal keys."""
    if isinstance(payload, list):
        records = payload
    elif isinstance(payload, dict):
        if isinstance(payload.get("log_signal_normalize"), list):
            records = payload["log_signal_normalize"]
        elif isinstance(payload.get("signal_history_normalized"), list):
            records = payload["signal_history_normalized"]
        elif isinstance(payload.get("records"), list):
            records = payload["records"]
        else:
            records = []
    else:
        records = []

    normalized: List[Dict[str, Any]] = []
    for item in records:
        if not isinstance(item, dict):
            continue
        signals = item.get("signals") if isinstance(item.get("signals"), dict) else {}
        if not signals:
            continue

        try:
            t = int(item.get("t"))
        except (TypeError, ValueError):
            continue

        price_raw = item.get("price")
        try:
            price = float(price_raw) if price_raw is not None else None
        except (TypeError, ValueError):
            price = None

        row = {"t": t, "signals": signals}
        if price is not None:
            row["price"] = price
        normalized.append(row)

    normalized.sort(key=lambda x: int(x.get("t", 0)))
    return normalized


def _resolve_price(record: Dict[str, Any], fallback: float) -> float:
    price_raw = record.get("price")
    if price_raw is not None:
        try:
            return float(price_raw)
        except (TypeError, ValueError):
            pass

    signals = record.get("signals") if isinstance(record.get("signals"), dict) else {}
    for key in ("zigzag", "htf_trend", "market_session"):
        candidate = signals.get(key)
        if isinstance(candidate, dict):
            for value_key in ("price", "close", "value"):
                value = candidate.get(value_key)
                try:
                    return float(value)
                except (TypeError, ValueError):
                    continue

    events = signals.get("events") if isinstance(signals.get("events"), list) else []
    for event in events:
        if not isinstance(event, dict):
            continue
        for value_key in ("price", "close", "value"):
            value = event.get(value_key)
            try:
                return float(value)
            except (TypeError, ValueError):
                continue

    return fallback


def build_price_frame(records: Sequence[Dict[str, Any]]) -> pd.DataFrame:
    """Build candle-like frame expected by ContextBuilder from normalized records."""
    if not records:
        return pd.DataFrame(columns=["t", "o", "h", "l", "c", "v"])

    rows: List[Dict[str, Any]] = []
    last_price = 0.0
    for rec in records:
        t = int(rec.get("t", 0))
        px = _resolve_price(rec, last_price)
        last_price = px
        rows.append(
            {
                "t": t,
                "o": px,
                "h": px,
                "l": px,
                "c": px,
                "v": 1.0,
            }
        )

    return pd.DataFrame(rows)


def _extract_swing_points(records: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    swing_tags = {"hh", "hl", "lh", "ll"}
    swings: List[Dict[str, Any]] = []

    for rec in records:
        t = int(rec.get("t", 0))
        signals = rec.get("signals") if isinstance(rec.get("signals"), dict) else {}
        events = signals.get("events") if isinstance(signals.get("events"), list) else []

        for event in events:
            if not isinstance(event, dict):
                continue
            tag = str(event.get("tag", "")).lower()
            if tag not in swing_tags:
                continue
            price = _resolve_price({"signals": {"events": [event]}}, rec.get("price") or 0.0)
            swings.append({"type": tag.upper(), "price": float(price), "t": t})

    return swings[-10:]


def build_state_adapter(symbol: str, records: Sequence[Dict[str, Any]]) -> PulseStateAdapter:
    last_price = 0.0
    if records:
        last_price = _resolve_price(records[-1], 0.0)

    return PulseStateAdapter(
        symbol=symbol,
        signal_history_normalized=list(records),
        last_candle={"c": float(last_price)},
        swing_points=_extract_swing_points(records),
    )


def load_records_from_file(path: str, limit: int) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as file_handle:
        payload = json.load(file_handle)

    records = extract_log_signal_records(payload)
    if limit > 0:
        records = records[-limit:]

    return records


async def run_prompt_test(
    symbol: str,
    records: Sequence[Dict[str, Any]],
    trigger_events: Sequence[str],
    request_llm: bool,
    llm_base_url: str,
    model: str,
) -> Dict[str, Any]:
    frame = build_price_frame(records)
    state = build_state_adapter(symbol, records)

    builder = ContextBuilder()
    context = builder.build_pulse_context(symbol, frame, state, list(trigger_events))

    result: Dict[str, Any] = {
        "symbol": symbol,
        "record_count": len(records),
        "trigger_events": list(trigger_events),
        "context": context,
    }

    if request_llm:
        brain = AIBrainClient(base_url=llm_base_url)
        if model:
            brain.set_model(model)
        pulse = await brain.generate_pulse(context)
        result["pulse"] = pulse

    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Standalone pulse prompt tester from log_signal_normalize JSON",
    )
    parser.add_argument("--input-json", required=True, help="Path to JSON input file")
    parser.add_argument("--symbol", default="XAUUSD", help="Symbol label for context")
    parser.add_argument(
        "--trigger",
        action="append",
        default=[],
        help="Trigger event (repeatable). Default: PERIODIC_PULSE",
    )
    parser.add_argument("--limit", type=int, default=60, help="Max records to load")
    parser.add_argument("--request-llm", action="store_true", help="Call generate_pulse")
    parser.add_argument(
        "--llm-base-url",
        default=os.getenv("LLM_BASE_URL", "http://localhost:8000/v1"),
        help="LLM base URL for request mode",
    )
    parser.add_argument("--model", default="", help="Override model name")
    parser.add_argument("--output-json", default="", help="Optional output JSON path")
    return parser.parse_args()


async def _main_async() -> int:
    args = parse_args()

    if not os.path.exists(args.input_json):
        raise FileNotFoundError(f"Input JSON not found: {args.input_json}")

    records = load_records_from_file(args.input_json, args.limit)
    if not records:
        raise ValueError("No valid records found in input JSON")

    triggers = args.trigger if args.trigger else ["PERIODIC_PULSE"]
    output = await run_prompt_test(
        symbol=args.symbol,
        records=records,
        trigger_events=triggers,
        request_llm=args.request_llm,
        llm_base_url=args.llm_base_url,
        model=args.model,
    )

    rendered = json.dumps(output, ensure_ascii=False, indent=2)
    if args.output_json:
        with open(args.output_json, "w", encoding="utf-8") as file_handle:
            file_handle.write(rendered)
    else:
        print(rendered)

    return 0


def main() -> int:
    return asyncio.run(_main_async())


if __name__ == "__main__":
    raise SystemExit(main())
