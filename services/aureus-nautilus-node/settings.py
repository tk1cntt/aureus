from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class NautilusNodeSettings:
    symbol_whitelist: List[str]
    candle_stream_pattern: str
    order_stream_pattern: str
    risk_mode: str
    require_sl_tp: bool
    max_position_notional: float
    max_order_notional: float
    poll_interval_ms: int
    max_read_retries: int
    retry_backoff_ms: int

    @staticmethod
    def _parse_csv(value: str) -> List[str]:
        return [item.strip().upper() for item in value.split(",") if item.strip()]

    @classmethod
    def from_env(cls) -> "NautilusNodeSettings":
        symbols = cls._parse_csv(os.getenv("NAUTILUS_SYMBOL_WHITELIST", ""))
        candle_pattern = os.getenv("NAUTILUS_CANDLE_STREAM_PATTERN", "aureus:stream:{symbol}:candle")
        order_pattern = os.getenv("NAUTILUS_ORDER_STREAM_PATTERN", "aureus:stream:{symbol}:orders")
        risk_mode = os.getenv("NAUTILUS_RISK_MODE", "STRICT").strip().upper()
        require_sl_tp = os.getenv("NAUTILUS_REQUIRE_SL_TP", "1").strip().lower() in {"1", "true", "yes"}
        max_position_notional = float(os.getenv("NAUTILUS_MAX_POSITION_NOTIONAL", "100000"))
        max_order_notional = float(os.getenv("NAUTILUS_MAX_ORDER_NOTIONAL", "10000"))
        poll_interval_ms = int(os.getenv("NAUTILUS_POLL_INTERVAL_MS", "100"))
        max_read_retries = int(os.getenv("NAUTILUS_MAX_READ_RETRIES", "3"))
        retry_backoff_ms = int(os.getenv("NAUTILUS_RETRY_BACKOFF_MS", "200"))

        settings = cls(
            symbol_whitelist=symbols,
            candle_stream_pattern=candle_pattern,
            order_stream_pattern=order_pattern,
            risk_mode=risk_mode,
            require_sl_tp=require_sl_tp,
            max_position_notional=max_position_notional,
            max_order_notional=max_order_notional,
            poll_interval_ms=poll_interval_ms,
            max_read_retries=max_read_retries,
            retry_backoff_ms=retry_backoff_ms,
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if not self.symbol_whitelist:
            raise ValueError("NAUTILUS_SYMBOL_WHITELIST must not be empty")

        for symbol in self.symbol_whitelist:
            if not symbol.isalnum() or symbol != symbol.upper():
                raise ValueError(f"Invalid symbol whitelist entry: {symbol}")

        if self.risk_mode != "STRICT":
            raise ValueError("Only STRICT risk mode is allowed for production")

        if self.risk_mode == "STRICT" and not self.require_sl_tp:
            raise ValueError("STRICT mode requires SL/TP enforcement")

        if self.max_position_notional <= 0 or self.max_order_notional <= 0:
            raise ValueError("Notional limits must be positive")

        if self.poll_interval_ms <= 0 or self.max_read_retries < 0 or self.retry_backoff_ms < 0:
            raise ValueError("Polling and retry settings are invalid")
