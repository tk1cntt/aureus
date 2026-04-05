---
phase: "27"
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - services/aureus-notifier/Dockerfile
  - services/aureus-notifier/requirements.txt
  - services/aureus-notifier/main.py
  - services/aureus-notifier/config.py
  - services/aureus-notifier/telegram_bot.py
  - services/aureus-notifier/formatters.py
  - services/aureus-notifier/rate_limiter.py
  - services/aureus-notifier/tests/test_formatters.py
  - services/aureus-notifier/tests/test_rate_limiter.py
  - services/aureus-notifier/tests/test_config.py
  - docker-compose.dev.yml
  - .env.example
autonomous: true
requirements:
  - NOTIF-02
  - NOTIF-03
  - NOTIF-04
  - NOTIF-05
  - NOTIF-06

must_haves:
  truths:
    - "Service subscribes to Redis channels aureus:signals:{symbol} for all configured symbols"
    - "SIGNAL_EVENT messages are formatted and sent to Telegram with HTML formatting"
    - "STRATEGY_MATCH messages are formatted with entry details (direction, SL/TP, size)"
    - "Filter config from Redis controls which events get sent"
    - "Rate limiting ensures max 1 msg/2s per chat"
    - "Multiple chats receive messages based on routing config"
    - "Config reloads at runtime via pub/sub without restart"
    - "Failed Telegram API calls retry with exponential backoff"
  artifacts:
    - path: "services/aureus-notifier/main.py"
      provides: "Entry point with Redis subscriber loop"
      exports: ["run_notifier"]
    - path: "services/aureus-notifier/config.py"
      provides: "Filter + route loader from Redis"
      exports: ["load_filters", "load_routes", "subscribe_config_updates"]
    - path: "services/aureus-notifier/telegram_bot.py"
      provides: "Telegram Bot API wrapper with retry"
      exports: ["TelegramSender"]
    - path: "services/aureus-notifier/formatters.py"
      provides: "Message formatting for SIGNAL_EVENT and STRATEGY_MATCH"
      exports: ["format_signal_event", "format_strategy_match"]
    - path: "services/aureus-notifier/rate_limiter.py"
      provides: "Queue-based dispatcher with fixed delay"
      exports: ["RateLimitedDispatcher"]
    - path: "services/aureus-notifier/Dockerfile"
      provides: "Docker image definition"
    - path: "services/aureus-notifier/requirements.txt"
      provides: "Python dependencies"
    - path: "services/aureus-notifier/tests/test_formatters.py"
      provides: "Formatter unit tests"
    - path: "services/aureus-notifier/tests/test_rate_limiter.py"
      provides: "Rate limiter unit tests"
    - path: "services/aureus-notifier/tests/test_config.py"
      provides: "Config loader unit tests"
    - path: "docker-compose.dev.yml"
      provides: "Service definition aureus-notifier-dev"
  key_links:
    - from: "services/aureus-notifier/main.py"
      to: "services/aureus-notifier/config.py"
      via: "import load_filters, load_routes, subscribe_config_updates"
      pattern: "from config import"
    - from: "services/aureus-notifier/main.py"
      to: "services/aureus-notifier/rate_limiter.py"
      via: "RateLimitedDispatcher enqueues messages"
      pattern: "RateLimitedDispatcher"
    - from: "services/aureus-notifier/rate_limiter.py"
      to: "services/aureus-notifier/telegram_bot.py"
      via: "TelegramSender.send_message with retry"
      pattern: "TelegramSender"
    - from: "services/aureus-notifier/rate_limiter.py"
      to: "services/aureus-notifier/formatters.py"
      via: "format_signal_event/format_strategy_match for message text"
      pattern: "format_signal_event|format_strategy_match"

user_setup:
  - service: telegram
    why: "Telegram Bot API requires bot token and chat IDs"
    env_vars:
      - name: TELEGRAM_BOT_TOKEN
        source: "Telegram BotFather -> /newbot or existing bot"
      - name: TELEGRAM_DEFAULT_CHAT_ID
        source: "Telegram chat/channel ID (use @userinfobot to get your chat ID)"
    dashboard_config:
      - task: "Create a Telegram bot via @BotFather and copy the token"
        location: "Telegram app, search @BotFather"
      - task: "Get your chat ID by messaging @userinfobot"
        location: "Telegram app, search @userinfobot"
