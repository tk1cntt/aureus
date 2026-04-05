---
phase: "27"
plan: 01
name: "Telegram Notification Service"
subsystem: "aureus-notifier"
tags: ["notification", "telegram", "redis", "docker"]
dependency_graph:
  requires: ["Redis pub/sub (aureus:signals:{symbol})", "python-telegram-bot v21+", "Docker"]
  provides: ["Telegram notifications for SIGNAL_EVENT and STRATEGY_MATCH"]
  affects: ["docker-compose.dev.yml (new service)", ".env.example (new vars)"]
tech_stack:
  added: ["python-telegram-bot==21.0", "redis>=5.0.0", "python-dotenv==1.0.0"]
  patterns: ["async/await pub/sub", "queue-based rate limiting", "exponential backoff retry"]
key_files:
  created:
    - services/aureus-notifier/main.py
    - services/aureus-notifier/config.py
    - services/aureus-notifier/telegram_bot.py
    - services/aureus-notifier/formatters.py
    - services/aureus-notifier/rate_limiter.py
    - services/aureus-notifier/Dockerfile
    - services/aureus-notifier/requirements.txt
    - services/aureus-notifier/tests/test_formatters.py
    - services/aureus-notifier/tests/test_config.py
    - services/aureus-notifier/tests/test_rate_limiter.py
    - services/aureus-notifier/__init__.py
    - services/aureus-notifier/tests/__init__.py
    - .env.example
  modified:
    - docker-compose.dev.yml
decisions:
  - "Used python-telegram-bot v21+ async API for non-blocking Telegram calls"
  - "Per-chat asyncio.Queue(maxsize=100) for rate limiting at 1 msg/2s per chat"
  - "Exponential backoff 2s→4s→8s for TelegramError, server-suggested retry for RetryAfter"
  - "Redis hash keys for filter/route config with pub/sub reload (no restart needed)"
  - "HTML escaping via html.escape() to prevent XSS in user-provided signal data"
  - "Queue overflow drops oldest message (not newest) to preserve latest signals"
metrics:
  duration: "~15 min"
  completed_date: "2026-04-06"
  tests: "34 passed, 0 failed"
  files_created: 13
  files_modified: 1
---

# Phase 27 Plan 01: Telegram Notification Service Summary

**One-liner:** Telegram notification service subscribing to Redis pub/sub channels, filtering events, formatting HTML messages with emoji, rate-limited at 1 msg/2s per chat with exponential backoff retry, integrated into docker-compose.dev.yml.

## What was built

A standalone Python microservice (`aureus-notifier`) that:

1. **Subscribes** to Redis pub/sub channels `aureus:signals:{symbol}` for all configured symbols
2. **Filters** events using configurable criteria (enabled, signal types, symbols, strategies) loaded from Redis hash `aureus:notifier:filters`
3. **Routes** messages to multiple Telegram chats based on route config from Redis hash `aureus:notifier:routes`
4. **Formats** messages as HTML with emoji:
   - 📊 SIGNAL ALERT: symbol, time, session, active signals as bullet list
   - 🎯 STRATEGY MATCH: symbol, strategy, direction (🟢BUY/🔴SELL), entry type, SL/TP, size, reason
5. **Rate limits** with per-chat asyncio.Queue (max 100), 1 msg/2s dispatch loop
6. **Retries** failed Telegram API calls with exponential backoff (2s→4s→8s, max 3 attempts)
7. **Reloads config at runtime** via `aureus:cmd:notifier_config` pub/sub channel (no restart)

## Test Results

| Test File | Tests | Passed | Failed |
|-----------|-------|--------|--------|
| test_formatters.py | 8 | 8 | 0 |
| test_config.py | 14 | 14 | 0 |
| test_rate_limiter.py | 12 | 12 | 0 |
| **Total** | **34** | **34** | **0** |

## Commits

| # | Hash | Message |
|---|------|---------|
| 1 | c314cef | test(27-01): add failing tests for signal/strategy formatters |
| 2 | ab74680 | feat(27-01): implement config loader with Redis filter/route management |
| 3 | ef2437f | feat(27-01): add Telegram Bot wrapper with retry and exponential backoff |
| 4 | 1cb814e | feat(27-01): add queue-based rate limiter dispatcher |
| 5 | 75c9997 | feat(27-01): add main.py entry point with Redis pub/sub subscriber |
| 6 | 9fce9c9 | chore(27-01): add Docker config and docker-compose integration |
| 7 | c7e30c0 | chore(27-01): add __init__.py package files |

## Deviations from Plan

None - plan executed exactly as written.

## Security Notes

- HTML special characters escaped in all user-provided strings (signal names, values, strategy names, reason codes)
- TELEGRAM_BOT_TOKEN never logged; injected via environment variable
- Bot token documented in .env.example with empty default (never hardcoded)

## Known Stubs

None. All functionality is wired end-to-end.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: network_endpoint | main.py | Subscribes to `aureus:signals:{symbol}` Redis pub/sub channels (T-27-01 mitigated) |
| threat_flag: secret_injection | main.py, docker-compose.dev.yml | TELEGRAM_BOT_TOKEN passed via env var (T-27-02 mitigated) |
| threat_flag: queue_overflow | rate_limiter.py | Queue(maxsize=100) per chat, drops oldest on overflow (T-27-03 mitigated) |

## Self-Check: PASSED

All files verified present, all 34 tests passed, all commits recorded.
