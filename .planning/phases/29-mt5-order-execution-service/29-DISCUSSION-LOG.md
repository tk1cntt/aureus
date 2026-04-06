# Phase 29: MT5 Order Execution Service - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-06
**Phase:** 29-mt5-order-execution-service
**Areas discussed:** Order Queue & Disconnect Resilience, Idempotency Key Design, Retry & Error Recovery, Strategy Match → Order Mapping

---

## Order Queue & Disconnect Resilience

| Option | Description | Selected |
|--------|-------------|----------|
| In-memory asyncio.Queue | Fast, simple, like aureus-notifier pattern | |
| Redis List | Persistent, survives service restart, RPUSH/LPOP | ✓ |
| Redis Stream + consumer group | Most robust, but overkill for single consumer | |

**User's choice:** Agent suggest tốt nhất (Redis List)
**Notes:** User chọn "suggest tốt nhất" cho tất cả areas. Redis List được chọn vì balance giữa durability (persist qua restart) và simplicity (không cần consumer groups). In-memory queue không đủ reliable cho orders (mất orders khi crash). Redis Stream overkill cho single-consumer scenario.

---

## Idempotency Key Design

| Option | Description | Selected |
|--------|-------------|----------|
| UUID random | Simple generation, but needs separate "already processed" check | |
| Hash-based deterministic | `md5(strategy_id:symbol:signal_ts:direction)` → naturally idempotent | ✓ |
| DB-backed dedup table | Most robust, but adds PostgreSQL dependency for Phase 29 | |

**User's choice:** Agent suggest tốt nhất (Hash-based deterministic + Redis TTL)
**Notes:** Deterministic hash đảm bảo cùng strategy match event → cùng cmd_id → exactly-once semantics tự nhiên. Redis key-per-order với 24h TTL đơn giản và đủ cho trading day cycle. Complement EA-side dedup (Phase 28) cho defense-in-depth.

---

## Retry & Error Recovery

| Option | Description | Selected |
|--------|-------------|----------|
| Retry all errors | Simple but wasteful — retries INSUFFICIENT_MARGIN, INVALID_STOPS | |
| Selective retry | Only retry transient errors (MARKET_CLOSED, timeout, busy) | ✓ |
| No retry | EA fail-fast, server also fail-fast — simplest but fragile | |

**User's choice:** Agent suggest tốt nhất (Selective retry, max 3, exponential backoff)
**Notes:** Selective retry avoids wasting resources on non-recoverable errors (INSUFFICIENT_MARGIN cần user top-up, INVALID_STOPS cần fix SL/TP calc). Max 3 retries + exponential backoff (2s, 4s, 8s) ≈ 15s total — reasonable for transient issues. Persistent failure → alert via existing notification pipeline.

---

## Strategy Match → Order Mapping

| Option | Description | Selected |
|--------|-------------|----------|
| Direct field mapping | Straight map from strategy match to OPEN_ORDER command | ✓ |
| Intermediate order model | Create OrderIntent model, then convert to command | |
| Config-driven mapping | YAML mapping config for field transforms | |

**User's choice:** Agent suggest tốt nhất (Direct field mapping + v1 FIXED_LOT only)
**Notes:** Direct mapping là simplest approach — fields already aligned between Phase 26 strategy contract và Phase 28 command schema. RISK_PERCENT → lot conversion deferred (needs MT5 account equity). v1 validates size_mode == FIXED_LOT, rejects RISK_PERCENT with warning log.

---

## Agent's Discretion

- Service internal structure, file layout, Docker config
- Logging verbosity levels (INFO vs DEBUG)
- Subscription channel pattern (all symbols vs per-symbol)

## Deferred Ideas

- RISK_PERCENT volume conversion (needs MT5 account equity)
- Order modification (ORDER-F01)
- Partial close (ORDER-F02)
- Dead letter queue (v1 uses Telegram alert instead)