---

<objective>
Create the aureus-notifier service: a standalone Python microservice that subscribes to Redis pub/sub channels, filters events, formats messages, and sends notifications to Telegram with rate limiting and multi-channel routing.

Purpose: Deliver NOTIF-02 through NOTIF-06 — complete Telegram notification capability for signal alerts and strategy matches.
Output: Working Docker service with 6 source files, 3 test files, docker-compose integration, and .env configuration.
</objective>

<execution_context>
@D:/Aureus/.qwen/get-shit-done/workflows/execute-plan.md
@D:/Aureus/.qwen/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/27-telegram-notification-service/27-CONTEXT.md
@.planning/REQUIREMENTS.md

@services/aureus-signal/engine/signal_event_publisher.py — Event payload shapes (SIGNAL_EVENT, STRATEGY_MATCH)
@services/aureus-gateway/main.py — Redis pub/sub subscriber pattern (lines 282-338)
@services/aureus-signal/Dockerfile — Python service Dockerfile pattern
@docker-compose.dev.yml — Existing service definitions for pattern matching
</context>

<interfaces>
<!-- Key types and contracts extracted from signal_event_publisher.py and CONTEXT.md -->

SIGNAL_EVENT payload (from signal_event_publisher.py:publish_signal_event):
```python
{
    "type": "SIGNAL_EVENT",
    "symbol": str,        # e.g. "XAUUSD"
    "t": int,             # Unix timestamp
    "data": {
        "signals": {      # Dict of signal_name -> signal_value
            "zigzag_state": "SWING_HIGH",
            "ob_state": "BULLISH",
            ...
        },
        "session": str,   # e.g. "NEW_YORK"
        ...
    }
}
```

STRATEGY_MATCH payload (from signal_event_publisher.py:publish_strategy_match):
```python
{
    "type": "STRATEGY_MATCH",
    "symbol": str,
    "t": int,
    "data": {
        "strategy": str,           # e.g. "CHOCH_UP"
        "strategy_id": int,        # e.g. 10
        "side": str,               # "BUY" or "SELL"
        "entry_type": str,         # "MARKET" | "LIMIT" | "STOP"
        "size_value": float,       # e.g. 1.0
        "size_mode": str,          # e.g. "FIXED_UNITS"
        "magic_number": int,
        "sl": float,               # Stop loss price
        "tp": float,               # Take profit price
        "reason_code": str,        # e.g. "OK"
        "origin_timestamp": str
    }
}
```

Redis channel pattern: `aureus:signals:{symbol}` (one channel per symbol)

Filter config (Redis hash `aureus:notifier:filters`):
```python
{
    "enabled": "true",                                    # "true" or "false"
    "signal_types": "SIGNAL_EVENT,STRATEGY_MATCH",        # comma-separated
    "symbols": "XAUUSD,BTCUSD,ETHUSD",                    # comma-separated, empty = all
    "strategies": "CHOCH_UP,CHOCH_DOWN",                  # comma-separated, empty = all
    "min_confidence": ""                                  # empty = no minimum
}
```

Route config (Redis hash `aureus:notifier:routes`, key "routes"):
```python
{
    "routes": json.dumps([
        {
            "chat_id": "-1001234567890",
            "event_types": ["STRATEGY_MATCH"],  # null/empty = all
            "symbols": ["XAUUSD", "BTCUSD"],    # null/empty = all
            "strategies": null                   # null/empty = all
        }
    ])
}
```

Telegram Bot API (python-telegram-bot v21+):
```python
from telegram import Bot
bot = Bot(token=os.environ["TELEGRAM_BOT_TOKEN"])
await bot.send_message(chat_id=chat_id, text=message, parse_mode="HTML")
```
</interfaces>

<tasks>

