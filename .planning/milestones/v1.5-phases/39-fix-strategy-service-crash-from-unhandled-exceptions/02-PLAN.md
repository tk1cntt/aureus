# Phase 39: Fix Strategy Service Crash from Unhandled Exceptions — Plan 02

**Wave:** 2
**Depends on:** Wave 1
**Autonomous:** Yes
**Files modified:** `services/aureus-signal/engine/live_engine.py`, `services/aureus-signal/engine/strategy_executor.py`

## Objective
Bảo vệ các điểm critical nhất trong code: `recalculate_all_signals()`, `news_refresh_loop()`, `listen_for_reload()`, và `tradingagents_provider.get_decision()`. Đây là những nơi mà exception sẽ gây chết service hoặc mất functionality.

## Read first
- `services/aureus-signal/engine/live_engine.py` — lines 250-450 (init warmup), lines 530-560 (news_refresh_loop), lines 450-500 (listen_for_reload), lines 760-780 (TA provider), lines 1085-1095 (recalculate_all_signals)
- `services/aureus-signal/engine/strategy_executor.py` — lines 250-280 (listen_for_reload)
- `.planning/phases/39-fix-strategy-service-crash-from-unhandled-exceptions/39-RESEARCH.md` — Pattern 2, 3, 4
- `.planning/phases/39-fix-strategy-service-crash-from-unhandled-exceptions/39-CONTEXT.md` — D2, D3, D4, D5

## Plan

### Task 2.1: Fix `recalculate_all_signals()` — bỏ re-raise
**file:** `live_engine.py` ~line 1089-1091
**action:**
```python
# hiện tại:
except Exception:
    window_manager.set_backfill_status(symbol, "NOT_READY", reason="RECALC_FAILED", updated_at=time.time())
    raise

# sửa thành:
except Exception as e:
    window_manager.set_backfill_status(symbol, "NOT_READY", reason="RECALC_FAILED", updated_at=time.time())
    logger.error(f"[{symbol}] [recalculate_all_signals] Recalculation failed — will retry on next cycle", exc_info=True)
```

### Task 2.2: Bảo vệ `news_refresh_loop()` 24h variant
**file:** `live_engine.py` ~line 537-543
**action:** Bọc toàn bộ loop body trong try-catch
```python
async def news_refresh_loop():
    while True:
        try:
            await asyncio.sleep(86400)
            logger.info("[GLOBAL] [news_refresh_loop] Refreshing weekly news calendar...")
            await asyncio.to_thread(NewsProvider.fetch_this_week)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"[GLOBAL] [news_refresh_loop] News refresh failed: {e}", exc_info=True)
```

### Task 2.3: Bảo vệ `listen_for_reload()` trong cả live_engine.py và strategy_executor.py
**file:** `live_engine.py` ~line 461-480 và `strategy_executor.py` ~line 255-270
**action:** Bọc toàn bộ pubsub listener loop trong try-catch với reconnect:
```python
async def listen_for_reload():
    while True:
        try:
            pubsub = r.pubsub()
            await pubsub.subscribe("aureus:cmd:refresh_strategies")
            async for message in pubsub.listen():
                if message and message.get("type") == "message":
                    for s in symbols_list:
                        await symbol_strategies[s].load_from_db(db_pool, s)
                    logger.info("[GLOBAL] [listen_for_reload] Strategies reloaded")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"[GLOBAL] [listen_for_reload] Error: {e}", exc_info=True)
            await asyncio.sleep(5)  # Wait before reconnect
```

### Task 2.4: Bảo vệ `tradingagents_provider.get_decision()` 
**file:** `live_engine.py` ~line 765-770
**action:**
```python
elif provider_mode == "ta_primary":
    try:
        ctx = ai_validator.builder.build_pulse_context(symbol, df, state, trigger_events=state.ai_trigger_events)
        decision = await tradingagents_provider.get_decision(symbol, ctx)
        logger.info(f"[t={ts_unix}] [{symbol}] TA Primary Decision logic evaluated")
    except asyncio.TimeoutError:
        logger.error(f"[t={ts_unix}] [{symbol}] TA Primary timeout — skipping pulse")
    except Exception as e:
        logger.error(f"[t={ts_unix}] [{symbol}] TA Primary error: {e}", exc_info=True)
```

## Acceptance criteria
- [ ] `recalculate_all_signals()` không còn `raise` trong except block
- [ ] `news_refresh_loop()` có try-catch bao quanh `fetch_this_week()` call
- [ ] `listen_for_reload()` trong cả 2 files có try-catch với reconnect logic
- [ ] `tradingagents_provider.get_decision()` có try-catch riêng
- [ ] `python -m py_compile services/aureus-signal/engine/live_engine.py` thành công
- [ ] `python -m py_compile services/aureus-signal/engine/strategy_executor.py` thành công

## Requirements addressed
- D2: Fix recalculate_all_signals re-raise
- D3: Bảo vệ news_refresh_loop 24h variant
- D4: Bảo vệ listen_for_reload pubsub listener
- D5: Bảo vệ tradingagents_provider.get_decision
