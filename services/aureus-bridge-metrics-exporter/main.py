import json
import logging
import os
import time
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

import redis
from prometheus_client import Counter, Gauge, start_http_server


logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("aureus-bridge-metrics-exporter")

REDIS_HOST = os.getenv("REDIS_HOST", "redis-dev")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
EXPORTER_PORT = int(os.getenv("EXPORTER_PORT", "9108"))
POLL_INTERVAL_SECONDS = float(os.getenv("POLL_INTERVAL_SECONDS", "2"))
SYMBOLS = [symbol.strip() for symbol in os.getenv("SYMBOLS", "XAUUSD").split(",") if symbol.strip()]

ORDERS_TOTAL = Counter(
    "aureus_bridge_orders_total",
    "Total number of order stream events observed by symbol",
    ["symbol"],
)
EXECUTIONS_TOTAL = Counter(
    "aureus_bridge_executions_total",
    "Total number of execution stream events observed by symbol",
    ["symbol"],
)
ERRORS_TOTAL = Counter(
    "aureus_bridge_errors_total",
    "Total processing errors in bridge metrics exporter",
)
BACKLOG_MESSAGES = Gauge(
    "aureus_bridge_backlog_messages",
    "Backlog estimate: order stream length minus execution stream length",
    ["symbol"],
)
LATENCY_MS = Gauge(
    "aureus_bridge_latency_ms",
    "Latest matched order->execution latency in milliseconds",
    ["symbol"],
)
ORDERS_MISSING_SL_TOTAL = Counter(
    "aureus_bridge_orders_missing_sl_total",
    "Total number of orders missing a Stop Loss",
    ["symbol"],
)
ORDERS_MISSING_TP_TOTAL = Counter(
    "aureus_bridge_orders_missing_tp_total",
    "Total number of orders missing a Take Profit",
    ["symbol"],
)
UNREALIZED_PNL = Gauge(
    "aureus_bridge_unrealized_pnl",
    "Latest unrealized PnL from position snapshots",
    ["symbol"],
)
REALIZED_PNL = Gauge(
    "aureus_bridge_realized_pnl",
    "Latest realized PnL from position snapshots",
    ["symbol"],
)
DUPLICATE_TRACE_ID_TOTAL = Counter(
    "aureus_bridge_duplicate_trace_id_total",
    "Total number of duplicate trace IDs observed in order stream events",
    ["symbol"],
)


def _parse_stream_id_ms(stream_id: str) -> Optional[int]:
    try:
        return int(str(stream_id).split("-")[0])
    except Exception:
        return None


def _decode_trace_id(fields: Dict[str, str]) -> Optional[str]:
    raw_data = fields.get("data")
    if not raw_data:
        return None
    try:
        data = json.loads(raw_data)
    except Exception:
        return None
    trace_id = data.get("trace_id")
    return str(trace_id) if trace_id else None


def _get_last_id(client: redis.Redis, stream_name: str) -> str:
    entries = client.xrevrange(stream_name, count=1)
    return entries[0][0] if entries else "0-0"


def _read_new_entries(client: redis.Redis, stream_name: str, last_id: str) -> Tuple[List[Tuple[str, Dict[str, str]]], str]:
    response = client.xread({stream_name: last_id}, count=500, block=1)
    if not response:
        return [], last_id

    entries = response[0][1]
    if not entries:
        return [], last_id

    new_last_id = entries[-1][0]
    return entries, new_last_id


