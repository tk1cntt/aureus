# Phase 27 — Telegram Notification Service

## CONTEXT

**Phase:** 27
**Requirements:** NOTIF-02, NOTIF-03, NOTIF-04, NOTIF-05, NOTIF-06
**Goal:** Xây dựng aureus-notifier service nhận events từ Redis và gửi thông báo lên Telegram.

---

## Decisions

### D1: Notification Triggers — Both SIGNAL_EVENT and STRATEGY_MATCH

**Decision:** Gửi Telegram notification cho **cả 2 event types** với format khác nhau:

**SIGNAL_EVENT format (lightweight alert):**
```
📊 SIGNAL ALERT
Symbol: XAUUSD
Time: 2026-04-05 16:30:00
Signals: zigzag_state=SWING_HIGH, ob_state=BULLISH
```

**STRATEGY_MATCH format (full trade alert):**
```
🎯 STRATEGY MATCH
Symbol: XAUUSD
Strategy: CHOCH_UP #10
Direction: BUY
Entry Type: MARKET
SL: 1950.50 | TP: 1970.00
Size: 1.0 lot
Reason: OK
```

**Rationale:**
- NOTIF-02: "Signal alerts gửi lên Telegram với format đầy đủ" → cần notify cả SIGNAL_EVENT
- NOTIF-04: "Strategy match alerts gửi với entry details" → cần notify cả STRATEGY_MATCH
- SIGNAL_EVENT cho trader biết market condition đang thay đổi (early warning)
- STRATEGY_MATCH cho trader biết cụ thể trade nào sẽ execute (actionable)
- Filter config (D2) cho phép user tắt từng loại nếu muốn giảm noise

**Payload refs:**
- `services/aureus-signal/engine/signal_event_publisher.py`: Publishes both types
- `services/aureus-signal/engine/live_engine.py` line 670: SIGNAL_EVENT publish
- `services/aureus-signal/engine/strategy_executor.py` line 410: STRATEGY_MATCH publish

---

### D2: Filter Configuration — Redis Key Store

**Decision:** Filter config lưu trong **Redis hash key** `aureus:notifier:filters` với structure:

```json
{
  "enabled": true,
  "signal_types": ["SIGNAL_EVENT", "STRATEGY_MATCH"],
  "symbols": ["XAUUSD", "BTCUSD", "ETHUSD"],
  "strategies": ["CHOCH_UP", "CHOCH_DOWN", "SESSION_SWEEP_BULL"],
  "min_confidence": null
}
```

**Commands:**
- `HGETALL aureus:notifier:filters` — đọc config hiện tại
- `HSET aureus:notifier:filters <key> <value>` — update từng field
- Subscribe to `aureus:cmd:notifier_config` channel để reload realtime

**Reload mechanism:** Notifier subscribe `aureus:cmd:notifier_config` pub/sub channel. Khi có message, reload filter từ Redis hash mà không cần restart.

**Rationale:**
- NOTIF-03: "Cấu hình filter signal (chọn signal nào được phép gửi Telegram)"
- Redis phù hợp vì: (1) đã có infra, (2) dynamic reload không cần restart, (3) đơn giản hơn DB
- Hash structure cho phép update từng field mà không cần overwrite toàn bộ config
- Pub/Sub reload channel theo pattern existing `aureus:cmd:refresh_strategies` đã dùng trong signal service
- JSON config file quá cứng (cần restart), DB table quá phức tạp cho use case này

**Canonical refs:**
- `services/aureus-gateway/main.py` lines 282-318: Pattern cho config reload via pub/sub
- `services/aureus-signal/engine/live_engine.py` lines 437-441: Same pattern for strategy refresh

---

### D3: Rate Limiting — Queue with Fixed Delay

**Decision:** Implement **message queue per chat** với fixed delay dispatcher:

**Architecture:**
```
Redis Event → Filter Check → Enqueue(chat_id) → Dispatcher Loop (every 2s)
```

**Implementation:**
- asyncio.Queue per chat_id: `queues[chat_id] = asyncio.Queue(maxsize=100)`
- Dispatcher task chạy mỗi 2 giây, lấy 1 message từ mỗi queue và gửi
- Nếu queue đầy (>100 messages), drop oldest message với warning log
- Telegram API limit: 30 msg/min per chat → 1 msg/2s = 30 msg/min (safe margin)

