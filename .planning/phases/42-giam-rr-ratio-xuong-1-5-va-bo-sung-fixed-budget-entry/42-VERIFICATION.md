---
phase: 42-giam-rr-ratio-xuong-1-5-va-bo-sung-fixed-budget-entry
verified: 2026-04-14T12:00:00Z
status: passed
score: 9/9 must-haves verified
overrides_applied: 0
gaps: []
deferred: []
human_verification: []
---

# Phase 42: Giảm RR ratio xuống 1.5 và bổ sung FIXED_BUD entry (50$) Verification Report

**Phase Goal:** Chuyển TP RR ratio mặc định của tất cả strategy xuống 1.5. Bổ sung cơ chế FIXED_BUDGET ($50) tự tính lot size dựa trên SL distance và entry price khi gửi lệnh sang MT5.
**Verified:** 2026-04-14
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| #   | Truth | Status | Evidence |
| --- | ----- | ------ | -------- |
| 1 | Backtest simulated_orders.py default RR fallback is 1.5 (not 2.0) | ✓ VERIFIED | `simulated_orders.py:208` — `tp_cfg.get('value', 1.5)` with comment `# default RR 1.5 per D-01, D-03`. Grep confirms zero occurrences of `get('value', 2.0)` in production code. |
| 2 | All 16 seed strategies have tp.value = 1.5 (no exceptions) | ✓ VERIFIED | `seed_strategies.py` — exactly 16 occurrences of `"value": 1.5` in tp config. Zero occurrences of `"value": 2.0`. SESSION_SWEEP_BEAR (line 124) confirmed at 1.5. |
| 3 | SESSION_SWEEP_BEAR also uses RR 1.5 (D-02, no special treatment) | ✓ VERIFIED | Line 124-137 in seed_strategies.py — tp config is `"value": 1.5`, same as all others. |
| 4 | VALID_SIZE_MODES chứa RISK_FIXED_AMOUNT | ✓ VERIFIED | `snapshot_utils.py:72` — `VALID_SIZE_MODES = ("FIXED_UNITS", "FIXED_LOT", "RISK_PERCENT", "RISK_FIXED_AMOUNT")` |
| 5 | risk_amount propagate qua registry → orders → publisher → order_builder → MT5 | ✓ VERIFIED | registry.py:489 (`order_plan.get("risk_amount")`), signal_event_publisher.py:72 (`strategy_result.get("risk_amount")`), orders.py:281 (`order_plan_snapshot["risk_amount"] = risk_amount`), order_builder.py:62 (`risk_amount if risk_amount else 50.0`), AureusProvider.mq5:979 (`ParseJSONDouble(raw, "risk_amount")`) |
| 6 | orders.py xử lý đúng flow mới: side → entry_price → SL/TP → validate (D-13, D-14) | ✓ VERIFIED | orders.py:199 (side), line 209 (entry_price via `_calculate_entry_price`), line 213 (SL/TP via `_calculate_sl_tp` with `entry_price_override=computed_entry`), line 235 (validate `missing_order_plan_keys` after SL/TP enrichment). KHÔNG có `continue` sau SL/TP=None block (lines 215-226 chỉ enrich). |
| 7 | orders.py set volume=0 + risk_amount khi RISK_FIXED_AMOUNT | ✓ VERIFIED | orders.py:279-282 — `if size_mode == "RISK_FIXED_AMOUNT"`: sets `risk_amount` (with $50 fallback) and `size_value = 0` as placeholder |
| 8 | order_builder.py forward RISK_FIXED_AMOUNT sang MT5 command | ✓ VERIFIED | order_builder.py:60-64 — `if size_mode == "RISK_FIXED_AMOUNT": command["size_mode"] = size_mode; command["risk_amount"] = risk_amount if risk_amount else 50.0; command["volume"] = 0` |
| 9 | MT5 CalculateLotFromBudget dùng Ask/Bid thực tế + auto-adjust budget | ✓ VERIFIED | AureusProvider.mq5:874-876 (Ask/Bid real-time), line 910 (`lot = riskAmount / riskPerLot`), lines 920/936 (auto-adjust loop), lines 948-952 (normalize + clamp), lines 982/1027 (ExecuteOpenOrder integration) |

