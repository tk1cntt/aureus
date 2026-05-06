---
phase: 260506-u8k-exit-reason-normalize
plan: 01
subsystem: mt5-provider/trader-journal
status: completed
tags:
  - quick
  - order-closed
  - exit-reason
requirements:
  - QUICK-260506-U8K
dependency_graph:
  requires:
    - mql5/AureusProvider_v2.mq5::PushOrderClosed
    - services/aureus-gateway/main.py::OrderClosedEvent
    - services/aureus-trader/journal.py::_normalize_exit_reason
  provides:
    - MT5 close reason forwarding and normalization
  affects:
    - ORDER_CLOSED payload flow
key_files:
  modified:
    - mql5/AureusProvider_v2.mq5
    - services/aureus-gateway/main.py
    - services/aureus-trader/journal.py
    - services/aureus-trader/tests/test_journal.py
metrics:
  completed_date: 2026-05-06
  tests_run: "python -m pytest services/aureus-trader/tests/test_journal.py -q"
---

# Quick Task 260506-u8k: Exit Reason Normalize Summary

Analyzed MT5 provider `PushOrderClosed`, gateway schema, and trader journal close reason normalization. Fixed missing close reason flow so closed orders no longer default to `MANUAL_CLOSE` when MT5 provides TP/SL/stop-out/client reason data.

## Findings

### `PushOrderClosed` before fix

- Sent `close_price` and `t`.
- Did not send explicit `exit_price`.
- Did not send explicit `exit_time`.
- Did not send `exit_reason` or `close_reason`.
- Therefore trader saw blank reason and `_normalize_exit_reason("")` returned `MANUAL_CLOSE`.

### Exit reason types supported from MT5/provider

| Provider reason | Normalized journal reason |
|---|---|
| `TP`, `DEAL_REASON_TP`, `TAKE_PROFIT` | `TP_HIT` |
| `SL`, `DEAL_REASON_SL`, `STOP_LOSS` | `SL_HIT` |
| `SO`, `DEAL_REASON_SO`, `STOP_OUT` | `SL_HIT` |
| `TRAIL*` | `TRAILING_STOP` |
| `SIGNAL*`, `EXIT*` | `SIGNAL_EXIT` |
| `CLIENT`, `MOBILE`, `WEB`, `EXPERT` | `MANUAL_CLOSE` |
| `DEAL_REASON_CLIENT`, `DEAL_REASON_MOBILE`, `DEAL_REASON_WEB`, `DEAL_REASON_EXPERT` | `MANUAL_CLOSE` |
| empty/unknown | `MANUAL_CLOSE` |

## Completed Changes

| Commit | Purpose | Files |
|---|---|---|
| `6f61c12` | Add exit reason regression tests and gateway fields | `services/aureus-gateway/main.py`, `services/aureus-trader/tests/test_journal.py` |
| `2e71631` | Forward MT5 close reasons and normalize aliases | `mql5/AureusProvider_v2.mq5`, `services/aureus-trader/journal.py` |

## Implementation

- `mql5/AureusProvider_v2.mq5`
  - Added `DealReasonToCloseReason(long reason)`.
  - `DEAL_ENTRY_OUT` handling reads `HistoryDealGetInteger(trans.deal, DEAL_REASON)`.
  - `PushOrderClosed` payload now includes:
    - `close_price`
    - `exit_price`
    - `t`
    - `exit_time`
    - `exit_reason`
    - `close_reason`
  - Existing `close_price` and `t` kept for compatibility.

- `services/aureus-gateway/main.py`
  - `OrderClosedEvent` accepts optional `exit_price`, `exit_reason`, `close_reason`, `reason`, and `exit_time`.

- `services/aureus-trader/journal.py`
  - `on_order_closed` prefers `exit_price` over `close_price` over `price`.
  - `on_order_closed` prefers `exit_reason` over `close_reason` over `reason`.
  - `_normalize_exit_reason` handles MT5/provider reason aliases above.

## Verification

```bash
python -m pytest services/aureus-trader/tests/test_journal.py -q
```

Result:

```text
79 passed in 0.44s
```

DB E2E not run because no DB schema or DB write contract changed; journal unit tests cover payload normalization and update data.

## GitNexus

Impact run before production edits:

- `_normalize_exit_reason`: direct caller `on_order_closed`, affected processes `9`, modules `3`, risk `CRITICAL`.
- `OrderClosedEvent`: direct callers `0`, affected processes `0`, risk `LOW`.

Detect changes:

- `npx gitnexus detect-changes --repo Aureus` failed: `error: unknown command 'detect-changes'`.
- Fallback used `git status`, focused diffs, and focused tests.

## Notes

Unrelated working tree files preserved:

- `mql5/AureusProvider_v2.ex5`
- `stable/`

`mql5/AureusProvider_v2.mq5` already had unrelated user edits before this task. Code commit intentionally included current provider file with required close-reason fix while preserving those edits.