**Error handling:**
- Telegram API lỗi (429, 500, timeout) → retry với exponential backoff (2s, 4s, 8s) max 3 lần
- Sau 3 lần failed → log error và drop message
- Network error → không block queue, move to next message

**Rationale:**
- NOTIF-05: "Rate limiting hoạt động (không vượt 25 msg/s)"
- Telegram Bot API giới hạn: 30 messages/second (global), 30 messages/minute (per chat)
- Queue + fixed delay đảm bảo KHÔNG BAO GIỜ vượt limit
- Đơn giản hơn token bucket (không cần tính refill rate) và sliding window (không cần track history)
- Per-queue isolation đảm bảo chat này không ảnh hưởng chat khác

**No existing rate limiter to reuse** — trading-agents chỉ có API-specific retry logic cho yfinance/AlphaVantage.

---

### D4: Multi-Channel — Configurable Event Routing

**Decision:** Configurable routing table trong Redis hash `aureus:notifier:routes`:

```json
{
  "routes": [
    {
      "chat_id": "-1001234567890",
      "event_types": ["STRATEGY_MATCH"],
      "symbols": ["XAUUSD", "BTCUSD"],
      "strategies": null
    },
    {
      "chat_id": "-1009876543210",
      "event_types": ["SIGNAL_EVENT", "STRATEGY_MATCH"],
      "symbols": null,
      "strategies": null
    }
  ]
}
```

**Routing logic:**
1. Event received → iterate routes
2. Match if: event_type in route.event_types (or route.event_types is null/empty)
3. Match if: symbol in route.symbols (or route.symbols is null/empty = all)
4. Match if: strategy in route.strategies (or route.strategies is null/empty = all)
5. Send to ALL matching chats

**Default route:** Nếu không có route nào config, dùng default route gửi TẤT CẢ events tới `DEFAULT_CHAT_ID` (env var).

**Reload:** Same pub/sub channel `aureus:cmd:notifier_config` để reload routes runtime.

**Rationale:**
- NOTIF-06: "Hỗ trợ gửi nhiều chat/channel"
- Configurable routing linh hoạt hơn "send same to all":
  - Admin channel nhận STRATEGY_MATCH (trades thực tế)
  - Trading signal channel nhận cả SIGNAL_EVENT + STRATEGY_MATCH
  - VIP channel chỉ nhận specific strategies hoặc symbols
- Null/empty = wildcard cho phép "all" mà không cần liệt kê
- Route table đơn giản, dễ debug, dễ modify qua Redis CLI

---

## Service Architecture

### Service Name: `aureus-notifier-dev`

**Directory structure:**
```
services/aureus-notifier/
├── Dockerfile
├── requirements.txt (asyncpg, redis, python-telegram-bot)
├── main.py (entry point, event loop)
├── config.py (filter + route loader from Redis)
├── telegram_bot.py (Telegram Bot API wrapper)
├── formatters.py (message formatting for each event type)
└── rate_limiter.py (queue-based dispatcher)
```

**Dependencies:**
- `python-telegram-bot` v21+ (async API)
- `redis` >= 5.0.0 (đã có trong ecosystem)
- `python-dotenv` cho local dev

**Environment variables:**
```bash
TELEGRAM_BOT_TOKEN=<bot token từ BotFather>
TELEGRAM_DEFAULT_CHAT_ID=<chat_id mặc định>
REDIS_HOST=redis-dev
REDIS_PORT=6379
LOG_LEVEL=INFO
```

**Docker compose:**
```yaml
aureus-notifier-dev:
  build: ./services/aureus-notifier
  container_name: aureus-notifier-dev
  environment:
    - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
    - TELEGRAM_DEFAULT_CHAT_ID=${TELEGRAM_DEFAULT_CHAT_ID}
    - REDIS_HOST=aureus_redis_dev
    - REDIS_PORT=6379
    - LOG_LEVEL=INFO
  networks:
    - aureus_dev_net
  depends_on:
    - aureus_redis_dev
  restart: unless-stopped
```