<task type="auto" tdd="true">
<id>T1</id>
<title>Create message formatters and write tests</title>
<requirements>NOTIF-02, NOTIF-04</requirements>
<wave>1</wave>
<depends_on></depends_on>
<autonomous>true</autonomous>
<files_modified>
- services/aureus-notifier/formatters.py
- services/aureus-notifier/tests/test_formatters.py
</files_modified>
<read_first>
- services/aureus-notifier/formatters.py (create new)
- services/aureus-signal/engine/signal_event_publisher.py (event payload shapes)
- .planning/phases/27-telegram-notification-service/27-CONTEXT.md (message format specifications)
</read_first>
<behavior>
- format_signal_event(event_dict) returns HTML string with emoji, symbol, time, session, active signals as bullet list, and hashtags
- format_signal_event handles missing optional fields gracefully (session=None → omit session line)
- format_strategy_match(result_dict) returns HTML string with emoji, symbol, strategy name+ID, direction with color emoji, entry type, SL/TP/size block, reason code, time, and hashtags
- format_strategy_match handles missing SL or TP by showing "N/A" instead of crashing
- Both functions return strings under 4096 chars (Telegram message limit)
- Both functions escape HTML special characters in user-provided strings
</behavior>
<action>
Create services/aureus-notifier/formatters.py with two functions:

1. `format_signal_event(event: dict) -> str`:
   - Input: dict with keys {type, symbol, t, data} where data contains {signals: dict, session: str}
   - Output: HTML-formatted string following this exact template:
   ```
   📊 <b>SIGNAL ALERT</b>
   ━━━━━━━━━━━━━━━━━━━
   <b>Symbol:</b> {symbol}
   <b>Time:</b> {utc_time} UTC
   <b>Session:</b> {session}    ← omit entire line if session is None/empty

   <b>Active Signals:</b>
   • {signal_name}: {signal_value}    ← one line per signal in data.signals
   • ...

   #{symbol} #Signal
   ```
   - Convert timestamp `t` (unix int) to UTC string: `datetime.utcfromtimestamp(t).strftime("%Y-%m-%d %H:%M:%S")`
   - Escape HTML special chars in signal names/values using `html.escape()`
   - If signals dict is empty, show "• (no active signals)"

2. `format_strategy_match(event: dict) -> str`:
   - Input: dict with keys {type, symbol, t, data} where data contains {strategy, strategy_id, side, entry_type, sl, tp, size_value, reason_code}
   - Output: HTML-formatted string following this exact template:
   ```
   🎯 <b>STRATEGY MATCH</b>
   ━━━━━━━━━━━━━━━━━━━
   <b>Symbol:</b> {symbol}
   <b>Strategy:</b> {strategy} #{strategy_id}
   <b>Direction:</b> {side} {emoji}    ← 🟢 for BUY, 🔴 for SELL, ⚪ for other
   <b>Entry Type:</b> {entry_type}

   <b>Trade Plan:</b>
   • SL: {sl or "N/A"}
   • TP: {tp or "N/A"}
   • Size: {size_value} lot
   • Risk: N/A

   <b>Reason:</b> {reason_code}
   <b>Time:</b> {utc_time} UTC

   #{symbol} #{strategy} #{side}
   ```
   - Handle None/missing sl/tp by showing "N/A"
   - Escape HTML special chars in strategy name, reason_code

Create services/aureus-notifier/tests/test_formatters.py with tests:
- test_format_signal_event_basic: Verify output contains "📊", "SIGNAL ALERT", symbol name, signal bullets
- test_format_signal_event_missing_session: Verify session line is absent when session=None
- test_format_signal_event_empty_signals: Verify "(no active signals)" shown
- test_format_strategy_match_buy: Verify "🟢", "BUY", SL/TP values present
- test_format_strategy_match_sell: Verify "🔴", "SELL"
- test_format_strategy_match_missing_sl_tp: Verify "N/A" for missing values
- test_format_functions_escape_html: Verify <script> in input becomes &lt;script&gt; in output
- test_format_functions_under_4096_chars: Verify output length < 4096
</action>
<verify>
<automated>cd /mnt/d/Aureus/services/aureus-notifier && ../../.venv/bin/python -m pytest tests/test_formatters.py -v</automated>
</verify>
<done>
All 8 formatter tests pass. format_signal_event and format_strategy_match produce correct HTML output per CONTEXT.md templates, handle edge cases, and stay under 4096 char limit.
</done>
</task>

