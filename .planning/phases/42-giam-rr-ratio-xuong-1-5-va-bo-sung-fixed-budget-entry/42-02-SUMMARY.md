---
phase: 42-giam-rr-ratio-xuong-1-5-va-bo-sung-fixed-budget-entry
plan: 02
type: verify
autonomous: true
tags:
  - RISK_FIXED_AMOUNT
  - pipeline-verification
  - lot-calculation
  - SL-TP-flow

dependency_graph:
  requires: []
  provides:
    - "Verified RISK_FIXED_AMOUNT pipeline completeness"
    - "Verified MT5 CalculateLotFromBudget correctness"
    - "Verified new order flow (side→entry→SL/TP→validate)"
  affects:
    - snapshot_utils.py
    - registry.py
    - signal_event_publisher.py
    - orders.py
    - order_builder.py
    - AureusProvider.mq5

tech-stack:
  added: []
  patterns:
    - "Pipeline verification via grep assertions"
    - "Layered forwarding: registry→publisher→order_builder→MT5"

key-files:
  created: []
  modified: []  # Verify-only plan — no code changes needed

decisions: []

metrics:
  tasks_completed: 4
  tasks_planned: 4
  duration: "~15 minutes"
  completed_date: "2026-04-14"
---

# Phase 42 Plan 02: Verify RISK_FIXED_AMOUNT Pipeline — Summary

**One-liner:** Toàn bộ pipeline RISK_FIXED_AMOUNT đã được verify pass — risk_amount propagate đúng qua registry → publisher → orders → order_builder → MT5, CalculateLotFromBudget đúng công thức, flow SL/TP mới đúng thứ tự.

## Task Completion

| Task | Name | Commit | Files | Status |
|------|------|--------|-------|--------|
| 1 | Verify VALID_SIZE_MODES + risk_amount propagation | 1f62cd5 | snapshot_utils.py, registry.py, signal_event_publisher.py, orders.py | PASS |
| 2 | Verify order_builder.py forwarding RISK_FIXED_AMOUNT | 03a1568 | order_builder.py | PASS |
| 3 | Verify MT5 CalculateLotFromBudget + auto-adjust | (no-commit, verified existing code) | AureusProvider.mq5 | PASS |
| 4 | Verify flow side→entry→SL/TP→validate (D-13, D-14) | f623d26 | orders.py | PASS |

## Verification Results

### Task 1: VALID_SIZE_MODES + risk_amount propagation

- **snapshot_utils.py:72** — `VALID_SIZE_MODES = ("FIXED_UNITS", "FIXED_LOT", "RISK_PERCENT", "RISK_FIXED_AMOUNT")` ✅
- **registry.py:489** — `"risk_amount": order_plan.get("risk_amount")` trong accepted dict ✅
- **signal_event_publisher.py:72** — `"risk_amount": strategy_result.get("risk_amount")` trong publish_strategy_match data ✅
- **orders.py:281-282** — `order_plan_snapshot["risk_amount"] = risk_amount`, `order_plan_snapshot["size_value"] = 0` trong RISK_FIXED_AMOUNT block ✅

### Task 2: order_builder.py forwarding

- **order_builder.py:60** — `if size_mode == "RISK_FIXED_AMOUNT":` ✅
- **order_builder.py:62** — `command["risk_amount"] = risk_amount if risk_amount else 50.0` (D-12 fallback) ✅
- **order_builder.py:64** — `command["volume"] = 0` (placeholder) ✅

### Task 3: MT5 CalculateLotFromBudget

- **D-08 — Ask/Bid thực tế:** Line 874-876, `SymbolInfoDouble(symbol, SYMBOL_ASK/BID)` ✅
- **D-09 — Công thức:** Line 910, `lot = riskAmount / riskPerLot` ✅
- **D-10 — Contract sizes:** XAUUSD=100 (line 891), XAGUSD=5000 (line 893), indices=1 (lines 894-899), crypto=1 (lines 900-903), forex=100000 (line 887 default) ✅
- **D-18 — Auto-adjust tăng budget:** Line 920, `adjustedBudget *= 2` trong loop max 20 iterations ✅
- **D-19 — Auto-adjust giảm budget:** Line 936, `adjustedBudget /= 2` trong loop max 20 iterations ✅
- **D-11 — Normalize + clamp:** Line 948 `MathFloor(lot / stepVol) * stepVol`, lines 951-952 clamp ✅
- **ExecuteOpenOrder integration:** Line 982 detect `calcVolumeOnMT5`, line 1027 gọi `CalculateLotFromBudget` ✅

### Task 4: Flow mới D-13, D-14

- **Flow đúng thứ tự:**
  1. Line 199: Xác định side (BUY/SELL)
  2. Line 207-209: Tính entry_price (`_calculate_entry_price`)
  3. Line 213: Tính SL/TP với `entry_price_override=computed_entry`
  4. Line 235: Validate `missing_order_plan_keys` (nằm sau SL/TP enrichment line 232) ✅
- **D-13:** KHÔNG có `continue` sau khi `sl/tp=None` (lines 215-226 chỉ enrich, không skip) ✅
- **_calculate_entry_price gọi trước _calculate_sl_tp:** Lines 209, 213 — đúng thứ tự ✅

## Threat Flags

Không phát hiện threat surface mới — tất cả các files đã có mitigations trong plan's threat_model (T-42-04, T-42-07, T-42-09, T-42-10, T-42-11).

## Known Stubs

Không có — plan verify-only, không tạo code mới.

## Self-Check: PASSED
