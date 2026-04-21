# Phase 42: Giảm RR ratio xuống 1.5 và bổ sung FIXED_BUDGET entry (50$) - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-14
**Phase:** 42-giam-rr-ratio-xuong-1-5-va-bo-sung-fixed-budget-entry
**Mode:** discuss (update existing context)
**Areas discussed:** Risk Amount fallback, MT5 volume validation, RR per-strategy override

---

## Risk Amount Fallback

| Option | Description | Selected |
|--------|-------------|----------|
| Symbol-specific fallback | Mỗi symbol có budget riêng (Forex $50, XAUUSD $100, US30 $150) | |
| Uniform $50 + min lot guard (Recommended) | Giữ $50 uniform, nếu lot < 0.01 → tự tăng budget cho đủ min lot | ✓ |
| Uniform $50 + max lot cap | Giữ $50 uniform, nếu lot > max thì cap ở max | |

**User's choice:** Uniform $50 + min lot guard
**Notes:** Người dùng muốn giữ uniform $50 cho mọi symbol, không symbol-specific. Nếu lot tính ra quá nhỏ → tăng budget cho đến khi đủ min lot (0.01).

## MT5 Volume Validation

| Option | Description | Selected |
|--------|-------------|----------|
| Validate trước khi gửi | Python tính lot nháp, reject nếu > max hoặc < min | |
| Cho MT5 reject | Không validate, accept NACK từ MT5 | |
| Auto-adjust budget (Recommended) | Nếu lot > max → giảm budget cho đủ max volume | ✓ |

**User's choice:** Auto-adjust budget
**Notes:** KHÔNG reject signal. Nếu lot vượt quá SYMBOL_VOLUME_MAX → tự động giảm budget cho đủ max volume. Chấp nhận rủi ro nhỏ hơn budget dự định.

## RR Per-Strategy Override

| Option | Description | Selected |
|--------|-------------|----------|
| Uniform 1.5 (Recommended) | Giữ 1.5 cho tất cả, đơn giản dễ quản lý | ✓ |
| Per-strategy override | Cho phép config RR riêng cho từng strategy | |
| Tiered RR theo strategy type | 1.5 cho scalping, 2.0 cho swing/trend | |

**User's choice:** Uniform 1.5
**Notes:** RR 1.5 uniform cho tất cả. Nếu strategy nào thực sự cần RR khác thì config sau.

---

## Claude's Discretion

Areas where user deferred to Claude:
- Contract size file `symbol_contracts.json` handling
- Log format for lot calculation
- Exact auto-adjust loop implementation (20 iterations max, halving/doubling)

## Deferred Ideas

- None — discussion stayed within phase scope

## Corrections Applied (Code Update)

- **CalculateLotFromBudget()**: Updated từ clamp đơn giản sang auto-adjust budget logic
  - Lot < minVol: doubling budget loop (tối đa 20 lần)
  - Lot > maxVol: halving budget loop (tối đa 20 lần)
  - Log thêm `originalBudget → adjustedBudget` để trace budget adjustment