<task type="auto" tdd="true">
<id>T2</id>
<title>Create config loader with Redis filter + route management and tests</title>
<requirements>NOTIF-03, NOTIF-06</requirements>
<wave>1</wave>
<depends_on></depends_on>
<autonomous>true</autonomous>
<files_modified>
- services/aureus-notifier/config.py
- services/aureus-notifier/tests/test_config.py
</files_modified>
<read_first>
- services/aureus-notifier/config.py (create new)
- services/aureus-gateway/main.py lines 282-318 (command subscriber pattern for config reload via pub/sub)
- .planning/phases/27-telegram-notification-service/27-CONTEXT.md (D2 filter config, D4 route config)
</read_first>
<behavior>
- load_filters(redis_client) reads aureus:notifier:filters hash, returns FilterConfig dataclass with {enabled, signal_types: set, symbols: set, strategies: set, min_confidence}
- load_routes(redis_client) reads aureus:notifier:routes hash key "routes", parses JSON, returns list of Route dataclass
- check_filter(config, event) returns True if event passes all filter criteria (enabled=True, event.type in signal_types, event.symbol in symbols or symbols empty, event.strategy in strategies or strategies empty)
- match_routes(event, routes) returns list of chat_ids whose route criteria match the event
- subscribe_config_updates(redis_client, callback) subscribes to aureus:cmd:notifier_config and calls callback on message
- Default values when Redis hash empty: enabled=True, signal_types={"SIGNAL_EVENT","STRATEGY_MATCH"}, symbols=set(), strategies=set()
</behavior>
<action>
Create services/aureus-notifier/config.py with:

1. Dataclasses:
```python
@dataclass
class FilterConfig:
    enabled: bool = True
    signal_types: set = field(default_factory=lambda: {"SIGNAL_EVENT", "STRATEGY_MATCH"})
    symbols: set = field(default_factory=set)
    strategies: set = field(default_factory=set)
    min_confidence: Optional[float] = None

@dataclass
class Route:
    chat_id: str
    event_types: Optional[list] = None    # null/empty = wildcard
    symbols: Optional[list] = None
    strategies: Optional[list] = None
```

2. `async def load_filters(r: redis.Redis) -> FilterConfig`:
   - HGETALL aureus:notifier:filters
   - Parse each field: "signal_types" → split by comma → set
   - "enabled" → "true"/"false" → bool
   - Return defaults if hash empty

3. `async def load_routes(r: redis.Redis) -> list[Route]`:
   - HGET aureus:notifier:routes "routes"
   - JSON parse → list of dicts → convert to Route list
   - Return empty list if key missing

4. `def passes_filter(config: FilterConfig, event: dict) -> bool`:
   - If config.enabled is False → return False
   - If config.signal_types is non-empty and event["type"] not in it → return False
   - If config.symbols is non-empty and event["symbol"] not in it → return False
   - Extract strategy from event["data"]["strategy"] if type=="STRATEGY_MATCH", check against config.strategies
   - Return True if all checks pass

5. `def match_routes(event: dict, routes: list[Route]) -> list[str]`:
   - For each route, check: event_type match (null/empty = all), symbol match (null/empty = all), strategy match (null/empty = all)
   - Return list of matching chat_ids

6. `async def subscribe_config_updates(r: redis.Redis, callback: Callable)`:
   - Subscribe to "aureus:cmd:notifier_config" pub/sub channel
   - On message, await callback() to reload config
   - Pattern matches aureus-gateway main.py lines 282-318

Create services/aureus-notifier/tests/test_config.py with tests:
- test_load_filters_defaults: Empty Redis returns enabled=True with default signal_types
- test_load_filters_from_redis: Mock HGETALL returns values, verify parsed correctly
- test_passes_filter_enabled_false: Returns False when enabled=False
- test_passes_filter_signal_type_mismatch: Returns False when event type not in signal_types
- test_passes_filter_symbol_mismatch: Returns False when symbol not in symbols set
- test_passes_filter_all_match: Returns True when all criteria match
- test_match_routes_exact: Event matches route with exact event_type, symbol, strategy
- test_match_routes_wildcard: Route with null symbols/strategies matches any event
- test_match_routes_no_match: Event doesn't match route criteria
- test_match_routes_multiple: One event matches multiple routes, returns multiple chat_ids
- test_match_routes_partial_criteria: Route filters only by event_type, not symbol
</action>
<verify>
<automated>cd /mnt/d/Aureus/services/aureus-notifier && ../../.venv/bin/python -m pytest tests/test_config.py -v</automated>
</verify>
<done>
All 11 config tests pass. Filter loading, route matching, and config update subscription work correctly with proper defaults and edge case handling.
</done>
</task>

