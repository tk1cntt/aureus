# Phase 49: order-execution-contract-multi-symbol - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-20
**Phase:** 49-order-execution-contract-multi-symbol
**Areas discussed:** ORDER_OPEN contract completeness, Multi-symbol consume semantics, Stream mapping consistency, Reliability & observability

---

## Gray Area Selection

| Option | Description | Selected |
|--------|-------------|----------|
| ORDER_OPEN contract completeness | Chốt mức bắt buộc của field critical vs optional và cách xử lý fallback để tránh reject sai. | ✓ |
| Multi-symbol consume semantics | Chốt cách discover stream/poll/whitelist để loại bỏ hardcode XAUUSD nhưng vẫn giữ guardrails. | ✓ |
| Stream mapping consistency | Chốt mapping field giữa signal -> bridge -> node để tránh mismatch `qty/quantity`, timestamp, strategy context. | ✓ |
| Reliability & observability | Chốt reason codes + metrics bắt buộc để verifier có evidence đóng integration gaps. | ✓ |

**Mode:** `--auto` (workflow auto-selected all gray areas theo chuẩn discuss-phase).
**Notes:** Không mở rộng scope ngoài boundary phase 49; giữ minimum-change wiring.

---

## Claude's Discretion

- Cách đặt tên helper normalize contract mapping và vị trí đặt helper.
- Cấu trúc test cases cụ thể (unit/integration split) để đóng đủ 3 integration gaps.
- Mức refactor tối thiểu để bỏ hardcode XAUUSD mà không động đến capability mới.

## Deferred Ideas

- Investigate missing OB events in signal history (todo pending) — ngoài scope contract wiring phase 49.
- Remove market_regime use htf_trend (todo pending) — ngoài scope execution contract multi-symbol.
