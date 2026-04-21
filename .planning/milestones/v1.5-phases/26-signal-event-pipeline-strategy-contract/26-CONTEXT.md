# Phase 26 — Signal Event Pipeline & Strategy Contract

## CONTEXT

**Phase:** 26
**Requirements:** NOTIF-01, STRAT-01, STRAT-02, STRAT-03, STRAT-04
**Goal:** Thiết lập foundation: signal engine publish events qua Redis pub/sub và mở rộng strategy contract với trade parameters.

---

## Decisions

### D1: Entry Contract — Extend `entry_type` enum

**Decision:** Giữ shape `entry_type` + `entry_policy` (đã canonical trong `REQUIRED_ORDER_PLAN_KEYS`). **Bổ sung enum validation** cho `entry_type`: `MARKET` | `LIMIT` | `STOP`.

**Rationale:**
- `entry_type` + `entry_policy` đã tồn tại xuyên suốt pipeline: `BaseStrategy.build_order_plan()` → `StrategyRegistry.evaluate_all()` → `orders.py` snapshot.
- STRAT-01 yêu cầu hỗ trợ market/limit/stop → cần extend enum, không chỉ giữ nguyên.
- Validation đặt tại `orders.py._build_order_plan_snapshot()` hoặc `registry.py` (reject sớm).

**Canonical refs:**
- `engine/strategies/base.py` line 97: default `MARKET`
- `engine/strategies/template.py` line 676: `build_order_plan()` emit `entry_type`
- `engine/snapshot_utils.py` line 57: `REQUIRED_ORDER_PLAN_KEYS` includes `entry_type`
- `engine/orders.py` line 299: snapshot builder reads `entry_type`

---

### D2: Position Sizing — `size` + `size_mode`, normalize naming

**Decision:** Canonical fields: `size_value` + `size_mode`. Strategy `build_order_plan()` **phải emit `size_value`** (không phải `size`) để match `REQUIRED_ORDER_PLAN_KEYS`. `lot_size` chỉ ở execution adapter layer.

**Enum cho `size_mode`:** `FIXED_UNITS` | `FIXED_LOT` | `RISK_PERCENT`

**Conversion ownership:** Execution adapter (aureus-trader) chịu trách nhiệm convert `RISK_PERCENT` → lot cụ thể (cần account equity).

**Rationale:**
- `REQUIRED_ORDER_PLAN_KEYS` yêu cầu `size_mode` + `size_value` (snapshot_utils.py line 65-66).
- Hiện `template.py` emit `size` nhưng `orders.py` map ngầm `size` → `size_value` (line 290). Cần chính thức hóa.
- `capital_risk_pct` đã tồn tại trong `template.py` line 672 → dùng khi `size_mode=RISK_PERCENT`.
- STRAT-03: "lot size / risk percentage" satisfied bởi `FIXED_LOT` + `RISK_PERCENT`.

**Canonical refs:**
- `engine/snapshot_utils.py` lines 65-66: `size_mode`, `size_value`
- `engine/strategies/template.py` line 657: `size` emit
- `engine/orders.py` lines 290-291: `size_value = order_plan.get("size")`

---

### D3: Magic Number — Static mapping per strategy trong DB

**Decision:** `magic_number` là **static mapping** lưu trong DB table `aureus_strategy_templates` (thêm column `magic_number`). **Không dùng hash.** Adapter chỉ đọc magic_number từ config, không tự sinh.

**Rationale:**
- STRAT-04: "Magic number per strategy cho MT5 order tracking" → per strategy, stable qua thời gian.
- PITFALLS.md: "Use `magic` number to distinguish bot orders from manual trades".
- Hash approach (strategy_id + symbol + env) không stable qua deploy → gãy MT5 history query.
- MT5 `magic` là ulong, static mapping đảm bảo deterministic + queryable.

**Implementation note:** Thêm column `magic_number BIGINT` vào `aureus_strategy_templates`. Migration script populate giá trị default dựa trên `strategy_id * 1000`.

---

### D4: Publish Channel — Redis Pub/Sub trước, Stream defer