<task type="auto">
<id>T3</id>
<title>Create Telegram Bot wrapper with retry and exponential backoff</title>
<requirements>NOTIF-05</requirements>
<wave>1</wave>
<depends_on></depends_on>
<autonomous>true</autonomous>
<files_modified>
- services/aureus-notifier/telegram_bot.py
</files_modified>
<read_first>
- services/aureus-notifier/telegram_bot.py (create new)
- .planning/phases/27-telegram-notification-service/27-CONTEXT.md (D3 rate limiting — error handling section)
</read_first>
<action>
Create services/aureus-notifier/telegram_bot.py with TelegramSender class:

```python
import asyncio
import os
import logging
from telegram import Bot
from telegram.error import TelegramError, RetryAfter

logger = logging.getLogger(__name__)

class TelegramSender:
    """Telegram Bot API wrapper with retry and exponential backoff."""

    def __init__(self, bot_token: str, max_retries: int = 3, base_delay: float = 2.0):
        self.bot = Bot(token=bot_token)
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
```

Key behaviors:
- Constructor accepts bot_token, max_retries (default 3), base_delay (default 2.0s)
- send_message uses python-telegram-bot v21+ async API
- RetryAfter exception: wait the server-suggested retry_after value (capped at 30s)
- TelegramError: exponential backoff 2s → 4s → 8s
- Other exceptions: log and return False immediately (no retry)
- Returns True on success, False after exhausting retries
- connect_timeout and read_timeout set to 10s to prevent hanging
</action>
<verify>
<automated>cd /mnt/d/Aureus/services/aureus-notifier && ../../.venv/bin/python -c "from telegram_bot import TelegramSender; print('import OK')"</automated>
</verify>
<done>
telegram_bot.py imports without error. TelegramSender class has send_message method with retry logic, exponential backoff, and proper error handling.
</done>
</task>

<task type="auto">
<id>T4</id>
<title>Create queue-based rate limiter dispatcher</title>
<requirements>NOTIF-05, NOTIF-06</requirements>
<wave>1</wave>
<depends_on>T2, T3</depends_on>
<autonomous>true</autonomous>
<files_modified>
- services/aureus-notifier/rate_limiter.py
</files_modified>
<read_first>
- services/aureus-notifier/rate_limiter.py (create new)
- services/aureus-notifier/config.py (Route, match_routes)
- services/aureus-notifier/telegram_bot.py (TelegramSender)
- services/aureus-notifier/formatters.py (format functions)
- .planning/phases/27-telegram-notification-service/27-CONTEXT.md (D3 rate limiting architecture)
</read_first>
<action>
Create services/aureus-notifier/rate_limiter.py with RateLimitedDispatcher class:

```python
import asyncio
import logging
from typing import Dict
from telegram_bot import TelegramSender
from config import Route, match_routes
from formatters import format_signal_event, format_strategy_match

logger = logging.getLogger(__name__)

class RateLimitedDispatcher:
    """Queue-based dispatcher: 1 msg/2s per chat, max 100 queued per chat."""

    def __init__(self, sender: TelegramSender, delay: float = 2.0, max_queue_size: int = 100):
        self.sender = sender
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
        # Format message based on event type
        if event["type"] == "SIGNAL_EVENT":
            text = format_signal_event(event)
        elif event["type"] == "STRATEGY_MATCH":
            text = format_strategy_match(event)
        else:
            logger.warning(f"Unknown event type: {event['type']}")
            return 0

        for chat_id in chat_ids:
            queue = self._get_queue(chat_id)
            try:
                queue.put_nowait((chat_id, text))
                count += 1
            except asyncio.QueueFull:
                # Drop oldest message when queue is full
                try:
                    queue.get_nowait()
                    queue.put_nowait((chat_id, text))
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
                        cid, text = queue.get_nowait()
                        success = await self.sender.send_message(cid, text)
                        if success:
                            queue.task_done()
                            sent_any = True
                        else:
                            # Re-queue if send failed (will be retried next cycle)
                            queue.put_nowait((cid, text))
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
```

