# Phase 35: MT5 Order Status Reporter - Context

**Gathered:** 2026-04-07
**Status:** Ready for planning

<domain>
## Phase Boundary

Gửi thông tin order MT5 hiện tại lên Telegram mỗi 1 phút. Bao gồm:
1. Danh sách open positions đang chạy (current P/L, pips, lot)
2. Order đã close trong vòng 1 phút gần nhất (profit/loss)
3. Tổng profit các lệnh đang chạy

Scope KHÔNG bao gồm: order management (modify SL/TP), position sizing, hay advanced analytics.

</domain>

<decisions>
## Implementation Decisions

### Data Flow Architecture
- **D-01:** Python service (aureus-notifier) chủ động gửi `REQUEST_TRADE_HISTORY` command xuống EA mỗi phút qua Redis → Gateway → TCP → EA. EA trả về trade history JSON.
- **D-02:** Cho open positions: cần thêm command mới `REQUEST_POSITIONS` trong EA để poll tất cả open positions hiện tại và trả về JSON.
- **D-03:** Tần suất: mỗi 60 giây 1 lần.

### Service Architecture
- **D-04:** Mở rộng `aureus-notifier` — tận dụng `TelegramSender`, rate limiter, Redis connection đã có.
- **D-05:** Thêm scheduled task (asyncio timer hoặc background loop) trong aureus-notifier để poll và gửi report mỗi phút.

### Message Format
- **D-06:** Gộp tất cả thông tin vào 1 message duy nhất, format đơn giản cho end user.
- **D-07:** Format mỗi position: `XAUUSD: -2.5$ (-20 pips) - 0.01`
  - Symbol: tên cặp tiền
  - Profit: $ (giá trị tuyệt đối P/L)
  - Pips: pips hiện tại
  - Volume: lot size
- **D-08:** Cuối message hiển thị **tổng profit** tất cả lệnh đang chạy.
- **D-09:** Nếu có order vừa close trong 1 phút gần nhất → thêm section "Recently Closed" vào cùng message.

### Telegram Bot
- **D-10:** Tạo bot mới riêng với token `8650116511:AAE25Gqc9WSVuZ53qrKp_l6b81_TTOVrjFk` — KHÔNG dùng chung bot signal/strategy hiện tại.
- **D-11:** Chat ID target: dùng cùng `TELEGRAM_DEFAULT_CHAT_ID` đã cấu hình.

### Agent's Discretion
- Exact message template (header, footer, emoji)
- Handling khi không có position nào đang mở (có gửi message trống hay skip)
- Error handling khi EA không phản hồi trong thời gian timeout

</decisions>

<specifics>
## Specific Ideas

- Format ví dụ từ user: `XAUUSD: -2.5$ (-20 pips) - 0.01`
- Thêm dòng tổng profit ở cuối: ví dụ "Tổng P/L: +15.3$"
- Message phải đơn giản, dễ đọc nhanh trên điện thoại

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### MT5 EA — Command handling
- `mql5/AureusProvider.mq5` L1030-1062 — `ExecuteTradeHistoryRequest` xử lý command REQUEST_TRADE_HISTORY, gọi `BuildTradeHistoryJSON`
- `mql5/AureusProvider.mq5` L1067-1168 — `ProcessIncomingCommands` dispatch commands nhận từ Gateway
- `mql5/AureusProvider.mq5` L1173-1223 — `OnTradeTransaction` push ORDER_CLOSED events realtime

### Gateway — Event routing
- `services/aureus-gateway/main.py` L73-120 — Order event models (OrderOpenedEvent, OrderClosedEvent, etc.)
- `services/aureus-gateway/main.py` L126-154 — `process_message` publish order events lên Redis `aureus:mt5:events`
- `services/aureus-gateway/main.py` L350-386 — `run_command_subscriber` forward commands từ Redis `aureus:mt5:commands` xuống EA qua TCP

### Notifier — Telegram infrastructure
- `services/aureus-notifier/telegram_bot.py` — `TelegramSender` class với retry + exponential backoff
- `services/aureus-notifier/main.py` — Main loop, Redis pub/sub subscription, dispatcher
- `services/aureus-notifier/formatters.py` — Message formatting patterns (HTML parse mode)
- `services/aureus-notifier/rate_limiter.py` — `RateLimitedDispatcher` queue-based dispatching

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `TelegramSender` (`aureus-notifier/telegram_bot.py`): Có thể tạo instance mới với bot token riêng, đã có retry/backoff.
- `RateLimitedDispatcher` (`rate_limiter.py`): Queue-based dispatch, có thể tái sử dụng hoặc tạo dispatcher riêng đơn giản hơn.
- `formatters.py`: Pattern format HTML message — tham khảo style khi viết formatter mới cho order report.

### Established Patterns
- Redis pub/sub channel `aureus:mt5:events` cho order events (ORDER_OPENED, ORDER_CLOSED).
- Redis pub/sub channel `aureus:mt5:commands` cho commands xuống EA (OPEN_ORDER, CLOSE_ORDER, REQUEST_TRADE_HISTORY).
- EA trả response qua TCP → Gateway publish lên Redis.

### Integration Points
- **aureus-notifier/main.py**: Thêm scheduled task bên cạnh pub/sub listener chính.
- **aureus-gateway/main.py**: Cần thêm model cho `POSITION_REPORT` response event từ EA.
- **AureusProvider.mq5**: Cần thêm command handler cho `REQUEST_POSITIONS` (poll `PositionsTotal`, `PositionGetSymbol`, etc.).

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 35-mt5-order-status-reporter*
*Context gathered: 2026-04-07*
