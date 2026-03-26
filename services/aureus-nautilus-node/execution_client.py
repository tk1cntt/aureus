from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple

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
            "backfill_violation_total": 0,
            "validator_state_error_total": 0,
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
        self.log.info(
            "[EXEC_CLIENT][CONNECT] Starting poll loop stream_pattern=%s policy_whitelist=%s require_sl_tp=%s max_notional=%.2f",
            "aureus:stream:*:orders",
            sorted(self._symbol_whitelist),
            self._require_sl_tp,
            self._max_order_notional,
        )
        asyncio.create_task(self._poll_loop())

    async def disconnect(self):
        self._running = False
        self.log.info("[EXEC_CLIENT][DISCONNECT] Poll loop stop requested metrics=%s", self.metrics)

    async def _poll_loop(self):
        self.log.info("[EXEC_CLIENT][POLL_LOOP] Started stream_pattern=aureus:stream:*:orders")
        while self._running:
            streams = await self._discover_order_streams()
            await self._poll_orders_once(streams)
            await asyncio.sleep(0.1)
        self.log.info("[EXEC_CLIENT][POLL_LOOP] Exited stream_pattern=aureus:stream:*:orders")

    async def _discover_order_streams(self) -> Dict[str, str]:
        discovered = {
            f"aureus:stream:{symbol}:orders"
            for symbol in sorted(self._symbol_whitelist)
            if symbol
        }

        scan = getattr(self.redis_client, "scan", None)
        if callable(scan):
            cursor: Any = 0
            try:
                while True:
                    cursor, keys = await scan(cursor=cursor, match="aureus:stream:*:orders", count=200)
                    for key in keys or []:
                        key_str = key.decode() if isinstance(key, bytes) else str(key)
                        if key_str:
                            discovered.add(key_str)

                    cursor_value = cursor.decode() if isinstance(cursor, bytes) else str(cursor)
                    if cursor_value == "0":
                        break
            except Exception as exc:
                self.log.debug("[EXEC_CLIENT][DISCOVERY] Stream scan failed, using default streams: %s", exc)

        if not discovered:
            discovered.add("aureus:stream:XAUUSD:orders")

        return {stream: self._last_ids.get(stream, "0-0") for stream in sorted(discovered)}

    async def _poll_orders_once(self, streams=None):
        if not streams:
            streams = await self._discover_order_streams()

        try:
            result = await self.redis_client.xread(streams, count=10, block=1000)
            if not result:
                return

            for stream, messages in result:
                stream_str = stream.decode() if isinstance(stream, bytes) else stream
                self.log.info(
                    "[EXEC_CLIENT][POLL] Received batch stream=%s message_count=%d last_id_before=%s",
                    stream_str,
                    len(messages),
                    self._last_ids.get(stream_str, "0-0"),
                )
                for idx, message in messages:
                    message_id = idx.decode() if isinstance(idx, bytes) else str(idx)
                    self._last_ids[stream_str] = message_id
                    self._handle_message(message, stream_str=stream_str, message_id=message_id)
        except Exception as exc:
            self.log.exception("[EXEC_CLIENT][POLL][ERROR] Error polling execution data: %s", exc)

    @staticmethod
    def _extract_stream_symbol(stream_str: str) -> str:
        parts = str(stream_str).split(":")
        if len(parts) < 4:
            return ""
        # aureus:stream:{symbol}:orders
        return parts[2].upper().strip()

    def _handle_message(
        self,
        message: Dict[Any, Any],
        *,
        stream_str: str = "<unknown>",
        message_id: str = "<unknown>",
    ):
        msg_type = self._decode_value(message.get(b"type", message.get("type", "")))
        if msg_type != "ORDER_OPEN":
            self.log.debug(
                "[EXEC_CLIENT][HANDLE] Ignored message stream=%s message_id=%s type=%s",
                stream_str,
                message_id,
                msg_type,
            )
            return

        payload_raw = self._decode_value(message.get(b"data", message.get("data", "{}")))
        try:
            payload = json.loads(payload_raw)
        except Exception:
            self._reject("MALFORMED_PAYLOAD", stream_str=stream_str, message_id=message_id)
            return

        trace_id = str(payload.get("trace_id", "")).strip() or "<missing>"
        symbol = str(payload.get("symbol", "")).upper().strip() or "<missing>"
        stream_symbol = self._extract_stream_symbol(stream_str)
        self.log.info(
            "[EXEC_CLIENT][HANDLE] Processing ORDER_OPEN stream=%s message_id=%s trace_id=%s symbol=%s stream_symbol=%s",
            stream_str,
            message_id,
            trace_id,
            symbol,
            stream_symbol or "<unknown>",
        )

        valid, reason, orders, fallback_applied = self._validate_and_build_orders(payload, stream_symbol=stream_symbol)
        if not valid:
            self._reject(
                reason,
                trace_id=trace_id,
                symbol=symbol,
                stream_str=stream_str,
                message_id=message_id,
            )
            return

        self.metrics["accepted_total"] += 1
        self.log.info(
            "[EXEC_CLIENT][HANDLE] Accepted ORDER_OPEN trace_id=%s symbol=%s generated_orders=%d fallback_applied=%s consumer_owner=%s",
            trace_id,
            symbol,
            len(orders),
            fallback_applied,
            "AureusExecutionClient",
        )
        for order in orders:
            self.generate_order(order)

    def _validate_and_build_orders(
        self,
        data: Dict[str, Any],
        *,
        stream_symbol: str = "",
    ) -> Tuple[bool, str, List[Dict[str, Any]], List[str]]:
        trace_id = str(data.get("trace_id", "")).strip()
        symbol = str(data.get("symbol", "")).upper().strip()
        side = str(data.get("side", "")).upper().strip()

        missing_critical_fields: List[str] = []
        for field in ("trace_id", "symbol", "side", "qty"):
            value = data.get(field)
            if value is None:
                missing_critical_fields.append(field)
                continue
            if isinstance(value, str) and not value.strip():
                missing_critical_fields.append(field)

        if missing_critical_fields:
            return False, "ORDER_OPEN_MISSING_CRITICAL_FIELD", [], []

        if trace_id in self._seen_trace_ids:
            self.metrics["duplicate_trace_id_total"] += 1
            return False, "DUPLICATE_TRACE_ID", [], []

        if stream_symbol and symbol != stream_symbol:
            self.metrics.setdefault("order_open_reject_symbol_mismatch_total", 0)
            self.metrics["order_open_reject_symbol_mismatch_total"] += 1
            return False, "SYMBOL_STREAM_MISMATCH", [], []

        if symbol not in self._symbol_whitelist:
            self.metrics["invalid_symbol_total"] += 1
            return False, "SYMBOL_NOT_ALLOWED", [], []

        if side not in {"BUY", "SELL"}:
            return False, "INVALID_SIDE", [], []

        qty_raw = data.get("qty")
        try:
            qty = float(qty_raw)
        except Exception:
            return False, "INVALID_QTY", [], []

        if qty <= 0:
            return False, "INVALID_QTY", [], []

        notional_raw = data.get("notional", qty)
        notional_value = qty if notional_raw is None else notional_raw
        try:
            notional = float(notional_value)
        except Exception:
            return False, "INVALID_NOTIONAL", [], []

        if notional > self._max_order_notional:
            self.metrics["invalid_notional_total"] += 1
            return False, "MAX_NOTIONAL_EXCEEDED", [], []

        if self._require_sl_tp and ("sl" not in data or "tp" not in data):
            self.metrics["missing_sl_tp_total"] += 1
            return False, "ORDER_OPEN_SLTP_REQUIRED_MISSING", [], []

        fallback_applied: List[str] = []

        entry_policy = str(data.get("entry_policy", "")).strip()
        if not entry_policy:
            entry_policy = "IMMEDIATE"
            fallback_applied.append("entry_policy")
            self.metrics["missing_entry_policy_total"] += 1
            self.metrics["trace_completeness_failures_total"] += 1

        expiry_policy = str(data.get("expiry_policy", "")).strip()
        if not expiry_policy:
            expiry_policy = "GTC"
            fallback_applied.append("expiry_policy")
            self.metrics["missing_expiry_policy_total"] += 1
            self.metrics["trace_completeness_failures_total"] += 1

        backfill_status = str(data.get("backfill_status", "")).upper().strip()
        if not backfill_status:
            backfill_status = "UNKNOWN"
            fallback_applied.append("backfill_status")
            self.metrics["missing_backfill_status_total"] += 1
            self.metrics["trace_completeness_failures_total"] += 1
        elif backfill_status != "READY":
            self.metrics["backfill_violation_total"] += 1
            return False, "BACKFILL_NOT_READY", [], []

        if fallback_applied:
            self.metrics.setdefault("order_open_optional_fallback_total", 0)
            self.metrics["order_open_optional_fallback_total"] += len(fallback_applied)

        transition_allowed = data.get("transition_allowed")
        validator_passed = data.get("validator_passed")
        validator_failures = data.get("validator_failures")
        validator_failures_list = validator_failures if isinstance(validator_failures, list) else []

        transition_blocked = transition_allowed is False
        validator_blocked = validator_passed is False or len(validator_failures_list) > 0
        if transition_blocked or validator_blocked:
            self.metrics["validator_state_error_total"] += 1
            return False, "VALIDATOR_STATE_BLOCKED", [], []

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
        return True, "", orders, fallback_applied

    @staticmethod
    def _decode_value(value: Any) -> str:
        if isinstance(value, bytes):
            return value.decode(errors="replace")
        return str(value)

    def _reject(
        self,
        reason: str,
        *,
        trace_id: str = "",
        symbol: str = "",
        stream_str: str = "",
        message_id: str = "",
    ) -> None:
        self.metrics["rejected_total"] += 1
        self.log.warning(
            "[EXEC_CLIENT][REJECT] reason=%s trace_id=%s symbol=%s stream=%s message_id=%s metrics=%s",
            reason,
            trace_id or "<missing>",
            symbol or "<missing>",
            stream_str or "<unknown>",
            message_id or "<unknown>",
            self.metrics,
        )

    def generate_order(self, order: Dict[str, Any]) -> None:  # pragma: no cover - adapter method
        self.log.info(
            "[EXEC_CLIENT][GENERATE_ORDER] kind=%s trace_id=%s instrument_id=%s side=%s qty=%s",
            order.get("kind"),
            order.get("trace_id"),
            order.get("instrument_id", ""),
            order.get("side"),
            order.get("qty", ""),
        )
        base_generate = getattr(super(), "generate_order", None)
        if callable(base_generate):
            base_generate(order)
            return
        self._generated_orders.append(order)