**Decision:** Phase 26 triển khai **Redis pub/sub channel** `aureus:signals:{symbol}` cho signal events (NOTIF-01). `decisions` stream defer sang phase sau.

**Rationale:**
- NOTIF-01: "Signal engine publishes signal events **qua Redis pub/sub**" → requirement nói rõ pub/sub.
- Stream (`XADD`) là persistent + consumer group → phù hợp cho internal processing (đã có `aureus:stream:{symbol}:signals`).
- Pub/Sub (`PUBLISH`) là fire-and-forget → phù hợp cho downstream notification (aureus-notifier Phase 27).
- Thêm stream mới ở Phase 26 tăng complexity mà chưa có consumer.
- Dọn rejection ra khỏi `orders` stream có thể defer khi có `decisions` stream thực sự.

**Pub/Sub payload shape:**
```json
{
  "type": "SIGNAL_EVENT" | "STRATEGY_MATCH",
  "symbol": "XAUUSD",
  "t": 1710000060,
  "data": { ... }
}
```

**Canonical refs:**
- `engine/strategy_executor.py` lines 85-91: rejection emit vào orders stream
- `engine/live_engine.py` line 661: signal stream XADD

---

### D5: SL/TP — Bỏ hardcoded fallback, explicit reject

**Decision:** 
1. Strategy phải cung cấp SL/TP config (`{mode, value}`) trong `exit_config` hoặc `trade_execution`.
2. **Bỏ hardcoded fallback** `300/10000.0` trong `_calculate_sl_tp()`.
3. Nếu strategy không cấu hình → `_calculate_sl_tp()` trả `(None, None)` → order bị reject bởi `_missing_order_plan_keys()` (behavior đã tồn tại).
4. **Log warning** khi enrichment xảy ra (sl_value/tp_value bị override từ calc).

**Rationale:**
- STRAT-02: "Strategy output chứa SL/TP values" → strategy phải chủ động cấu hình.
- `REQUIRED_ORDER_PLAN_KEYS` đã bắt buộc `sl_mode`/`sl_value`/`tp_mode`/`tp_value`.
- Hardcoded 300 pips fallback nguy hiểm cho index/crypto symbols.
- Feature flag approach redundant — validation pipeline đã reject khi thiếu.

**2 layer rõ ràng:**
- `order_plan.sl` = config object `{mode: "FIXED_PIPS", value: 300}`
- `order.sl` = computed absolute price (output của `_calculate_sl_tp`)

**Canonical refs:**
- `engine/orders.py` lines 325-384: `_calculate_sl_tp()` với hardcoded defaults
- `engine/orders.py` lines 261-267: `_missing_order_plan_keys()` validation
- `engine/snapshot_utils.py` lines 59-62: `sl_mode`, `sl_value`, `tp_mode`, `tp_value`

---

## Carry-forward from prior phases

| Source | Decision | Relevance |
|--------|----------|-----------|
| Phase 21 | `.venv` virtualenv for aureus-signal | Dev environment setup |
| Phase 22 | `DecisionProvider` ABC pattern | Strategy contract inherits this abstraction |
| Phase 24 | Provider mode routing (redis_primary, ta_shadow, ta_primary) | Signal flow context |
| Phase 25 | Circuit breaker + drift telemetry | Error handling patterns |

## Todos matched to Phase 26

_(Từ GSD todo match — 0 active todos matched)_

---

## Success Criteria (Updated)

1. ✅ Signal engine phát signal events lên Redis **pub/sub** channel khi có signal mới
2. ✅ Strategy contract hỗ trợ `entry_type` enum: MARKET/LIMIT/STOP + validation
3. ✅ Strategy output chứa SL/TP config; **bỏ hardcoded fallback** trong orders layer
4. ✅ `size_value` + `size_mode` normalized; `FIXED_LOT` + `RISK_PERCENT` supported
5. ✅ `magic_number` static mapping trong DB per strategy
6. ✅ Backward compatibility: existing strategies tiếp tục hoạt động
7. ✅ Unit tests cho contract mới và backward compat

---
*Context created: 2026-04-05*
