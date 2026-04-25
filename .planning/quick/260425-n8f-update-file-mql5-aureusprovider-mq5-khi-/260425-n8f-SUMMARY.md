---
phase: quick-260425-n8f-update-file-mql5-aureusprovider-mq5-khi-
plan: 01
subsystem: mql5-provider
tags: [mql5, mt5, order-failed, diagnostics]
requires:
  - phase: quick-260425-n8f-update-file-mql5-aureusprovider-mq5-khi-
    provides: ORDER_FAILED diagnostic plan
provides:
  - ORDER_FAILED payloads now include entry_price, ask, and bid diagnostics
  - ExecuteOpenOrder failure paths pass read-only price diagnostics to PushOrderFailed
affects: [mt5-provider, gateway-order-events]
tech-stack:
  added: []
  patterns: [backward-compatible optional diagnostic parameters]
key-files:
  created:
    - .planning/quick/260425-n8f-update-file-mql5-aureusprovider-mq5-khi-/260425-n8f-SUMMARY.md
  modified:
    - mql5/AureusProvider.mq5
key-decisions:
  - "Kept PushOrderFailed backward-compatible with optional default diagnostic values so non-open-order failure paths still compile and emit zero-valued diagnostics."
patterns-established:
  - "ORDER_FAILED diagnostics carry read-only price context without changing request.price, OrderCheck, OrderSend, retry, ACK/NACK, SL/TP, or volume behavior."
requirements-completed: [QUICK-260425-N8F]
duration: 20min
completed: 2026-04-25
---

# Quick 260425-n8f: AureusProvider ORDER_FAILED Diagnostics Summary

**ORDER_FAILED events now include entry_price, ask, and bid diagnostics for INVALID_PRICE/retcode 10015 triage without changing order execution behavior.**

## Performance

- **Duration:** 20 min
- **Started:** 2026-04-25T00:00:00Z
- **Completed:** 2026-04-25T00:20:00Z
- **Tasks:** 2
- **Files modified:** 1 implementation file

## Accomplishments

- Extended `PushOrderFailed` in `mql5/AureusProvider.mq5` with optional `entryPrice`, `ask`, and `bid` parameters.
- Added numeric `entry_price`, `ask`, and `bid` fields to the ORDER_FAILED JSON payload while preserving existing `type`, `cmd_id`, `symbol`, `reason`, `retcode`, and `t` fields.
- Added the same diagnostics to the terminal `PrintFormat` log.
- Passed `entry_price`, `ask`, and `bid` from `ExecuteOpenOrder` failure paths that already have those values: unknown order type, OrderCheck fail, OrderSend fail, non-DONE retcode, and terminal event gate.

## Task Commits

1. **Task 1/2: Bổ sung diagnostic entry/ask/bid và kiểm tra scope** - `a4065d3` (fix)

## Files Created/Modified

- `D:/Aureus/mql5/AureusProvider.mq5` - Adds ORDER_FAILED diagnostic price fields and passes existing open-order price context through failure branches.
- `D:/Aureus/.planning/quick/260425-n8f-update-file-mql5-aureusprovider-mq5-khi-/260425-n8f-SUMMARY.md` - Execution summary only; intentionally not committed by this executor per quick-task constraint.

## Decisions Made

- Kept `PushOrderFailed` backward-compatible with default diagnostic values (`0.0`) so close-order and pre-price failure paths do not require behavioral changes.
- Did not modify `request.price`, `entry_price`, `ask`, `bid`, volume, SL/TP, `OrderCheck`, `OrderSend`, retry/idempotency, ACK/NACK, or terminal event semantics.

## GitNexus / Impact Analysis

GitNexus MCP tools were not available in this executor environment, so project-required impact checks used source-search fallback.

Fallback blast radius:

| Symbol | Direct call sites found | Affected process | Risk |
|--------|--------------------------|------------------|------|
| `PushOrderFailed` | 10 call sites in `D:/Aureus/mql5/AureusProvider.mq5` | MT5 provider ORDER_FAILED event emission | Low: signature is backward-compatible via optional defaults; payload/log adds diagnostic fields only. |
| `ExecuteOpenOrder` | Function body only modified at `PushOrderFailed` calls | OPEN_ORDER failure reporting | Low: no request construction or send/check behavior changed. |

Pre-commit detect-changes fallback:

- `git diff -- mql5/AureusProvider.mq5` reviewed before commit.
- `git status --short mql5/AureusProvider.mq5` showed only the intended implementation file.
- `git diff --check -- mql5/AureusProvider.mq5` passed.

## Verification

- Static diagnostic check passed with `ORDER_FAILED diagnostics present`.
- Scoped diff review confirmed only `PushOrderFailed` signature/payload/log and `ExecuteOpenOrder` failure call-sites changed.
- No database changes were made; database e2e testing was not applicable.
- MT5/MetaEditor compiler was not available in this executor environment, so MQL5 compile was not run.

## Deviations from Plan

None - plan executed as written, except GitNexus MCP was unavailable and source-search/diff fallback was used as allowed by the plan constraints.

## Known Stubs

None found in the modified implementation scope.

## Threat Flags

None. The plan threat model already covered adding non-secret market/order diagnostic fields to ORDER_FAILED payload/log.

## Issues Encountered

- The first static verification command failed because the shell heredoc quoting did not match escaped MQL5 string literals. Re-ran an equivalent static check with escaped string matching; it passed.

## User Setup Required

None.

## Next Readiness

The gateway can now receive ORDER_FAILED payloads with `entry_price`, `ask`, and `bid`; downstream consumers that tolerate additive JSON fields need no changes.

## Self-Check: PASSED

- Found implementation file: `D:/Aureus/mql5/AureusProvider.mq5`
- Found summary file: `D:/Aureus/.planning/quick/260425-n8f-update-file-mql5-aureusprovider-mq5-khi-/260425-n8f-SUMMARY.md`
- Found task commit: `a4065d3`

---
*Phase: quick-260425-n8f-update-file-mql5-aureusprovider-mq5-khi-*
*Completed: 2026-04-25*