def _update_symbol_metrics(
    client: redis.Redis,
    symbol: str,
    last_order_id: str,
    last_execution_id: str,
    order_stream_ids_by_trace: Dict[str, Dict[str, int]],
    seen_trace_ids_by_symbol: Dict[str, set[str]],
) -> Tuple[str, str]:
    order_stream = f"aureus:stream:{symbol}:orders"
    execution_stream = f"aureus:stream:{symbol}:execution"
    position_stream = f"aureus:stream:{symbol}:positions"

    order_entries, next_order_id = _read_new_entries(client, order_stream, last_order_id)
    if order_entries:
        ORDERS_TOTAL.labels(symbol=symbol).inc(len(order_entries))
        for entry_id, fields in order_entries:
            trace_id = _decode_trace_id(fields)
            entry_ts_ms = _parse_stream_id_ms(entry_id)
            if trace_id:
                if trace_id in seen_trace_ids_by_symbol[symbol]:
                    DUPLICATE_TRACE_ID_TOTAL.labels(symbol=symbol).inc()
                else:
                    seen_trace_ids_by_symbol[symbol].add(trace_id)
                if entry_ts_ms is not None:
                    order_stream_ids_by_trace[symbol][trace_id] = entry_ts_ms

            # Check for missing SL/TP
            raw_data = fields.get("data", "")
            if raw_data:
                try:
                    data = json.loads(raw_data)
                    if data.get("type") == "ORDER_OPEN":
                        if not data.get("sl"):
                            ORDERS_MISSING_SL_TOTAL.labels(symbol=symbol).inc()
                        if not data.get("tp"):
                            ORDERS_MISSING_TP_TOTAL.labels(symbol=symbol).inc()
                except Exception:
                    pass

    execution_entries, next_execution_id = _read_new_entries(client, execution_stream, last_execution_id)
    if execution_entries:
        EXECUTIONS_TOTAL.labels(symbol=symbol).inc(len(execution_entries))
        for entry_id, fields in execution_entries:
            trace_id = _decode_trace_id(fields)
            execution_ts_ms = _parse_stream_id_ms(entry_id)
            if not trace_id or execution_ts_ms is None:
                continue

            order_ts_ms = order_stream_ids_by_trace[symbol].pop(trace_id, None)
            if order_ts_ms is None:
                continue

            latency = max(execution_ts_ms - order_ts_ms, 0)
            LATENCY_MS.labels(symbol=symbol).set(latency)

    orders_len = client.xlen(order_stream)
    executions_len = client.xlen(execution_stream)
    BACKLOG_MESSAGES.labels(symbol=symbol).set(max(orders_len - executions_len, 0))

    # Read latest position snapshot for PnL
    position_entries = client.xrevrange(position_stream, count=1)
    if position_entries:
        try:
            fields = position_entries[0][1]
            raw_data = fields.get("data", "")
            if raw_data:
                data = json.loads(raw_data)
                upnl = data.get("unrealized_pnl")
                rpnl = data.get("realized_pnl")
                if upnl is not None:
                    UNREALIZED_PNL.labels(symbol=symbol).set(float(upnl))
                if rpnl is not None:
                    REALIZED_PNL.labels(symbol=symbol).set(float(rpnl))
        except Exception as e:
            logger.debug(f"Failed to parse position for PnL: {e}")

    return next_order_id, next_execution_id


def run() -> None:
    logger.info("Starting Aureus bridge metrics exporter on :%s for symbols=%s", EXPORTER_PORT, SYMBOLS)
    start_http_server(EXPORTER_PORT)

    client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    while True:
        try:
            client.ping()
            break
        except Exception as exc:
            logger.warning("Waiting for Redis %s:%s (%s)", REDIS_HOST, REDIS_PORT, exc)
            time.sleep(2)

    last_order_ids = {symbol: _get_last_id(client, f"aureus:stream:{symbol}:orders") for symbol in SYMBOLS}
    last_execution_ids = {symbol: _get_last_id(client, f"aureus:stream:{symbol}:execution") for symbol in SYMBOLS}
    order_stream_ids_by_trace: Dict[str, Dict[str, int]] = defaultdict(dict)
    seen_trace_ids_by_symbol: Dict[str, set[str]] = defaultdict(set)

    while True:
        for symbol in SYMBOLS:
            try:
                next_order_id, next_execution_id = _update_symbol_metrics(
                    client=client,
                    symbol=symbol,
                    last_order_id=last_order_ids[symbol],
                    last_execution_id=last_execution_ids[symbol],
                    order_stream_ids_by_trace=order_stream_ids_by_trace,
                    seen_trace_ids_by_symbol=seen_trace_ids_by_symbol,
                )
                last_order_ids[symbol] = next_order_id
                last_execution_ids[symbol] = next_execution_id
            except Exception as exc:
                ERRORS_TOTAL.inc()
                logger.exception("Failed metrics update for %s: %s", symbol, exc)
        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    run()
