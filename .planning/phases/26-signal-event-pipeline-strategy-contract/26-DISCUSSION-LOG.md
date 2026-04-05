# Phase 26 — Discussion Log

**Phase:** 26 — Signal Event Pipeline & Strategy Contract
**Date:** 2026-04-05
**Participants:** User + AI Agent (gsd-discuss-phase)

---

## Topics Discussed

### 1. Entry Contract Shape
- **Initial proposal:** Giữ nguyên `entry_type` + `entry_policy`
- **Challenge:** STRAT-01 cần extend enum (MARKET/LIMIT/STOP), không chỉ giữ nguyên
- **Finding:** 2 nơi set `entry_type` (template.build_order_plan + orders.snapshot) → cần validate consistency
- **Final:** Giữ shape, extend enum + validation

### 2. Position Sizing
- **Initial proposal:** `size` + `size_mode` canonical; `lot_size` chỉ adapter
- **Challenge:** Naming mismatch — `build_order_plan()` emit `size` nhưng `REQUIRED_ORDER_PLAN_KEYS` cần `size_value`
- **Finding:** `orders.py` map ngầm `size` → `size_value`; `capital_risk_pct` đã tồn tại trong template.py
- **Final:** Normalize sang `size_value`; chốt enum `FIXED_UNITS|FIXED_LOT|RISK_PERCENT`; conversion tại adapter

### 3. Magic Number
- **Initial proposal:** Sinh ở adapter bằng hash
- **Challenge:** Hash không stable qua deploy → gãy MT5 history sync
- **Finding:** PITFALLS.md xác nhận magic number là execution concern; STRAT-04 yêu cầu per strategy
- **Final:** Static mapping trong DB `aureus_strategy_templates`

### 4. Publish Channel
- **Initial proposal:** Giữ orders stream + thêm decisions stream
- **Challenge:** NOTIF-01 yêu cầu pub/sub, không phải stream; thêm stream tăng complexity
- **Finding:** `strategy_executor.py` đã trộn rejections vào orders stream
- **Final:** Pub/sub channel trước (Phase 26); decisions stream defer

### 5. SL/TP Source of Truth
- **Initial proposal:** Giữ fallback + feature flag strict mode
- **Challenge:** `REQUIRED_ORDER_PLAN_KEYS` validation đã tồn tại → flag redundant. Hardcoded fallback 300 pips nguy hiểm.
- **Finding:** `_calculate_sl_tp` có magic number 300/10000.0 fallback cho mọi symbol
- **Final:** Bỏ hardcoded fallback; strategy phải cung cấp config; explicit reject nếu thiếu

---

## Key Artifacts
- [26-CONTEXT.md](file:///d:/Aureus/.planning/phases/26-signal-event-pipeline-strategy-contract/26-CONTEXT.md) — Canonical decisions
- [phase26_devils_advocate.md](file:///C:/Users/Admin/.gemini/antigravity/brain/f4e256ac-d5be-491e-b53a-3c8f0a0b74b8/phase26_devils_advocate.md) — Phản biện chi tiết

---
*Log created: 2026-04-05*
