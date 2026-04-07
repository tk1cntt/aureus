"""
Queue-based rate limiter dispatcher for Telegram notifications.

Per-chat isolation with fixed delay between sends.
"""
import asyncio
import logging
from typing import Dict

from telegram_bot import TelegramSender
from config import Route, match_routes
from formatters import format_signal_event, format_strategy_match

logger = logging.getLogger(__name__)


class RateLimitedDispatcher:
    """Queue-based dispatcher: 1 msg/2s per chat (30 msg/min per-chat safe margin), max 100 queued per chat.

    Note: Telegram limits are 30 msg/s globally and 30 msg/min per chat.
    This dispatcher handles per-chat limiting. Global limiting is implicitly
    bounded by the number of active chats × dispatch_loop iteration time.
    """

    def __init__(self, sender: TelegramSender, sender_strategy: TelegramSender = None, delay: float = 2.0, max_queue_size: int = 100):
        self.sender = sender
        self.sender_strategy = sender_strategy or sender
        self.delay = delay
        self.max_queue_size = max_queue_size
        self.queues: Dict[str, asyncio.Queue] = {}
        self._running = False

    def _get_queue(self, chat_id: str) -> asyncio.Queue:
        """Get or create queue for a chat_id."""
        if chat_id not in self.queues:
            self.queues[chat_id] = asyncio.Queue(maxsize=self.max_queue_size)
            logger.info(f"Created queue for chat {chat_id}")
        return self.queues[chat_id]

    async def enqueue(self, event: dict, routes: list[Route]) -> int:
        """
        Route event to matching chats, enqueue formatted messages.
        Returns number of messages enqueued.
        """
        chat_ids = match_routes(event, routes)
        if not chat_ids:
            logger.warning(f"No routes matched for event type={event.get('type')} symbol={event.get('symbol')}")
            return 0

        count = 0
        if event["type"] == "SIGNAL_EVENT":
            text = format_signal_event(event)
        elif event["type"] == "STRATEGY_MATCH":
            text = format_strategy_match(event)
        else:
            logger.warning(f"Unknown event type: {event['type']}")
            return 0

        if not text:
            return 0

        for chat_id in chat_ids:
            queue = self._get_queue(chat_id)
            try:
                queue.put_nowait((chat_id, text, event["type"]))
                count += 1
            except asyncio.QueueFull:
                # Drop oldest message when queue is full
                try:
                    queue.get_nowait()
                    queue.put_nowait((chat_id, text, event["type"]))
                    count += 1
                    logger.warning(f"Queue full for chat {chat_id}, dropped oldest message")
                except Exception as e:
                    logger.error(f"Failed to enqueue for chat {chat_id}: {e}")

        return count

    async def dispatch_loop(self):
        """Main dispatcher loop: send 1 message from each queue every {delay} seconds."""
        self._running = True
        logger.info("Dispatcher loop started")
        while self._running:
            sent_any = False
            for chat_id, queue in list(self.queues.items()):
                if not queue.empty():
                    try:
                        cid, text, evt_type = queue.get_nowait()
                        target_sender = self.sender_strategy if evt_type == "STRATEGY_MATCH" else self.sender
                        success = await target_sender.send_message(cid, text)
                        if success:
                            queue.task_done()
                            sent_any = True
                        else:
                            # Re-queue if send failed (will be retried next cycle)
                            queue.put_nowait((cid, text, evt_type))
                    except asyncio.QueueEmpty:
                        pass
                    except Exception as e:
                        logger.error(f"Dispatch error for chat {chat_id}: {e}")

            if not sent_any:
                # No messages to send, wait the full delay
                await asyncio.sleep(self.delay)
            else:
                # Sent something, small sleep before next iteration
                await asyncio.sleep(0.1)

    def stop(self):
        """Stop the dispatcher loop."""
        self._running = False