Key behaviors:
- Per-chat isolation: each chat_id gets its own asyncio.Queue(maxsize=100)
- enqueue() routes event → matches chat_ids → formats message → enqueues to each matching chat
- dispatch_loop() runs continuously: iterates all queues, sends 1 message from each, sleeps {delay}s between cycles
- Queue full handling: drop oldest message (get_nowait) then put new message, with warning log
- Failed send handling: re-queue message for next cycle (sender handles its own retries)
- stop() sets _running=False to gracefully exit loop
</action>
<verify>
<automated>cd /mnt/d/Aureus/services/aureus-notifier && ../../.venv/bin/python -c "from rate_limiter import RateLimitedDispatcher; print('import OK')"</automated>
</verify>
<done>
rate_limiter.py imports without error. RateLimitedDispatcher has enqueue(), dispatch_loop(), stop() methods with queue-based rate limiting at 1 msg/2s per chat.
</done>
</task>

<task type="auto">
<id>T5</id>
<title>Create main.py entry point with Redis pub/sub subscriber</title>
<requirements>NOTIF-02</requirements>
<wave>1</wave>
<depends_on>T1, T2, T3, T4</depends_on>
<autonomous>true</autonomous>
<files_modified>
- services/aureus-notifier/main.py
</files_modified>
<read_first>
- services/aureus-notifier/main.py (create new)
- services/aureus-gateway/main.py lines 282-338 (Redis pub/sub subscriber pattern)
- services/aureus-signal/engine/signal_event_publisher.py (channel naming: aureus:signals:{symbol})
- .planning/phases/27-telegram-notification-service/27-CONTEXT.md (service architecture)
</read_first>
<action>
Create services/aureus-notifier/main.py with run_notifier() async function:

```python
import asyncio
import json
import os
import signal
import logging
import redis
from config import load_filters, load_routes, subscribe_config_updates, FilterConfig, Route
from telegram_bot import TelegramSender
from rate_limiter import RateLimitedDispatcher

logging.basicConfig(
    level=getattr(logging, os.environ.get("LOG_LEVEL", "INFO")),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

async def run_notifier():
    # 1. Initialize Redis connection
    redis_host = os.environ.get("REDIS_HOST", "aureus_redis_dev")
    redis_port = int(os.environ.get("REDIS_PORT", 6379))
    logger.info(f"Connecting to Redis at {redis_host}:{redis_port}")
    r = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
    await r.ping()
    logger.info("Redis connected")

    # 2. Initialize Telegram sender
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        logger.error("TELEGRAM_BOT_TOKEN not set")
        return
    sender = TelegramSender(bot_token)

    # 3. Load initial config
    filters: FilterConfig = await load_filters(r)
    routes: list[Route] = await load_routes(r)
    logger.info(f"Loaded filters: enabled={filters.enabled}, signal_types={filters.signal_types}")
    logger.info(f"Loaded routes: {len(routes)} routes")

    # 4. Initialize dispatcher
    dispatcher = RateLimitedDispatcher(sender)

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
```

Key behaviors:
- Reads env vars: REDIS_HOST, REDIS_PORT, TELEGRAM_BOT_TOKEN, SYMBOLS, LOG_LEVEL
- Subscribes to aureus:signals:{symbol} for each symbol in SYMBOLS env var
- Uses config.subscribe_config_updates for runtime config reload
- Runs dispatcher.dispatch_loop() as background task
- Filters events before enqueueing using config.passes_filter
- Parses JSON events, handles malformed data gracefully
- Graceful shutdown on Ctrl+C
</action>
<verify>
<automated>cd /mnt/d/Aureus/services/aureus-notifier && ../../.venv/bin/python -c "import main; print('import OK')"</automated>
</verify>
<done>
main.py imports without error. run_notifier() connects to Redis, subscribes to signal channels, loads config, starts dispatcher, and processes events with filtering.
</done>
</task>

