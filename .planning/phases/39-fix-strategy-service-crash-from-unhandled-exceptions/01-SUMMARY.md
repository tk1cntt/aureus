# Phase 39: Fix Strategy Service Crash — Summary (Plan 01, Bare except fix)

**Status:** In progress
**Wave:** 1
**Depends on:** None

## What this plan does

- Replace bare `except:` clauses in `services/aureus-signal/engine/simulated_orders.py` with `except Exception:`
- Bare `except:` catches `KeyboardInterrupt` and `SystemExit`, preventing clean shutdown
- Ensures consistency with `orders.py` pattern

## Acceptance criteria

- No bare `except:` remaining in `simulated_orders.py` (verified by grep)
- File compiles successfully via `py_compile`
- No new lint errors

## Requirements addressed

- D7: Replace bare `except:` with `except Exception:`
