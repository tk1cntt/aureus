"""
Configuration loader for aureus-notifier.

Loads filter and route configuration from Redis, provides
filtering and routing functions, and supports runtime config
updates via pub/sub.
"""
import json
import logging
from dataclasses import dataclass, field
from typing import Callable, Optional

import redis.asyncio as redis

logger = logging.getLogger(__name__)

REDIS_FILTER_KEY = "aureus:notifier:filters"
REDIS_ROUTE_KEY = "aureus:notifier:routes"
REDIS_CONFIG_CHANNEL = "aureus:cmd:notifier_config"


@dataclass
class FilterConfig:
    """Filter configuration for event processing."""
    enabled: bool = True
    signal_types: set = field(default_factory=lambda: {"SIGNAL_EVENT", "STRATEGY_MATCH"})
    symbols: set = field(default_factory=set)
    strategies: set = field(default_factory=set)
    min_confidence: Optional[float] = None


@dataclass
class Route:
    """Route configuration for message dispatch."""
    chat_id: str
    event_types: Optional[list] = None    # null/empty = wildcard
    symbols: Optional[list] = None
    strategies: Optional[list] = None


async def load_filters(r: redis.Redis) -> FilterConfig:
    """Load filter configuration from Redis hash.

    Reads aureus:notifier:filters and returns FilterConfig.
    Returns defaults if hash is empty.
    """
    data = await r.hgetall(REDIS_FILTER_KEY)

    if not data:
        return FilterConfig()

    # Parse enabled
    enabled_str = data.get("enabled", "true").lower()
    enabled = enabled_str == "true"

    # Parse signal_types
    signal_types_str = data.get("signal_types", "")
    signal_types = set(
        s.strip() for s in signal_types_str.split(",") if s.strip()
    ) if signal_types_str else {"SIGNAL_EVENT", "STRATEGY_MATCH"}

    # Parse symbols
    symbols_str = data.get("symbols", "")
    symbols = set(
        s.strip() for s in symbols_str.split(",") if s.strip()
    ) if symbols_str else set()

    # Parse strategies
    strategies_str = data.get("strategies", "")
    strategies = set(
        s.strip() for s in strategies_str.split(",") if s.strip()
    ) if strategies_str else set()

    # Parse min_confidence
    min_conf_str = data.get("min_confidence", "")
    min_confidence = float(min_conf_str) if min_conf_str else None

    return FilterConfig(
        enabled=enabled,
        signal_types=signal_types,
        symbols=symbols,
        strategies=strategies,
        min_confidence=min_confidence,
    )


async def load_routes(r: redis.Redis) -> list[Route]:
    """Load route configuration from Redis hash.

    Reads aureus:notifier:routes key "routes" (JSON array)
    and returns list of Route objects.
    Returns empty list if key is missing.
    """
    routes_json = await r.hget(REDIS_ROUTE_KEY, "routes")

    if not routes_json:
        return []

    try:
        routes_data = json.loads(routes_json)
        return [
            Route(
                chat_id=r.get("chat_id", ""),
                event_types=r.get("event_types"),
                symbols=r.get("symbols"),
                strategies=r.get("strategies"),
            )
            for r in routes_data
        ]
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning(f"Failed to parse routes config: {e}")
        return []


def passes_filter(config: FilterConfig, event: dict) -> bool:
    """Check if an event passes all filter criteria.

    Returns True if event should be processed, False if filtered out.
    """
    # Check enabled
    if not config.enabled:
        return False

    event_type = event.get("type", "")
    event_symbol = event.get("symbol", "")

    # Check signal_types
    if config.signal_types and event_type not in config.signal_types:
        return False

    # Check symbols (empty set = all symbols allowed)
    if config.symbols and event_symbol not in config.symbols:
        return False

    # Check strategies (only for STRATEGY_MATCH events)
    if config.strategies and event_type == "STRATEGY_MATCH":
        event_strategy = event.get("data", {}).get("strategy", "")
        if event_strategy not in config.strategies:
            return False

    return True


def match_routes(event: dict, routes: list[Route]) -> list[str]:
    """Find matching routes for an event.

    Returns list of chat_ids whose route criteria match the event.
    null/empty criteria in a route = wildcard (matches any value).
    """
    event_type = event.get("type", "")
    event_symbol = event.get("symbol", "")
    event_strategy = event.get("data", {}).get("strategy") if event_type == "STRATEGY_MATCH" else None

    matching_chat_ids = []

    for route in routes:
        # Check event_type match (null/empty = all)
        if route.event_types and event_type not in route.event_types:
            continue

        # Check symbol match (null/empty = all)
        if route.symbols and event_symbol not in route.symbols:
            continue

        # Check strategy match (null/empty = all)
        if route.strategies:
            if event_strategy is None or event_strategy not in route.strategies:
                continue

        matching_chat_ids.append(route.chat_id)

    return matching_chat_ids


async def subscribe_config_updates(r: redis.Redis, callback: Callable):
    """Subscribe to config update channel and call callback on message.

    Listens to aureus:cmd:notifier_config pub/sub channel.
    When any message is received, awaits callback() to reload config.
    Pattern matches aureus-gateway main.py lines 282-318.
    """
    pubsub = r.pubsub()
    await pubsub.subscribe(REDIS_CONFIG_CHANNEL)
    logger.info(f"Subscribed to config updates on {REDIS_CONFIG_CHANNEL}")

    async for message in pubsub.listen():
        if message["type"] != "message":
            continue
        logger.info(f"Config update message received on {REDIS_CONFIG_CHANNEL}")
        await callback()
