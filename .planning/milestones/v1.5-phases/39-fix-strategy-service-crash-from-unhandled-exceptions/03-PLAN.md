# Phase 39: Fix Strategy Service Crash from Unhandled Exceptions — Plan 03

**Wave:** 3
**Depends on:** Wave 2
**Autonomous:** Yes
**Files modified:** `services/aureus-signal/engine/strategy_executor.py`, `services/aureus-signal/engine/live_engine.py`

## Objective
Bảo vệ các điểm còn lại: `update_orders()`/`process_triggers()` trong strategy executor, fire-and-forget tasks, và cải thiện outer loop exception diagnostics.

## Read first
- `services/aureus-signal/engine/strategy_executor.py` — lines 430-470 (entry processing loop)
- `services/aureus-signal/engine/live_engine.py` — lines 720-730 (insert_single_snapshot fire-and-forget), lines 785-795 (shadow_execute_pulse fire-and-forget), lines 800-815 (outer loop exception handler)
- `.planning/phases/39-fix-strategy-service-crash-from-unhandled-exceptions/39-CONTEXT.md` — D6, D8, D9

## Plan

### Task 3.1: Bảo vệ `update_orders()` và `process_triggers()` trong strategy_executor.py
**file:** `strategy_executor.py` ~lines 438-458
**action:** Bọc try-catch riêng cho mỗi function call:
```python
if execution_mode == "simulated":
    try:
        await trade_manager.update_orders(symbol, candle_data, executor_state)
    except Exception as e:
        logger.error(f"[EXECUTOR][{symbol}] update_orders error: {e}", exc_info=True)

if strategy_results:
    try:
        pending_order = await trade_manager.process_triggers(symbol, strategy_results, executor_state)
    except Exception as e:
        logger.error(f"[EXECUTOR][{symbol}] process_triggers error: {e}", exc_info=True)
        pending_order = None
```

### Task 3.2: Tạo supervised task wrapper cho fire-and-forget tasks
**file:** `live_engine.py` — thêm helper function trước `run_signal_engine()`
**action:** Thêm wrapper function:
```python
async def supervised_background_task(name: str, coro):
    """Wraps background tasks with logging, restart, and crash reporting."""
    max_restarts = 5
    restart_count = 0
    while True:
        try:
            await coro
            break
        except asyncio.CancelledError:
            logger.info(f"[SUPERVISOR] Task '{name}' cancelled")
            raise
        except Exception:
            restart_count += 1
            if restart_count > max_restarts:
                logger.critical(f"[SUPERVISOR] Task '{name}' crashed {max_restarts}x — giving up", exc_info=True)
                break
            delay = min(2 ** restart_count, 60)
            logger.warning(f"[SUPERVISOR] Task '{name}' crashed ({restart_count}/{max_restarts}), restarting in {delay}s", exc_info=True)
            await asyncio.sleep(delay)
```

Sau đó thay thế các `asyncio.create_task()` calls:
- `asyncio.create_task(insert_single_snapshot(db_pool, snapshot))` → `asyncio.create_task(_safe_insert_snapshot(db_pool, snapshot))`
- `asyncio.create_task(shadow_execute_pulse(...))` → `asyncio.create_task(_safe_shadow_pulse(...))`

Helper cụ thể:
```python
async def _safe_insert_snapshot(pool, snap):
    try:
        await insert_single_snapshot(pool, snap)
    except Exception as e:
        logger.warning(f"[Snapshot] DB insert failed: {e}")
```

### Task 3.3: Cải thiện outer loop exception diagnostics
**file:** `live_engine.py` lines ~800-815 và `strategy_executor.py` lines ~475-485
**action:** Phân biệt exception types trong outer try-catch:
```python
except asyncio.CancelledError:
    logger.info("[GLOBAL] Engine loop cancelled, shutting down gracefully")
    raise
except ConnectionError as e:
    logger.error(f"[GLOBAL] Connection lost: {e}", exc_info=True)
    await asyncio.sleep(10)  # Longer wait for reconnect
except Exception as e:
    logger.error(f"[GLOBAL] Engine loop error: {e}", exc_info=True)
    traceback.print_exc()
    await asyncio.sleep(1)
```

## Acceptance criteria
- [ ] `update_orders()` và `process_triggers()` có try-catch riêng trong strategy_executor.py
- [ ] `supervised_background_task()` helper được thêm vào live_engine.py
- [ ] Fire-and-forget tasks (`insert_single_snapshot`, `shadow_execute_pulse`) được bọc trong safe wrappers
- [ ] Outer loop exception handler phân biệt CancelledError, ConnectionError, generic Exception
- [ ] `python -m py_compile services/aureus-signal/engine/live_engine.py` thành công
- [ ] `python -m py_compile services/aureus-signal/engine/strategy_executor.py` thành công
- [ ] Service restart và chạy ổn định 30+ phút không crash

## Requirements addressed
- D6: Bảo vệ update_orders và process_triggers
- D8: Fire-and-forget tasks có supervisor
- D9: Cải thiện outer loop diagnostics
