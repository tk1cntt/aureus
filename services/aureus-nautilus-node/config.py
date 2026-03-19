from __future__ import annotations

from typing import Any

from settings import NautilusNodeSettings

try:
    from nautilus_trader.config import TradingNodeConfig
except Exception:  # pragma: no cover
    TradingNodeConfig = None


def get_settings() -> NautilusNodeSettings:
    return NautilusNodeSettings.from_env()


def get_node_config() -> Any:
    settings = get_settings()

    if TradingNodeConfig is None:
        return {
            "symbol_whitelist": settings.symbol_whitelist,
            "risk_mode": settings.risk_mode,
            "poll_interval_ms": settings.poll_interval_ms,
        }

    return TradingNodeConfig()
