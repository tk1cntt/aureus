# Phase 39: Fix Strategy Service Crash — Summary (Plan 03, Remaining gaps + supervision)

**Status:** In progress
**Wave:** 3
**Depends on:** Wave 2

## What this plan does

Protects remaining exception paths and adds supervision infrastructure:

1. **`update_orders()` and `process_triggers()`** — Adds separate try-catch for each function call in `strategy_executor.py` entry processing loop
2. **`supervised_background_task()` wrapper** — New helper in `live_engine.py` with exponential backoff restart (max 5), crash logging, and graceful cancellation
3. **Fire-and-forget task safety** — `_safe_insert_snapshot()` and `_safe_shadow_pulse()` wrappers for `asyncio.create_task()` calls that previously died silently
4. **Outer loop diagnostics** — Distinguishes `CancelledError`, `ConnectionError`, and generic `Exception` in outer try-catch with appropriate recovery actions

## Acceptance criteria

- `update_orders()` and `process_triggers()` have separate try-catch in `strategy_executor.py`
- `supervised_background_task()` helper added to `live_engine.py`
- Fire-and-forget tasks (`insert_single_snapshot`, `shadow_execute_pulse`) wrapped in safe wrappers
- Outer loop exception handler distinguishes CancelledError, ConnectionError, generic Exception
- Both files compile successfully via `py_compile`
- Service runs stable 30+ minutes without crash

## Requirements addressed

- D6: Protect update_orders and process_triggers
- D8: Fire-and-forget tasks have supervisor
- D9: Improve outer loop diagnostics
