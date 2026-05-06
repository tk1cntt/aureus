---
phase: 260506-u8k-exit-reason-normalize
verified: 2026-05-06T00:00:00Z
status: passed
score: 4/4 must-haves verified
overrides_applied: 0
---

# Quick Task 260506-u8k: Exit Reason Normalize Verification Report

**Task Goal:** Phân tích `mql5/AureusProvider_v2.mq5::PushOrderClosed`, xác nhận `exit_price`, `exit_time`, `exit_reason`; thống kê reason và update `_normalize_exit_reason` để close reason không còn default toàn bộ thành `MANUAL_CLOSE`.

## Verdict

PASSED.

## Goal Achievement

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | `PushOrderClosed` payload có close/exit price, exit time, exit reason/close reason. | VERIFIED | `mql5/AureusProvider_v2.mq5` payload giữ `close_price`/`t` và thêm `exit_price`, `exit_time`, `exit_reason`, `close_reason`. |
| 2 | Gateway `ORDER_CLOSED` model nhận/forward reason fields không drop. | VERIFIED | `services/aureus-gateway/main.py::OrderClosedEvent` có optional `exit_price`, `exit_reason`, `close_reason`, `reason`, `exit_time`. |
| 3 | Journal ưu tiên `exit_reason` và normalize MT5/provider aliases. | VERIFIED | `on_order_closed` đọc `exit_price` trước `close_price`; đọc `exit_reason` trước `close_reason`/`reason`; `_normalize_exit_reason` map TP/SL/SO/client/mobile/web/expert aliases. |
| 4 | Regression tests cover aliases và unknown/empty vẫn `MANUAL_CLOSE`. | VERIFIED | `services/aureus-trader/tests/test_journal.py`; focused suite `79 passed in 0.44s`. |

## Exit Reason Mapping

| Provider reason | Normalized |
|---|---|
| `TP`, `DEAL_REASON_TP`, `TAKE_PROFIT` | `TP_HIT` |
| `SL`, `DEAL_REASON_SL`, `STOP_LOSS` | `SL_HIT` |
| `SO`, `DEAL_REASON_SO`, `STOP_OUT` | `SL_HIT` |
| `TRAIL*` | `TRAILING_STOP` |
| `SIGNAL*`, `EXIT*` | `SIGNAL_EXIT` |
| `CLIENT`, `MOBILE`, `WEB`, `EXPERT` | `MANUAL_CLOSE` |
| `DEAL_REASON_CLIENT`, `DEAL_REASON_MOBILE`, `DEAL_REASON_WEB`, `DEAL_REASON_EXPERT` | `MANUAL_CLOSE` |
| empty/unknown | `MANUAL_CLOSE` |

## Required Artifacts

| Artifact | Status | Details |
|---|---|---|
| `mql5/AureusProvider_v2.mq5` | VERIFIED | Added MT5 deal reason mapping and close payload reason fields. |
| `services/aureus-gateway/main.py` | VERIFIED | `OrderClosedEvent` accepts close reason fields. |
| `services/aureus-trader/journal.py` | VERIFIED | Consumes `exit_reason`; normalizes aliases. |
| `services/aureus-trader/tests/test_journal.py` | VERIFIED | Regression tests for aliases and gateway model. |

## Test Run

```bash
python -m pytest services/aureus-trader/tests/test_journal.py -q
```

Result:

```text
79 passed in 0.44s
```

## GitNexus / Scope

Impact run before production edits:

- `_normalize_exit_reason`: direct caller `on_order_closed`, affected processes `9`, risk `CRITICAL`.
- `OrderClosedEvent`: direct callers `0`, affected processes `0`, risk `LOW`.

Detect changes unavailable:

```text
error: unknown command 'detect-changes'
```

Fallback used `git status`, scoped diffs, and focused test suite.

## Human Verification Required

None.

## Gaps Summary

No gaps found. Provider now emits reason fields, gateway accepts them, journal consumes/normalizes them. TP/SL closes should no longer all become `MANUAL_CLOSE` when MT5 sends usable deal reason.