<task type="auto">
<id>T6</id>
<title>Create Dockerfile, requirements.txt, and docker-compose.dev.yml service entry</title>
<requirements>NOTIF-02</requirements>
<wave>1</wave>
<depends_on></depends_on>
<autonomous>true</autonomous>
<files_modified>
- services/aureus-notifier/Dockerfile
- services/aureus-notifier/requirements.txt
- docker-compose.dev.yml
- .env.example
</files_modified>
<read_first>
- services/aureus-signal/Dockerfile (Python service Dockerfile pattern)
- docker-compose.dev.yml (existing service definitions, especially aureus-signal-dev and aureus-gateway-dev)
- .env.example (existing env var documentation)
</read_first>
<action>
Create services/aureus-notifier/Dockerfile:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
```

Create services/aureus-notifier/requirements.txt:
```
python-telegram-bot==21.0
redis>=5.0.0
python-dotenv==1.0.0
```

Add to docker-compose.dev.yml (append to services section, before networks):
```yaml
  aureus-notifier-dev:
    build:
      context: ./services/aureus-notifier
    container_name: aureus-notifier-dev
    environment:
      - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
      - TELEGRAM_DEFAULT_CHAT_ID=${TELEGRAM_DEFAULT_CHAT_ID}
      - REDIS_HOST=redis-dev
      - REDIS_PORT=6379
      - SYMBOLS=${SYMBOLS:-XAUUSD,BTCUSD,ETHUSD,USTEC,USDJPY,EURUSD,GBPUSD,AUDUSD}
      - LOG_LEVEL=INFO
      - PYTHONUNBUFFERED=1
    networks:
      - aureus_dev_net
    depends_on:
      - redis-dev
    restart: unless-stopped
```

Append to .env.example:
```
# Telegram Notifier (Phase 27)
TELEGRAM_BOT_TOKEN=          # Bot token from @BotFather on Telegram
TELEGRAM_DEFAULT_CHAT_ID=    # Chat/channel ID (use @userinfobot to get your ID)
```

Note: Use `redis-dev` as REDIS_HOST (matches other services' naming in docker-compose.dev.yml).
</action>
<verify>
<automated>wsl -d Aureus -u root bash -lc "cd /mnt/d/Aureus && grep -q 'aureus-notifier-dev' docker-compose.dev.yml && echo 'FOUND' || echo 'MISSING'"</automated>
</verify>
<done>
Dockerfile exists with FROM python:3.11-slim. requirements.txt contains python-telegram-bot. docker-compose.dev.yml contains service aureus-notifier-dev with TELEGRAM_BOT_TOKEN env var and depends_on redis-dev. .env.example contains TELEGRAM_BOT_TOKEN and TELEGRAM_DEFAULT_CHAT_ID entries.
</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Redis → Notifier | Untrusted event data from pub/sub channels (malformed JSON, oversized payloads) |
| Notifier → Telegram Bot API | Outbound HTTPS calls to api.telegram.org (external service) |
| Env Vars → Notifier | TELEGRAM_BOT_TOKEN is secret material injected at runtime |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-27-01 | Tampering | Redis pub/sub events | mitigate | Validate event JSON structure before processing; catch json.JSONDecodeError and log warning without crashing |
| T-27-02 | Information Disclosure | TELEGRAM_BOT_TOKEN in env | mitigate | Never log bot token; use `${TELEGRAM_BOT_TOKEN}` in docker-compose (not hardcoded); document in .env.example with empty default |
| T-27-03 | Denial of Service | Queue overflow | mitigate | asyncio.Queue(maxsize=100) per chat; drop oldest message when full with warning log (prevents memory exhaustion) |
| T-27-04 | Spoofing | Fake signal channels | accept | Notifier subscribes only to pre-configured `aureus:signals:{symbol}` channels; no dynamic channel creation from untrusted input |
| T-27-05 | Elevation of Privilege | Config reload via pub/sub | mitigate | `aureus:cmd:notifier_config` channel only triggers config reload (HGETALL), not arbitrary commands; no exec/eval of message content |
| T-27-06 | Repudiation | Failed message delivery | mitigate | Log all send failures with chat_id, event type, and error details; return False after max retries so caller knows delivery failed |
</threat_model>

<verification>
## Verification

### Must Haves
- [ ] `services/aureus-notifier/` directory exists with all 6 source files
- [ ] `services/aureus-notifier/Dockerfile` uses `FROM python:3.11-slim`
- [ ] `services/aureus-notifier/requirements.txt` includes `python-telegram-bot`, `redis`, `python-dotenv`
- [ ] `services/aureus-notifier/main.py` subscribes to `aureus:signals:{symbol}` channels
- [ ] `services/aureus-notifier/config.py` reads from `aureus:notifier:filters` and `aureus:notifier:routes`
- [ ] `services/aureus-notifier/formatters.py` has `format_signal_event` and `format_strategy_match`
- [ ] `services/aureus-notifier/rate_limiter.py` has `RateLimitedDispatcher` with per-chat queues
- [ ] `services/aureus-notifier/telegram_bot.py` has `TelegramSender` with exponential backoff retry
- [ ] `docker-compose.dev.yml` contains `aureus-notifier-dev` service
- [ ] `.env.example` documents `TELEGRAM_BOT_TOKEN` and `TELEGRAM_DEFAULT_CHAT_ID`
- [ ] All 19 unit tests pass (8 formatters + 11 config)

### Tests
```bash
# Run all tests from services/aureus-notifier directory
cd /mnt/d/Aureus/services/aureus-notifier
../../.venv/bin/python -m pytest tests/test_formatters.py tests/test_config.py -v
```

Expected: 19 passed, 0 failed

### Build Test
```bash
wsl -d Aureus -u root bash -lc "cd /mnt/d/Aureus && docker compose -f docker-compose.dev.yml build aureus-notifier-dev"
```
Expected: Build completes without error, image created

### Integration Test (manual, requires TELEGRAM_BOT_TOKEN set)
1. Set TELEGRAM_BOT_TOKEN and TELEGRAM_DEFAULT_CHAT_ID in .env
2. `wsl -d Aureus -u root bash -lc "cd /mnt/d/Aureus && docker compose -f docker-compose.dev.yml up -d aureus-notifier-dev"`
3. Check logs: `wsl -d Aureus -e bash -lc "docker logs aureus-notifier-dev 2>&1 | tail -20"`
4. Expected: "Subscribed to channels: [...]" and "Dispatcher loop started"
5. Publish test event: `wsl -d Aureus -e bash -lc "docker exec aureus_redis_dev redis-cli PUBLISH aureus:signals:XAUUSD '{\"type\":\"SIGNAL_EVENT\",\"symbol\":\"XAUUSD\",\"t\":1712345678,\"data\":{\"signals\":{\"test\":\"value\"},\"session\":\"NEW_YORK\"}}'"`
6. Expected: Message appears in Telegram chat

### UAT
```bash
# Verify service is running
wsl -d Aureus -e bash -lc "docker compose -f docker-compose.dev.yml ps aureus-notifier-dev"
# Expected: State = Up