**Score:** 9/9 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `services/aureus-signal/engine/simulated_orders.py` | Backtest TP calculation with RR 1.5 default fallback | ✓ VERIFIED | Line 208: `get('value', 1.5)` — full SL/TP logic with correct default |
| `services/aureus-signal/engine/strategies/seed_strategies.py` | 16 seed strategies all with tp.value = 1.5 | ✓ VERIFIED | 16/16 strategies confirmed at value=1.5, zero exceptions |
| `services/aureus-signal/engine/snapshot_utils.py` | VALID_SIZE_MODES tuple với RISK_FIXED_AMOUNT | ✓ VERIFIED | Line 72: tuple includes `"RISK_FIXED_AMOUNT"` |
| `services/aureus-signal/engine/strategies/registry.py` | risk_amount trong accepted output | ✓ VERIFIED | Line 489: `"risk_amount": order_plan.get("risk_amount")` |
| `services/aureus-signal/engine/signal_event_publisher.py` | risk_amount trong STRATEGY_MATCH event data | ✓ VERIFIED | Line 72: `"risk_amount": strategy_result.get("risk_amount")` |
| `services/aureus-signal/engine/orders.py` | RISK_FIXED_AMOUNT handling + flow mới | ✓ VERIFIED | Lines 275-283: RISK_FIXED_AMOUNT block, lines 199-235: correct flow order |
| `services/aureus-trader/order_builder.py` | build_order_command forwarding RISK_FIXED_AMOUNT | ✓ VERIFIED | Lines 60-64: size_mode + risk_amount + volume=0 forwarding |
| `mql5/AureusProvider.mq5` | CalculateLotFromBudget() với auto-adjust budget | ✓ VERIFIED | Lines 869-959: full implementation, lines 982/1025-1027: ExecuteOpenOrder integration |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| `seed_strategies.py` (tp.value=1.5) | `simulated_orders.py._calculate_sl_tp` | `tp_cfg.get('value', 1.5)` | ✓ WIRED | Line 208: seed provides 1.5, fallback also 1.5 |
| `registry.py` (risk_amount) | `signal_event_publisher.py` | accepted dict → publish_strategy_match | ✓ WIRED | registry.py:489 → publisher.py:72, both use `"risk_amount"` key |
| `signal_event_publisher.py` (risk_amount) | `order_builder.py` | Redis STRATEGY_MATCH → match_event["data"] | ✓ WIRED | publisher.py:72 serializes → order_builder.py:41 deserializes |
| `order_builder.py` (RISK_FIXED_AMOUNT cmd) | `AureusProvider.mq5` | TCP JSON → ParseJSONDouble/ParseJSONString | ✓ WIRED | order_builder.py:60-64 → mq5:979/982 |
| `orders.py` (side) | `orders.py` (entry_price) | `_calculate_entry_price(side, ...)` | ✓ WIRED | Line 199 determines side, line 209 calls with side |
| `orders.py` (entry_price) | `orders.py` (SL/TP) | `entry_price_override=computed_entry` | ✓ WIRED | Line 209 computes, line 213 passes as override |
| `orders.py` (SL/TP) | `orders.py` (validate) | Enrichment before missing_keys check | ✓ WIRED | Lines 229-232 enrich, line 235 validates |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| `orders.py` RISK_FIXED_AMOUNT block | `risk_amount` | `size_value` from order_plan_snapshot (strategy config) | ✓ FLOWING | Line 280: `size_value if isinstance(...) else 50.0` — reads from strategy config, fallback to $50 |
| `signal_event_publisher.py` | `risk_amount` | `strategy_result` dict (from registry accepted output) | ✓ FLOWING | Line 72: `strategy_result.get("risk_amount")` — populated by registry.py:489 |
| `order_builder.py` | `risk_amount` | `match_event["data"]` (from Redis pub/sub) | ✓ FLOWING | Line 41: `data.get("risk_amount")` — deserialized from publisher |
| `AureusProvider.mq5` | `riskAmount` | JSON command via TCP socket | ✓ FLOWING | Line 979: `ParseJSONDouble(raw, "risk_amount")` → used in CalculateLotFromBudget |
| `AureusProvider.mq5` CalculateLotFromBudget | `lot` | `SymbolInfoDouble(SYMBOL_ASK/BID)` + `slDistance * contractSize` | ✓ FLOWING | Lines 874-876: real market prices; line 910: real formula; lines 948-952: normalize/clamp |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| All 16 seed strategies have RR 1.5 | grep -c '"value": 1.5' seed_strategies.py | 16 | ✓ PASS |
| No RR 2.0 in production code | grep -rn "get('value', 2.0)" engine/ | No matches | ✓ PASS |
| VALID_SIZE_MODES includes RISK_FIXED_AMOUNT | grep '"RISK_FIXED_AMOUNT"' snapshot_utils.py | Line 72 match | ✓ PASS |
| RISK_FIXED_AMOUNT block in orders.py | grep 'RISK_FIXED_AMOUNT' orders.py | Lines 275, 279, 283 | ✓ PASS |
| MT5 CalculateLotFromBudget exists | grep 'CalculateLotFromBudget' AureusProvider.mq5 | Lines 869, 1027 | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ----------- | ----------- | ------ | -------- |
| RR-01 | ROADMAP | RR ratio giảm xuống 1.5 cho tất cả strategy | ✓ SATISFIED | seed_strategies.py: 16/16 at 1.5; simulated_orders.py:208 default 1.5 |
| ORDER-02 | ROADMAP | Tạo và gửi market order xuống MT5 qua TCP | ✓ SATISFIED | order_builder.py builds OPEN_ORDER command; AureusProvider.mq5 ExecuteOpenOrder sends OrderSend with real-time lot calc |
| ORDER-03 | ROADMAP | Tạo và gửi pending order (limit/stop) xuống MT5 | ✓ SATISFIED | AureusProvider.mq5 lines 1112-1127 handles LIMIT/STOP order types; RISK_FIXED_AMOUNT applies to market orders (calcVolumeOnMT5 at line 982) |
| ORDER-04 | ROADMAP | AureusProvider.mq5 nhận order commands và execute OrderSend() | ✓ SATISFIED | ExecuteOpenOrder (line 965) parses JSON commands, calculates lot via CalculateLotFromBudget (line 1027), executes OrderSend (line 1177) |
| STRAT-03 | ROADMAP | Strategy output chứa lot size / risk percentage | ✓ SATISFIED | registry.py:488-489 outputs `size_value` + `risk_amount`; orders.py:279-282 handles RISK_FIXED_AMOUNT with budget; signal_event_publisher.py:70-72 includes all in event |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| `services/aureus-signal/tests/test_strategy_trigger_lifecycle.py` | 71 | `"value": 2.0` in test fixture | ℹ️ Info | Test fixture — intentionally tests with RR 2.0, not production code. Expected behavior. |
| `services/aureus-signal/tests/test_seed_strategies_activation.py` | 71,92,114,136,157 | `"value": 2.0` in test fixtures | ℹ️ Info | Test fixtures — testing activation with various RR values, not production code. |
| `services/aureus-signal/tests/test_pivot_sl.py` | 93-146 | `"value": 2.0` in test fixtures | ℹ️ Info | Test fixtures — verifying SL/TP logic with different RR values. |
| `services/aureus-signal/tests/test_strategy_choch_triggers.py` | 27 | `"value": 2.0` in test fixture | ℹ️ Info | Test fixture — not production code. |

No production code contains RR 2.0. Test fixtures are intentionally configured with various RR values for comprehensive testing coverage.

### Human Verification Required

_No items — all truths verified programmatically._

### Deferred Items

_No items — all phase goals achieved within this phase._

---

_Verified: 2026-04-14T12:00:00Z_
_Verifier: Claude (gsd-verifier)_
