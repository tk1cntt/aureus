# Phase 26 — Technical Research

**Date:** 2026-04-05
**Scope:** Signal Event Pipeline & Strategy Contract Enhancement
**Requirements:** NOTIF-01, STRAT-01, STRAT-02, STRAT-03, STRAT-04

---

## 1. Entry Type Pipeline Flow

**Current state:** `entry_type` flows through 4 layers:

```
base.py:97          → default "MARKET"
template.py:676     → reads from trade_execution > exit_config > "MARKET"
registry.py:473     → copies to accepted output: order_plan.get("entry_type", "MARKET")
orders.py:299       → _build_order_plan_snapshot reads entry_type
snapshot_utils.py:57 → REQUIRED_ORDER_PLAN_KEYS validates presence
```

**Finding:** No enum validation exists anywhere. Invalid values pass silently through entire pipeline.

**Risk:** LIMIT/STOP orders need different handling in aureus-trader (Phase 29) — if invalid values leak now, downstream breaks.

---

## 2. Size Normalization — Naming Mismatch

**Current mapping:**
| Layer | Key emitted | Key consumed |
|-------|-------------|--------------|
| `base.py:100` | `"size": 1.0` | — |
| `template.py:657` | `"size": float(...)` | — |
| `registry.py:475` | `"size": order_plan.get("size")` | downstream trigger |
| `orders.py:290` | — | `size_value = order_plan.get("size")` |
| `snapshot_utils.py:66` | — | validates `"size_value"` |

**Finding:** `template.py` emits `size`, `orders.py` reads `size` but stores as `size_value`, `snapshot_utils` validates `size_value`. Implicit mapping works but fragile.

**Decision impact:** `size_mode` defaults to `FIXED_UNITS` everywhere. No strategy currently sets other modes → safe to extend.

---

## 3. SL/TP Hardcoded Fallbacks — Full Audit

**File:** `orders.py` `_calculate_sl_tp()` lines 325-384

| Line | Hardcode | Context | Danger |
|------|----------|---------|--------|
| 337 | `sl_cfg.get('value', 300)` | FIXED_PIPS SL default | 30 pip SL for ALL symbols |
| 339 | `sl_cfg.get('value', 300)` | FIXED_PIPS SL (JPY) | 3 pip SL for JPY (wrong!) |
| 371 | `pips = 300 / 10000.0` | Fallback when SIGNAL_LOW/HIGH fails | Silent 30 pip SL |
| 377 | `tp_cfg.get('value', 1.5)` | RR TP default | 1.5 RR assumed |
| 381 | `tp_cfg.get('value', 500)` | FIXED_PIPS TP default | 50 pip TP |

**Risk:** Gold (XAUUSD) trades with 30 pip SL = $3.00 stop → absurdly tight. Index trades (NAS100) with 30 pip stop = meaningless.

---

## 4. Magic Number — DB Schema

**Table:** `aureus_strategy_templates`

```sql
-- Current columns (from registry.py:197):
SELECT t.id, t.name, t.config, t.min_score
FROM aureus_strategy_templates t
```

**Finding:** No `magic_number` column exists. `registry.py:load_by_ids` query must be extended.

**Constraint:** `magic_number` must be:
- `BIGINT` (MT5 ulong is 64-bit)
- Unique per strategy (not per symbol-strategy pair)
- Stable across deploys (no hashing)
- Formula for auto-populate: `strategy_id * 1000` (gives room for 999 sub-IDs per strategy)

---

## 5. Redis Pub/Sub Integration Point

**File:** `strategy_executor.py`

**Current data flow:**
```
line 377: strategy_results = registry.evaluate_all(...)
line 394: strategy_results = enrich_strategy_decisions_with_contract_metadata(...)
line 406: await emit_registry_rejections(r, symbol, enriched_rejections)
line 420: pending_order = await trade_manager.process_triggers(...)
line 430: for res in strategy_results: logger.info(...)
```

**Best integration point:** After enrichment (line 397), before process_triggers (line 420).
- We have enriched strategy_results with metadata
- We haven't yet processed orders (no side effects yet)
- Notification consumers need the enriched data

**Signal events:** At `live_engine.py` after XADD to signal stream — publish to pub/sub for real-time notification.

---

## 6. Registry Accepted Output — Gap Found

**Critical finding:** `registry.py:463-484` accepted dict is MISSING new fields:

```python
accepted.append({
    ...
    "size": order_plan.get("size"),        # ← only "size", no "size_value"
    "sl": order_plan.get("sl"),            # ← config object, not value
    "tp": order_plan.get("tp"),            # ← config object, not value
    # MISSING: "size_value", "size_mode", "magic_number"
})
```

**Impact:** `strategy_executor.py` passes `strategy_results` (registry output) to `trade_manager.process_triggers()` which calls `_build_order_plan_snapshot()`. The snapshot builder reads from `trigger.get("order_plan")` — but registry puts `order_plan` as nested dict at key `"order_plan"`.

So the flow is:
1. Registry accepted output at line 483: `"order_plan": order_plan`
2. `orders.py:275`: `order_plan = trigger.get("order_plan")`
3. `orders.py:290`: `size_value = order_plan.get("size")`

**Conclusion:** `_build_order_plan_snapshot` reads from the nested `order_plan` dict, NOT from the top-level trigger. So `size_value`/`size_mode`/`magic_number` changes in `template.py:build_order_plan()` will flow correctly through the nested `order_plan` key. The top-level `"size"` in registry is for logging/notification only.

**However:** `registry.py:475` should also pass `size_value`/`size_mode`/`magic_number` to top level for pub/sub publisher to read.

---

## 7. Existing Test Coverage

| Test file | Covers | Phase 26 impact |
|-----------|--------|-----------------|
| `test_strategy_contract_v1.py` | V1 contract shape | Must still pass |
| `test_decision_trace_schema.py` | Trace payload validation | Uses `REQUIRED_ORDER_PLAN_KEYS` |
| `test_template_strategy.py` | TemplateStrategy evaluate | Affected by `build_order_plan` change |
| `test_strategy_context_filters.py` | Context filter logic | Not affected |

---

## Validation Architecture

### Unit Tests
1. `test_strategy_contract_v2.py` — entry_type enum, size normalization, magic_number, backward compat
2. `test_signal_event_publisher.py` — pub/sub publish, channel format, failure handling

### Integration Verification
```bash
# All existing tests pass:
python -m pytest tests/test_strategy_contract_v1.py tests/test_decision_trace_schema.py tests/test_template_strategy.py -v

# New tests pass:
python -m pytest tests/test_strategy_contract_v2.py tests/test_signal_event_publisher.py -v

# Grep: no hardcoded fallbacks remain
grep -c "sl_cfg.get('value', 300)" engine/orders.py  # → 0
grep -c "tp_cfg.get('value', 1.5)" engine/orders.py  # → 0
```

---
*Research date: 2026-04-05*
