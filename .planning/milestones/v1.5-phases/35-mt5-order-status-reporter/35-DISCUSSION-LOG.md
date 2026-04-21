# Phase 35: MT5 Order Status Reporter - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-07
**Phase:** 35-mt5-order-status-reporter
**Areas discussed:** Data Flow, Service Architecture, Message Format, Bot/Channel Target

---

## Data Flow Architecture

| Option | Description | Selected |
|--------|-------------|----------|
| EA poll & push | EA poll positions mỗi phút → push JSON qua TCP → Gateway → Redis | |
| Python REQUEST command | Python service gửi REQUEST_TRADE_HISTORY command xuống EA mỗi phút | ✓ |
| MT5 Python lib | Kết nối trực tiếp MT5 via Python lib (Out of Scope) | |

**User's choice:** Python service gửi REQUEST command xuống EA
**Notes:** User chọn cách 2 — service chủ động request, EA phản hồi. Protocol REQUEST_TRADE_HISTORY đã tồn tại trong EA.

---

## Service Architecture

| Option | Description | Selected |
|--------|-------------|----------|
| Mở rộng aureus-notifier | Tận dụng TelegramSender + rate limiter đã có | ✓ |
| Service mới riêng | Tạo service mới tách biệt | |

**User's choice:** Mở rộng aureus-notifier
**Notes:** Tận dụng infrastructure Telegram hiện có.

---

## Message Format

| Option | Description | Selected |
|--------|-------------|----------|
| 1 message gộp | Tất cả positions + closed orders trong 1 message | ✓ |
| Message riêng | Mỗi order 1 message riêng | |

**User's choice:** Gộp 1 message, format đơn giản
**Notes:** Ví dụ format: `XAUUSD: -2.5$ (-20 pips) - 0.01`. Thêm tổng profit các lệnh đang chạy.

---

## Bot/Channel Target

| Option | Description | Selected |
|--------|-------------|----------|
| Bot hiện tại | Dùng chung bot signal/strategy | |
| Bot mới riêng | Tạo bot mới với token 8650116511:... | ✓ |

**User's choice:** Tạo bot mới riêng
**Notes:** Token `8650116511:AAE25Gqc9WSVuZ53qrKp_l6b81_TTOVrjFk`

---

## Agent's Discretion

- Message template chi tiết (header, footer, emoji)
- Handling khi không có position nào
- Error handling/timeout

## Deferred Ideas

None — discussion stayed within phase scope.
