from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Dict, List, Tuple

try:
    from nautilus_trader.live.execution_client import LiveExecutionClient
except Exception:  # pragma: no cover - optional dependency in unit test env
    LiveExecutionClient = object


@dataclass(frozen=True)
class ExecutionRiskPolicy:
    symbol_whitelist: List[str]
    require_sl_tp: bool
    max_order_notional: float


class AureusExecutionClient(LiveExecutionClient):
    def __init__(self, redis_client, settings: Any = None, *args, **kwargs):
        if LiveExecutionClient is object:
            super().__init__()
        else:  # pragma: no cover
            super().__init__(*args, **kwargs)

        self.redis_client = redis_client
        self._running = False
        self._last_ids: Dict[str, str] = {}
        self._seen_trace_ids: set[str] = set()
        self._generated_orders: List[Dict[str, Any]] = []
        self.log = logging.getLogger(self.__class__.__name__)

        policy = self._build_policy(settings)
        self._symbol_whitelist = set(policy.symbol_whitelist)
        self._require_sl_tp = policy.require_sl_tp
        self._max_order_notional = policy.max_order_notional

        self.metrics = {
            "accepted_total": 0,
            "rejected_total": 0,
            "duplicate_trace_id_total": 0,
            "missing_sl_tp_total": 0,
            "invalid_symbol_total": 0,
            "invalid_notional_total": 0,
            "trace_completeness_failures_total": 0,
            "missing_backfill_status_total": 0,
            "missing_entry_policy_total": 0,
            "missing_expiry_policy_total": 0,
            "order_open_optional_fallback_total": 0,
        }

    @staticmethod
    def _build_policy(settings: Any) -> ExecutionRiskPolicy:
        if settings is None:
            settings = SimpleNamespace(
                symbol_whitelist=["XAUUSD"],
                require_sl_tp=True,
                max_order_notional=10_000.0,
            )

        return ExecutionRiskPolicy(
            symbol_whitelist=[str(s).upper() for s in getattr(settings, "symbol_whitelist", ["XAUUSD"])],
            require_sl_tp=bool(getattr(settings, "require_sl_tp", True)),
            max_order_notional=float(getattr(settings, "max_order_notional", 10_000.0)),
        )

    async def connect(self):
        self._running = True
        asyncio.create_task(self._poll_loop())

    async def disconnect(self):
        self._running = False

    async def _poll_loop(self):
        self.log.info("AureusExecutionClient started polling orders")
        streams = {"aureus:stream:XAUUSD:orders": self._last_ids.get("aureus:stream:XAUUSD:orders", "0-0")}
        while self._running:
            await self._poll_orders_once(streams)
            await asyncio.sleep(0.1)

    async def _poll_orders_once(self, streams=None):
        if not streams:
            streams = {"aureus:stream:XAUUSD:orders": self._last_ids.get("aureus:stream:XAUUSD:orders", "0-0")}

        try:
            result = await self.redis_client.xread(streams, count=10, block=1000)
            if not result:
                return

            for stream, messages in result:
                stream_str = stream.decode() if isinstance(stream, bytes) else stream
                for idx, message in messages:
                    self._last_ids[stream_str] = idx.decode() if isinstance(idx, bytes) else str(idx)
                    self._handle_message(message)
        except Exception as exc:
            self.log.error(f"Error polling execution data: {exc}")

    def _handle_message(self, message: Dict[Any, Any]):
        msg_type = self._decode_value(message.get(b"type", message.get("type", "")))
        if msg_type != "ORDER_OPEN":
            return

        payload_raw = self._decode_value(message.get(b"data", message.get("data", "{}")))
        try:
            payload = json.loads(payload_raw)
        except Exception:
            self._reject("MALFORMED_PAYLOAD")
            return

        valid, reason, orders = self._validate_and_build_orders(payload)
        if not valid:
            self._reject(reason)
            return

        self.metrics["accepted_total"] += 1
        for order in orders:
            self.generate_order(order)

    def _validate_and_build_orders(self, data: Dict[str, Any]) -> Tuple[bool, str, List[Dict[str, Any]]]:
        trace_id = str(data.get("trace_id", "")).strip()
        symbol = str(data.get("symbol", "")).upper().strip()
        side = str(data.get("side", "")).upper().strip()

        qty_raw = data.get("qty")
        if qty_raw is None:
            qty_raw = data.get("quantity")

        missing_critical_fields: List[str] = []
        if not trace_id:
            missing_critical_fields.append("trace_id")
        if not symbol:
            missing_critical_fields.append("symbol")
        if not side:
            missing_critical_fields.append("side")
        if qty_raw is None or (isinstance(qty_raw, str) and not qty_raw.strip()):
            missing_critical_fields.append("qty")

        if missing_critical_fields:
            return False, "ORDER_OPEN_MISSING_CRITICAL_FIELD", []

        if trace_id in self._seen_trace_ids:
            self.metrics["duplicate_trace_id_total"] += 1
            return False, "DUPLICATE_TRACE_ID", []

        if symbol not in self._symbol_whitelist:
            self.metrics["invalid_symbol_total"] += 1
            return False, "SYMBOL_NOT_ALLOWED", []

        if side not in {"BUY", "SELL"}:
            return False, "INVALID_SIDE", []

        try:
            qty = float(qty_raw)
        except Exception:
            return False, "INVALID_QTY", []

        if qty <= 0:
            return False, "INVALID_QTY", []

        notional_raw = data.get("notional", qty)
        notional_value = qty if notional_raw is None else notional_raw
        try:
            notional = float(notional_value)
        except Exception:
            return False, "INVALID_NOTIONAL", []

        if notional > self._max_order_notional:
            self.metrics["invalid_notional_total"] += 1
            return False, "MAX_NOTIONAL_EXCEEDED", []

        if self._require_sl_tp and ("sl" not in data or "tp" not in data):
            self.metrics["missing_sl_tp_total"] += 1
            return False, "ORDER_OPEN_SLTP_REQUIRED_MISSING", []

        entry_policy = str(data.get("entry_policy", "")).strip()
        if not entry_policy:
            entry_policy = "IMMEDIATE"
            self.metrics["missing_entry_policy_total"] += 1
            self.metrics["trace_completeness_failures_total"] += 1
            self.metrics["order_open_optional_fallback_total"] += 1

        expiry_policy = str(data.get("expiry_policy", "")).strip()
        if not expiry_policy:
            expiry_policy = "GTC"
            self.metrics["missing_expiry_policy_total"] += 1
            self.metrics["trace_completeness_failures_total"] += 1
            self.metrics["order_open_optional_fallback_total"] += 1

        backfill_status = str(data.get("backfill_status", "")).upper().strip()
        if not backfill_status:
            backfill_status = "UNKNOWN"
            self.metrics["missing_backfill_status_total"] += 1
            self.metrics["trace_completeness_failures_total"] += 1
            self.metrics["order_open_optional_fallback_total"] += 1

        sl = data.get("sl")
        tp = data.get("tp")
        if sl is not None:
            sl = float(sl)
        if tp is not None:
            tp = float(tp)

        orders: List[Dict[str, Any]] = [
            {
                "kind": "ENTRY",
                "trace_id": trace_id,
                "instrument_id": f"{symbol}.AUREUS_VIRTUAL",
                "side": side,
                "qty": qty,
                "entry_policy": entry_policy,
                "expiry_policy": expiry_policy,
                "backfill_status": backfill_status,
            }
        ]

        if sl is not None:
            orders.append({"kind": "STOP_LOSS", "trace_id": trace_id, "price": sl, "side": "SELL" if side == "BUY" else "BUY"})
        if tp is not None:
            orders.append({"kind": "TAKE_PROFIT", "trace_id": trace_id, "price": tp, "side": "SELL" if side == "BUY" else "BUY"})

        self._seen_trace_ids.add(trace_id)
        return True, "", orders

    @staticmethod
    def _decode_value(value: Any) -> str:
        if isinstance(value, bytes):
            return value.decode()
        return str(value)

    def _reject(self, reason: str) -> None:
        self.metrics["rejected_total"] += 1
        self.log.warning(f"Rejected execution intent: {reason}")

    def generate_order(self, order: Dict[str, Any]) -> None:  # pragma: no cover - adapter method
        base_generate = getattr(super(), "generate_order", None)
        if callable(base_generate):
            base_generate(order)
            return
        self._generated_orders.append(order)
