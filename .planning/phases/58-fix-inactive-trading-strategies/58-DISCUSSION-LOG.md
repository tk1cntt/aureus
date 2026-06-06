# Phase 58: Fix inactive trading strategies - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-06
**Phase:** 58-fix-inactive-trading-strategies
**Mode:** discuss
**Areas discussed:** Scope, Success criteria, Config change policy

---

## Scope

| Option | Description | Selected |
|--------|-------------|----------|
| TPO + FZ_CONT (8 strategies) | Chỉ verify 6 TPO + 2 FZ_CONT đã có quick fix 260602-pvk/riq | ✓ |
| Tất cả 16 chiến lược 0-lệnh | Thêm 8 strategies chưa rõ trạng thái | |
| Bao gồm cả winrate thấp | Thêm SESSION_SWEEP, LIMIT_PULLBACK | |
| Để Claude quyết định | Claude chọn phạm vi dựa trên cost/benefit | |

**User's choice:** TPO + FZ_CONT (8 strategies)
**Notes:** User chọn nghĩa hẹp nhất vì đã có quick fixes cụ thể (260602-pvk cho TPO, 260602-riq cho FZ_CONT). Không muốn mở rộng scope sang phần chưa rõ root cause.

---

## Success Criteria

| Option | Description | Selected |
|--------|-------------|----------|
| Mỗi strategy có ≥1 lệnh backtest E2E | Chạy replay/backtest deterministic | |
| Mỗi strategy phải có winrate ≥ ngưỡng | Có nguy cơ tune logic, vượt scope | |
| Live runtime emit được signal | Verify signal tag trong Redis/event stream | ✓ |
| Để Claude quyết định | Claude chọn tiêu chí phù hợp | |

**User's choice:** Live runtime emit được signal
**Notes:** User muốn verify signal xuất hiện trong pipeline, chưa cần qua MT5 order. Không yêu cầu winrate.

---

## Config Change Policy

| Option | Description | Selected |
|--------|-------------|----------|
| Không, chỉ fix pipeline/runtime | Giữ nguyên 28 strategies config | ✓ |
| Có thể điều chỉnh min_score/context_filter | Cho phép nới threshold nếu root cause là threshold quá chặt | |
| Để Claude quyết định | Claude thay đổi config khi cần thiết | |

**User's choice:** Không, chỉ fix pipeline/runtime
**Notes:** User muốn tách biệt rõ giữa "fix bug pipeline" và "tune strategy config". Strategy config thuộc phase khác.

---

## Claude's Discretion

- Thứ tự verify 8 strategies (TPO trước hay FZ_CONT trước)
- Cách instrument để capture signal flow evidence
- Có verify bằng replay harness hay chỉ review code + unit test

## Deferred Ideas

- Cải thiện winrate SESSION_SWEEP (43%) — future phase (scoring/reporting)
- Cải thiện winrate LIMIT_PULLBACK (35%) — future phase (scoring/reporting)
- Root cause 8 strategies chưa rõ (LIMIT_OB_EDGE, LIMIT_EMA_TOUCH, TREND_CONT_FVG, TREND_CONT_LIMIT) — new phase needed
- Tune strategy config — out of scope for this phase