---

## Message Format Specifications

### SIGNAL_EVENT Message
```
📊 <b>SIGNAL ALERT</b>
━━━━━━━━━━━━━━━━━━━
<b>Symbol:</b> XAUUSD
<b>Time:</b> 2026-04-05 16:30:00 UTC
<b>Session:</b> NEW_YORK

<b>Active Signals:</b>
• zigzag_state: SWING_HIGH
• ob_state: BULLISH
• trend_state: BULLISH_CONTINUATION

#XAUUSD #Signal
```

### STRATEGY_MATCH Message
```
🎯 <b>STRATEGY MATCH</b>
━━━━━━━━━━━━━━━━━━━
<b>Symbol:</b> XAUUSD
<b>Strategy:</b> CHOCH_UP #10
<b>Direction:</b> BUY 🟢
<b>Entry Type:</b> MARKET

<b>Trade Plan:</b>
• SL: 1950.50
• TP: 1970.00
• Size: 1.0 lot
• Risk: N/A

<b>Reason:</b> OK
<b>Time:</b> 2026-04-05 16:30:00 UTC

#XAUUSD #CHOCH_UP #BUY
```

**Format notes:**
- HTML parse mode cho bold/emoji
- Hashtags ở cuối để dễ search trong Telegram
- Separator line cho readability
- Time format: UTC cho consistency across timezones

---

## Reusable Assets

### EXISTS (can reuse):
- ✅ Redis pub/sub publisher: `services/aureus-signal/engine/signal_event_publisher.py`
- ✅ Redis pub/sub subscriber pattern: `services/aureus-gateway/main.py` lines 282-318
- ✅ Signal event payloads: Two shapes (SIGNAL_EVENT, STRATEGY_MATCH)
- ✅ Publisher tests: `services/aureus-signal/tests/test_signal_event_publisher.py`
- ✅ Docker compose patterns: Existing 12 services trong `docker-compose.dev.yml`
- ✅ Redis connection setup: `services/aureus-signal/infrastructure/redis.py`
- ✅ Config reload via pub/sub: `services/aureus-signal/engine/strategy_executor.py`

### MUST BUILD:
- ❌ `services/aureus-notifier/` directory (new service)
- ❌ Telegram Bot API integration (python-telegram-bot)
- ❌ Message formatters for both event types
- ❌ Queue-based rate limiter (new implementation)
- ❌ Filter config loader from Redis
- ❌ Route table matcher
- ❌ Docker service definition in compose files
- ❌ `.env` configuration for bot token and chat IDs

---

## Carry-forward from prior phases

| Source | Decision | Relevance |
|--------|----------|-----------|
| Phase 26 | Signal event publisher with 2 event types | Primary input for notifier |
| Phase 26 | STRATEGY_MATCH payload includes magic_number, SL/TP, entry_type | Used in message formatting |
| Phase 26 | Redis pub/sub channel `aureus:signals:{symbol}` | Notifier subscribes to these |
| Phase 24 | Provider mode routing | Not applicable (notifier chỉ đọc Redis) |
| Phase 25 | Circuit breaker pattern | Có thể áp dụng cho Telegram API calls |

---

## Success Criteria (Updated)

1. ✅ Service `aureus-notifier` chạy trong Docker, subscribe Redis channels `aureus:signals:{symbol}`
2. ✅ SIGNAL_EVENT alerts gửi lên Telegram với format đầy đủ (symbol, signal type, values)
3. ✅ STRATEGY_MATCH alerts gửi với entry details (strategy, direction, entry, SL/TP, size)
4. ✅ Filter config từ Redis cho phép bật/tắt từng loại signal/symbol/strategy
5. ✅ Rate limiting hoạt động (queue-based, max 1 msg/2s per chat, không vượt 30 msg/min)
6. ✅ Multi-channel support với configurable routing (event type, symbol, strategy filters)
7. ✅ Runtime config reload qua pub/sub channel (không cần restart)
8. ✅ Error recovery với retry + exponential backoff cho Telegram API calls

---
*Context created: 2026-04-05*
*Ready for researcher and planner agents*
