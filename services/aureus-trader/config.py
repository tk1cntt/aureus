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
    max_in_flight_orders: int | None = None
    strategy_lane_capacity: int = 8
    scheduler_poll_interval: float = 0.1
    dedup_ttl: int = 86400
    # Database config for trade journal
    db_host: str = "aureus-db"
    db_port: int = 5432
    db_name: str = "aureus"
    db_user: str = "aureus"
    db_password: str = "aureus"

    def __post_init__(self):
        if self.symbols is None:
            self.symbols = ["XAUUSD", "BTCUSD", "ETHUSD", "USTEC",
                            "USDJPY", "EURUSD", "GBPUSD", "AUDUSD"]
        if self.max_in_flight_orders is None:
            self.max_in_flight_orders = len(self.symbols) * self.strategy_lane_capacity


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
        max_in_flight_orders=(
            int(os.environ["MAX_IN_FLIGHT_ORDERS"])
            if os.environ.get("MAX_IN_FLIGHT_ORDERS")
            else None
        ),
        strategy_lane_capacity=int(os.environ.get("STRATEGY_LANE_CAPACITY", "8")),
        scheduler_poll_interval=float(os.environ.get("SCHEDULER_POLL_INTERVAL", "0.1")),
        dedup_ttl=int(os.environ.get("DEDUP_TTL", "86400")),
        db_host=os.environ.get("DB_HOST", "aureus-db"),
        db_port=int(os.environ.get("DB_PORT", "5432")),
        db_name=os.environ.get("DB_NAME", "aureus"),
        db_user=os.environ.get("DB_USER", "aureus"),
        db_password=os.environ.get("DB_PASSWORD", "aureus"),
    )


# Redis key constants
ORDER_QUEUE_KEY = "aureus:trader:order_queue"
DEDUP_KEY_PREFIX = "aureus:trader:dedup:"
COMMANDS_CHANNEL = "aureus:mt5:commands"
EVENTS_CHANNEL = "aureus:mt5:events"
SIGNALS_CHANNEL_PREFIX = "aureus:signals:"
