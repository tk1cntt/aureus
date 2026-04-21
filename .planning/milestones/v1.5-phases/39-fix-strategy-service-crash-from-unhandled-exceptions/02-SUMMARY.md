# Phase 39: Fix Strategy Service Crash — Summary (Plan 02, Critical path protection)

**Status:** In progress
**Wave:** 2
**Depends on:** Wave 1

## What this plan does

Protects 4 critical unhandled exception paths:

1. **`recalculate_all_signals()`** — Removes bare `raise` in except block that kills `daily_gc_loop` parent task
2. **`news_refresh_loop()`** — Wraps 24h news refresh loop body in try-catch (zero protection before)
3. **`listen_for_reload()`** — Adds try-catch with reconnect logic to pubsub listeners in both `live_engine.py` and `strategy_executor.py`
4. **`tradingagents_provider.get_decision()`** — Adds timeout-aware try-catch for TA provider calls

## Acceptance criteria

- `recalculate_all_signals()` no longer re-raises (logs error instead)
- `news_refresh_loop()` has try-catch around `fetch_this_week()` call
- `listen_for_reload()` in both files has try-catch with reconnect (5s delay)
- `tradingagents_provider.get_decision()` has separate try-catch for timeout vs general errors
- Both files compile successfully via `py_compile`

## Requirements addressed

- D2: Fix recalculate_all_signals re-raise
- D3: Protect news_refresh_loop 24h variant
- D4: Protect listen_for_reload pubsub listener
- D5: Protect tradingagents_provider.get_decision
