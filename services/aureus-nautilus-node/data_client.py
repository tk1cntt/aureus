from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass
from typing import Dict, Tuple

try:
    from nautilus_trader.live.data_client import LiveMarketDataClient
    from nautilus_trader.model.data import Bar, BarType
    from nautilus_trader.model.identifiers import InstrumentId
except Exception:  # pragma: no cover
    class _LoggerStub:
        def error(self, *_args, **_kwargs) -> None:
            return None

        def info(self, *_args, **_kwargs) -> None:
            return None

    class LiveMarketDataClient:  # type: ignore[override]
        def __init__(self, *args, **kwargs):
            self.msg_bus = None
            self.log = _LoggerStub()

    @dataclass
    class _SymbolStub:
        value: str

    @dataclass
    class InstrumentId:  # type: ignore[override]
        value: str
        symbol: _SymbolStub

        @classmethod
        def from_str(cls, value: str) -> "InstrumentId":
            symbol = value.split(".", 1)[0]
            return cls(value=value, symbol=_SymbolStub(symbol))

    @dataclass
    class BarType:  # type: ignore[override]
        value: str

        @classmethod
        def from_str(cls, value: str) -> "BarType":
            return cls(value=value)

    @dataclass
    class Bar:  # type: ignore[override]
        bar_type: BarType
        open: float
        high: float
        low: float
        close: float
        volume: float
        ts_event: int
        ts_init: int


class AureusMarketDataClient(LiveMarketDataClient):
    REQUIRED_FIELDS = ("open", "high", "low", "close", "volume", "timestamp")

    def __init__(
        self,
        redis_client,
        stream_name: str,
        instrument_id: str,
        poll_interval_ms: int = 100,
        max_read_retries: int = 3,
        retry_backoff_ms: int = 200,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.redis_client = redis_client
        self.stream_name = stream_name
        self.instrument_id = InstrumentId.from_str(instrument_id)
        self._last_id = "0-0"
        self._running = False
        self._poll_interval = max(1, poll_interval_ms) / 1000.0
        self._max_read_retries = max(0, max_read_retries)
        self._retry_backoff_ms = max(0, retry_backoff_ms)
        self._metrics: Dict[str, int] = {
            "duplicates_total": 0,
            "stream_gap_total": 0,
            "malformed_payload_total": 0,
            "read_error_total": 0,
        }

        if not hasattr(self, "log"):
            self.log = _LoggerStub()
        if not hasattr(self, "msg_bus"):
            self.msg_bus = None

    @property
    def metrics(self) -> Dict[str, int]:
        return dict(self._metrics)

    async def connect(self):
        self._running = True
        asyncio.create_task(self._poll_loop())

    async def disconnect(self):
        self._running = False

    async def _poll_loop(self):
        while self._running:
            await self._poll_market_data_once()
            await asyncio.sleep(self._poll_interval)

    @staticmethod
    def _normalize_message(message: dict) -> Dict[str, str]:
        normalized: Dict[str, str] = {}
        for key, value in message.items():
            key_str = key.decode() if isinstance(key, bytes) else str(key)
            value_str = value.decode() if isinstance(value, bytes) else str(value)
            normalized[key_str] = value_str
        return normalized

    @staticmethod
    def _stream_id_to_tuple(stream_id: str) -> Tuple[int, int]:
        major, minor = stream_id.split("-", 1)
        return int(major), int(minor)

    async def _poll_market_data_once(self):
        streams = {self.stream_name: self._last_id}
        attempt = 0
        while True:
            try:
                result = await self.redis_client.xread(streams, count=100, block=1000)
                break
            except Exception as exc:
                self._metrics["read_error_total"] += 1
                if attempt >= self._max_read_retries:
                    self.log.error(f"Error polling market data after retries: {exc}")
                    return
                attempt += 1
                jitter = random.uniform(0, 0.25) * self._retry_backoff_ms
                await asyncio.sleep((self._retry_backoff_ms + jitter) / 1000.0)

        if not result:
            return

        for _stream, messages in result:
            for idx, message in messages:
                stream_id = idx.decode() if isinstance(idx, bytes) else str(idx)
                if stream_id <= self._last_id:
                    self._metrics["duplicates_total"] += 1
                    continue

                if self._last_id != "0-0":
                    prev_major, prev_minor = self._stream_id_to_tuple(self._last_id)
                    curr_major, curr_minor = self._stream_id_to_tuple(stream_id)
                    if curr_major < prev_major or (curr_major == prev_major and curr_minor > prev_minor + 1):
                        self._metrics["stream_gap_total"] += 1

                self._last_id = stream_id
                self._handle_message(message)

    def _handle_message(self, message: dict):
        normalized = self._normalize_message(message)
        if not all(field in normalized for field in self.REQUIRED_FIELDS):
            self._metrics["malformed_payload_total"] += 1
            self.log.error(f"Malformed bar data (missing fields): {normalized}")
            return

        try:
            open_price = float(normalized["open"])
            high_price = float(normalized["high"])
            low_price = float(normalized["low"])
            close_price = float(normalized["close"])
            volume = float(normalized["volume"])
            ts_ms = int(normalized["timestamp"])

            bar_type = BarType.from_str(f"{self.instrument_id.value}-1-MINUTE-LAST-EXTERNAL")
            bar = Bar(
                bar_type=bar_type,
                open=open_price,
                high=high_price,
                low=low_price,
                close=close_price,
                volume=volume,
                ts_event=ts_ms * 1_000_000,
                ts_init=ts_ms * 1_000_000,
            )
            msg_bus = getattr(self, "msg_bus", None)
            publish = getattr(msg_bus, "publish", None)
            if callable(publish):
                publish(bar)
        except (TypeError, ValueError, KeyError) as exc:
            self._metrics["malformed_payload_total"] += 1
            self.log.error(f"Malformed bar data: {normalized}, error: {exc}")
