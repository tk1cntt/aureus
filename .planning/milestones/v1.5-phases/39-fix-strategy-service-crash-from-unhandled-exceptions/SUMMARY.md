# Phase 39: Fix Strategy Service Crash from Unhandled Exceptions — Summary

**Status:** COMPLETED
**Commit:** e419ee9
**Date:** 2026-04-10

## Objective
Fix all unhandled exception points in the signal engine that could cause service crashes, data loss, or silent failures.

## Changes Made

### Wave 1: Bare except fix (simulated_orders.py)
- Replaced bare `except:` with `except Exception:` to allow clean shutdown (KeyboardInterrupt, SystemExit propagate correctly)

### Wave 2: Critical protection (live_engine.py, strategy_executor.py)
- `recalculate_all_signals()`: Removed `raise` in except block, added error logging — recalculation failures no longer kill parent task
- `news_refresh_loop()`: Wrapped entire loop body in try-catch with CancelledError re-raise
- `listen_for_reload()` (both files): Added reconnect loop with 5s backoff, CancelledError handling
- `tradingagents_provider.get_decision()`: Added dedicated try-catch with TimeoutError vs generic Exception distinction

### Wave 3: Remaining protection + diagnostics
- Task 3.2: Added `_safe_insert_snapshot()` fire-and-forget wrapper
- Task 3.2: Added `supervised_background_task()` helper with crash counting, exponential backoff, max 5 restarts
- Task 3.3: Added `asyncio.CancelledError` handler to outer engine loop
- Task 3.3: Added `traceback.print_exc()` to outer loop diagnostics

## Files Modified
| File | Lines Changed |
|------|--------------|
| `engine/simulated_orders.py` | +1/-1 (bare except fix) |
| `engine/live_engine.py` | +68/-30 (Wave 2 + Wave 3 changes) |
| `engine/strategy_executor.py` | +43/-33 (Wave 2 + Wave 3.1 changes) |

## Acceptance Criteria
- [x] No bare `except:` in simulated_orders.py
- [x] `recalculate_all_signals()` no longer re-raises exceptions
- [x] `news_refresh_loop()` has try-catch around fetch_this_week
- [x] `listen_for_reload()` in both files has try-catch with reconnect
- [x] `tradingagents_provider.get_decision()` has dedicated try-catch
- [x] `update_orders()` and `process_triggers()` have individual try-catch
- [x] `_safe_insert_snapshot()` wrapper added
- [x] `supervised_background_task()` helper added
- [x] Outer loop distinguishes CancelledError from generic Exception
- [x] All files pass `python -m py_compile`

## Risk Assessment
- **Blast radius:** Medium — affects exception handling in core engine loops
- **Direction change:** Exception suppression (re-raise removed) — previously failures killed the task, now they log and continue
- **Mitigation:** All suppressed exceptions now have explicit error logging with `exc_info=True`