# Verify filter config can be set
wsl -d Aureus -e bash -lc "docker exec aureus_redis_dev redis-cli HSET aureus:notifier:filters enabled true signal_types SIGNAL_EVENT,STRATEGY_MATCH symbols XAUUSD,BTCUSD"
# Expected: (integer) N

# Verify runtime config reload
wsl -d Aureus -e bash -lc "docker exec aureus_redis_dev redis-cli PUBLISH aureus:cmd:notifier_config reload"
# Expected: Log shows "Config reloaded"
```
</verification>

<success_criteria>
1. Service `aureus-notifier-dev` builds and starts in Docker compose environment
2. Subscribes to Redis channels `aureus:signals:{symbol}` for all configured symbols
3. SIGNAL_EVENT alerts format and send to Telegram with emoji, symbol, signals, session
4. STRATEGY_MATCH alerts format and send with strategy, direction, entry type, SL/TP, size
5. Filter config from `aureus:notifier:filters` controls which events are sent (by type, symbol, strategy)
6. Rate limiting works: queue-based, max 1 msg/2s per chat, never exceeds 30 msg/min
7. Multi-channel routing from `aureus:notifier:routes` sends to correct chats based on event criteria
8. Runtime config reload via `aureus:cmd:notifier_config` pub/sub channel without restart
9. Error recovery: retry with exponential backoff (2s, 4s, 8s) max 3 attempts for Telegram API failures
10. 19 unit tests pass (formatters + config)
</success_criteria>

<output>
After completion, create `.planning/phases/27-telegram-notification-service/27-01-SUMMARY.md` with:
- Build status (success/failure)
- Test results (pass/fail count)
- Service startup confirmation
- Any issues encountered
- Next steps (Phase 28 planning or manual testing with real bot token)
</output>
