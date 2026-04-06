"""
Configuration for aureus-trader service.

Loads environment variables and provides Redis key constants
for the order execution pipeline.
"""
import os
from dataclasses import dataclass


@dataclass
class TraderConfig:
    """Configuration for the aureus-trader service."""
    redis_host: str = "redis-dev"
    redis_port: int = 6379
    symbols: list[str] = None
    log_level: str = "INFO"
    max_queue_size: int = 100
    ack_timeout: float = 5.0
    result_timeout: float = 30.0
    max_retries: int = 3
    dedup_ttl: int = 86400

    def __post_init__(self):
        if self.symbols is None:
            self.symbols = ["XAUUSD", "BTCUSD", "ETHUSD", "USTEC",
                            "USDJPY", "EURUSD", "GBPUSD", "AUDUSD"]


def load_config() -> TraderConfig:
    """Read environment variables and return a TraderConfig instance."""
    symbols_raw = os.environ.get(
        "SYMBOLS", "XAUUSD,BTCUSD,ETHUSD,USTEC,USDJPY,EURUSD,GBPUSD,AUDUSD"
    )
    symbols = [s.strip() for s in symbols_raw.split(",") if s.strip()]

    return TraderConfig(
        redis_host=os.environ.get("REDIS_HOST", "redis-dev"),
        redis_port=int(os.environ.get("REDIS_PORT", "6379")),
        symbols=symbols,
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
        max_queue_size=int(os.environ.get("MAX_QUEUE_SIZE", "100")),
        ack_timeout=float(os.environ.get("ACK_TIMEOUT", "5.0")),
        result_timeout=float(os.environ.get("RESULT_TIMEOUT", "30.0")),
        max_retries=int(os.environ.get("MAX_RETRIES", "3")),
        dedup_ttl=int(os.environ.get("DEDUP_TTL", "86400")),
    )


# Redis key constants
ORDER_QUEUE_KEY = "aureus:trader:order_queue"
DEDUP_KEY_PREFIX = "aureus:trader:dedup:"
COMMANDS_CHANNEL = "aureus:mt5:commands"
EVENTS_CHANNEL = "aureus:mt5:events"
SIGNALS_CHANNEL_PREFIX = "aureus:signals:"
