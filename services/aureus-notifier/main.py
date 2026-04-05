"""
Main entry point for aureus-notifier service.

Subscribes to Redis pub/sub channels for signal events,
filters them, and dispatches formatted Telegram notifications.
"""
import asyncio
import json
import os
import logging
from datetime import datetime, timezone

import redis.asyncio as redis

from config import load_filters, load_routes, subscribe_config_updates, passes_filter, FilterConfig, Route
from telegram_bot import TelegramSender
from rate_limiter import RateLimitedDispatcher

logging.basicConfig(
    level=getattr(logging, os.environ.get("LOG_LEVEL", "INFO")),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


async def run_notifier():
    # 1. Initialize Redis connection
    redis_host = os.environ.get("REDIS_HOST", "redis-dev")
    redis_port = int(os.environ.get("REDIS_PORT", 6379))
    logger.info(f"Connecting to Redis at {redis_host}:{redis_port}")
    r = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
    await r.ping()
    logger.info("Redis connected")

    # 2. Initialize Telegram sender
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        logger.error("TELEGRAM_BOT_TOKEN not set. Please configure Telegram bot token in .env file.")
        logger.error("Service will exit. See .env.example for configuration instructions.")
        import sys
        sys.exit(1)
    sender = TelegramSender(bot_token)

    # 3. Load initial config
    filters: FilterConfig = await load_filters(r)
    routes: list[Route] = await load_routes(r)
    
    # If no routes configured, create default route from env var
    if not routes:
        default_chat_id = os.environ.get("TELEGRAM_DEFAULT_CHAT_ID")
        if default_chat_id:
            routes = [Route(chat_id=default_chat_id)]
            logger.info(f"Created default route for chat: {default_chat_id}")
        else:
            logger.warning("TELEGRAM_DEFAULT_CHAT_ID not set and no routes configured")
    
    logger.info(f"Loaded filters: enabled={filters.enabled}, signal_types={filters.signal_types}")
    logger.info(f"Loaded routes: {len(routes)} routes")

    # 4. Initialize dispatcher
    dispatcher = RateLimitedDispatcher(sender)

    # 6. Start dispatcher loop
    dispatch_task = asyncio.create_task(dispatcher.dispatch_loop())

    # 7. Subscribe to signal channels for all configured symbols
    symbols_str = os.environ.get("SYMBOLS", "XAUUSD,BTCUSD,ETHUSD,USTEC,USDJPY,EURUSD,GBPUSD,AUDUSD")
    symbols = [s.strip() for s in symbols_str.split(",") if s.strip()]
    channels = [f"aureus:signals:{sym}" for sym in symbols]

    pubsub = r.pubsub()
    await pubsub.subscribe(*channels)
    logger.info(f"Subscribed to channels: {channels}")

    # 8. Send greeting message on startup
    default_chat_id = os.environ.get("TELEGRAM_DEFAULT_CHAT_ID")
    if default_chat_id:
        greeting = (
            f"🤖 <b>Aureus Notifier Online</b>\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"Service started: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
            f"Symbols: {len(symbols)}\n"
            f"Filters: enabled={filters.enabled}\n"
            f"Routes: {len(routes)} configured\n"
            f"\n"
            f"Ready to send notifications! 🚀"
        )
        try:
            success = await sender.send_message(default_chat_id, greeting)
            if success:
                logger.info("Greeting message sent successfully")
            else:
                logger.warning("Failed to send greeting message")
        except Exception as e:
            logger.warning(f"Failed to send greeting: {e}")

    async def reload_config():
        nonlocal filters, routes
        filters = await load_filters(r)
        routes = await load_routes(r)
        logger.info(f"Config reloaded: enabled={filters.enabled}, routes={len(routes)}")

    # 5. Subscribe to config updates
    config_task = asyncio.create_task(subscribe_config_updates(r, reload_config))

    # 6. Start dispatcher loop
    dispatch_task = asyncio.create_task(dispatcher.dispatch_loop())

    # 7. Subscribe to signal channels for all configured symbols
    symbols_str = os.environ.get("SYMBOLS", "XAUUSD,BTCUSD,ETHUSD,USTEC,USDJPY,EURUSD,GBPUSD,AUDUSD")
    symbols = [s.strip() for s in symbols_str.split(",") if s.strip()]
    channels = [f"aureus:signals:{sym}" for sym in symbols]

    pubsub = r.pubsub()
    await pubsub.subscribe(*channels)
    logger.info(f"Subscribed to channels: {channels}")

    # 8. Process incoming events
    async for message in pubsub.listen():
        if message["type"] != "message":
            continue

        try:
            event = json.loads(message["data"])
            event_type = event.get("type", "UNKNOWN")
            event_symbol = event.get("symbol", "UNKNOWN")

            # Apply filter
            if not passes_filter(filters, event):
                logger.debug(f"Event filtered out: type={event_type} symbol={event_symbol}")
                continue

            # Enqueue for dispatch
            enqueued = await dispatcher.enqueue(event, routes)
            logger.debug(f"Event type={event_type} symbol={event_symbol} enqueued to {enqueued} chat(s)")

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse event: {e} data={message['data'][:200]}")
        except Exception as e:
            logger.error(f"Error processing event: {e}")

    # Cleanup on shutdown
    dispatcher.stop()
    await pubsub.unsubscribe()
    await r.close()


if __name__ == "__main__":
    try:
        asyncio.run(run_notifier())
    except KeyboardInterrupt:
        logger.info("Shutting down...")
