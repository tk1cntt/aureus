"""
Telegram Bot API wrapper with retry and exponential backoff.
"""
import asyncio
import os
import logging
from telegram import Bot
from telegram.request import HTTPXRequest
from telegram.error import TelegramError, RetryAfter

logger = logging.getLogger(__name__)


class TelegramSender:
    """Telegram Bot API wrapper with retry and exponential backoff."""

    def __init__(self, bot_token: str, max_retries: int = 3, base_delay: float = 2.0):
        req = HTTPXRequest(connection_pool_size=50)
        self.bot = Bot(token=bot_token, request=req)
        self.max_retries = max_retries
        self.base_delay = base_delay

    async def send_message(self, chat_id: str, text: str, parse_mode: str = "HTML") -> bool:
        """Send message with exponential backoff retry. Returns True on success."""
        for attempt in range(self.max_retries):
            try:
                await self.bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    parse_mode=parse_mode,
                    connect_timeout=10,
                    read_timeout=10,
                )
                logger.info(f"Message sent to {chat_id}")
                return True
            except RetryAfter as e:
                # Telegram rate limit hit — wait the suggested retry time
                wait_time = min(e.retry_after, 30)  # cap at 30s
                logger.warning(f"Rate limited by Telegram, retrying in {wait_time}s")
                await asyncio.sleep(wait_time)
            except TelegramError as e:
                if attempt < self.max_retries - 1:
                    delay = self.base_delay * (2 ** attempt)  # 2s, 4s, 8s
                    logger.warning(f"Telegram error: {e}, retrying in {delay}s (attempt {attempt+1}/{self.max_retries})")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Failed to send message to {chat_id} after {self.max_retries} attempts: {e}")
                    return False
            except Exception as e:
                logger.error(f"Unexpected error sending to {chat_id}: {e}")
                return False
        return False
