# Phase 39: Fix Strategy Service Crash from Unhandled Exceptions — Research

**Researched:** 2026-04-10
**Domain:** Python async exception handling, Redis stream consumer resilience, strategy execution lifecycle
**Confidence:** HIGH

## Summary

The `aureus-signal` service has two main async entry points: `run_signal_engine()` (signal aggregation) and `run_strategy_executor()` (strategy evaluation). Both run as long-lived `while True` loops consuming Redis streams. The codebase has mixed exception handling quality — some paths are well-protected with try/except, while others have gaps that can crash the service silently.

The primary crash vectors are: (1) the outer `asyncio.create_task()` fire-and-forget calls where exceptions are silently swallowed, (2) the `recalculate_all_signals()` function which re-raises exceptions without catching them, (3) bare `except:` clauses that mask root causes, and (4) missing try/except in the `news_refresh_loop` (the 24-hour variant, not the 900-second one).

**Primary recommendation:** Add a global exception wrapper for all `asyncio.create_task()` background workers, fix the `recalculate_all_signals()` re-raise to log-and-recover, and add explicit crash-recovery to both main engine loops.

## User Constraints (from CONTEXT.md)

No CONTEXT.md exists for this phase — all decisions are at Claude's discretion.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.12.9 [VERIFIED: runtime] | Runtime | Project uses async/await extensively |
| redis.asyncio | 7.2.0 [VERIFIED: requirements.txt] | Async Redis client | Stream consumers, pub/sub |
| asyncpg | 0.31.0 [VERIFIED: requirements.txt] | Async PostgreSQL | TimescaleDB candle/snapshot storage |
| pandas | 3.0.1 [VERIFIED: requirements.txt] | Data manipulation | Candle dataframes for signal calculation |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| openai | 2.21.0 [VERIFIED: requirements.txt] | LLM client (vLLM) | AI validation and pulse analysis |
| httpx | 0.28.1 [VERIFIED: requirements.txt] | HTTP client | TradingAgents API calls |
| python-dotenv | 1.2.1 [VERIFIED: requirements.txt] | Env loading | Local dev configuration |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `asyncio.create_task()` + manual error handling | `asyncio.TaskGroup` (Python 3.11+) | Better structured concurrency, but requires Python 3.11+ (we have 3.12, so this is viable) |
| Manual try/except in each loop | Sentry or structlog-based crash reporting | Overkill for a single-service deployment |

## Architecture Patterns

### Service Entry Points

```
main.py → run_signal_engine()      # Signal aggregation: candles → signals → Redis stream
main_executor.py → run_strategy_executor()  # Strategy evaluation: signals → orders → AI queue
```

Both use the same pattern:
1. Connect to Redis and PostgreSQL
2. Seed strategies from DB
3. Spawn background tasks (brain workers, news refresh, integrity checks)
4. Enter infinite `while True` loop consuming Redis streams
5. Top-level try/except around the loop body with `await asyncio.sleep(1)` on error

### Recommended Project Structure
```
services/aureus-signal/
├── main.py                 # Entry: signal engine
├── main_executor.py        # Entry: strategy executor
├── engine/
│   ├── live_engine.py      # Signal aggregation pipeline (1132 lines)
│   ├── strategy_executor.py # Strategy evaluation pipeline (483 lines)
│   ├── manager.py          # WindowManager — candle window + state management
│   ├── orders.py           # SimulatedTradeManager — order lifecycle
│   ├── ai_validator.py     # AIValidator — LLM audit + hybrid orchestrator
│   ├── registry.py         # EngineRegistry — signal/strategy auto-discovery
│   ├── feature_flags.py    # FeatureFlags — Redis-backed config
│   ├── state.py            # SymbolState — per-symbol persistent state
│   ├── strategies/
│   │   ├── registry.py     # StrategyRegistry — load/evaluate strategies
│   │   ├── template.py     # TemplateStrategy — configurable signal sequences
│   │   ├── base.py         # BaseStrategy — abstract contract
│   │   └── seed_strategies.py  # Bootstrap system strategies
│   ├── signals/            # Individual signal calculators (ATR, EMA, FVG, etc.)
│   ├── providers/          # External decision providers
│   └── logic/              # AI audit gates and judges
└── common/
    └── circuit_breaker.py  # CircuitBreaker for external API calls
```

### Exception Handling Pattern (Current State)

**Well-protected paths (has try/except):**
- `run_signal_engine()` main loop body — outer try/except with sleep(1) recovery [VERIFIED: live_engine.py:567-812]
- `run_strategy_executor()` main loop body — outer try/except with sleep(1) recovery [VERIFIED: strategy_executor.py:278-482]
- Individual signal calculation in `execute_signals_for_candle()` — per-signal try/except [VERIFIED: live_engine.py:62-76]
- Strategy evaluation in `evaluate_all()` — per-strategy try/except [VERIFIED: strategies/registry.py:240-515]
- `brain_worker()` in both engines — try/except with sleep(1) [VERIFIED]
- `validate_trigger()` in AIValidator — try/except returning safe fallback [VERIFIED: ai_validator.py:483-542]
- `generate_pulse()` in AIBrainClient — try/except returning fallback contract [VERIFIED: ai_validator.py:757-778]
- `publish_signal_event()` — try/except returning False [VERIFIED: signal_event_publisher.py:37-48]
- `FeatureFlags.get()` — try/except returning default [VERIFIED: feature_flags.py:57-64]

**Unprotected or partially-protected paths (crash risk):**

### Pattern 1: Fire-and-forget tasks with no error handling
**What:** `asyncio.create_task()` spawns background tasks. If they raise an unhandled exception, Python logs it but the task silently dies — the service does not crash immediately but degrades over time.

**When to use:** Every `asyncio.create_task()` in the codebase.

**Affected tasks in `live_engine.py`:**
| Task | Line | Risk |
|------|------|------|
| `news_refresh_worker(refresh_interval)` | 188 | LOW — has its own try/except |
| `brain_worker()` x2 | 192 | LOW — has its own try/except |
| `integrity_and_recalc_task()` | 455 | **HIGH** — calls `recalculate_all_signals()` which re-raises |
| `listen_for_reload()` | 483 | MEDIUM — pubsub listener, no error handling inside |
| `global_command_stream_listener()` | 534 | LOW — has try/except inside |
| `news_refresh_loop()` (24h variant) | 543 | **HIGH** — NO try/except, calls `NewsProvider.fetch_this_week()` |
| `daily_gc_loop()` | 562 | MEDIUM — has try/except but triggers `recalculate_all_signals()` |
| `recalculate_all_signals()` (from COMMAND handler) | 637 | **HIGH** — function re-raises on failure |
| `insert_single_snapshot()` | 724 | LOW — fire-and-forget, no critical impact |
| `shadow_execute_pulse()` | 789 | LOW — has its own try/except |

**Affected tasks in `strategy_executor.py`:**
| Task | Line | Risk |
|------|------|------|
| `brain_worker()` x2 | 222 | LOW — has its own try/except |
| `listen_for_reload()` | 270 | MEDIUM — pubsub listener, no error handling inside |

**Affected tasks in `tradingagents.py`:**
| Task | Line | Risk |
|------|------|------|
| `log_ta_drift()` | 67 | LOW — has its own try/except |

**Affected tasks in `pivots.py`:**
| Task | Line | Risk |
|------|------|------|
| Unknown async task | 265 | Need to investigate |

### Pattern 2: `recalculate_all_signals()` re-raises exception
**What:** The function wraps its body in try/except but calls `raise` at the end (line 1091 in `live_engine.py`). This means any failure during recalculation bubbles up to the caller.

**When called:**
- From `daily_gc_loop()` (line 555) — the task does NOT catch this exception
- From `integrity_and_recalc_task()` (line 1122) — the task catches exceptions in its own while loop, so this is protected
- From COMMAND handler (line 637) — spawned as fire-and-forget task, exception will be silently lost

**Impact:** If recalculation fails during the daily GC, the `daily_gc_loop` task dies permanently. The service loses daily recalculation capability until restart.

### Pattern 3: `news_refresh_loop()` has no try/except
**What:** Lines 537-543 in `live_engine.py` — a bare `while True` loop that sleeps 86400 seconds and calls `NewsProvider.fetch_this_week()`. No exception handling at all.

```python
async def news_refresh_loop():
    while True:
        await asyncio.sleep(86400)  # 24 hours
        logger.info("[GLOBAL] [news_refresh_loop] 1... Refreshing weekly news calendar...")
        NewsProvider.fetch_this_week()  # ← UNPROTECTED
```

**Impact:** If `fetch_this_week()` raises any exception (network error, parse error, etc.), this task dies permanently. Note: there is also a `news_refresh_worker()` (line 112) that runs every 900 seconds and HAS try/except — so there is redundancy, but the 24h loop is unprotected.

### Pattern 4: `listen_for_reload()` — no error handling
**What:** In both `live_engine.py` (line 461) and `strategy_executor.py` (line 255), the pubsub listener has no try/except. If the pubsub subscription breaks or `load_from_db` fails, the entire loop crashes.

```python
async def listen_for_reload():
    pubsub = r.pubsub()
    await pubsub.subscribe("aureus:cmd:refresh_strategies")
    async for message in pubsub.listen():  # ← If this raises, task dies
        ...
        await symbol_strategies[s].load_from_db(db_pool, s)  # ← If this raises, task dies
```

### Pattern 5: Bare `except:` clause
**What:** `simulated_orders.py` line 170 uses bare `except:` instead of `except Exception:`. This catches `KeyboardInterrupt` and `SystemExit`, preventing clean shutdown.

### Anti-Patterns to Avoid
- **Bare `except:`** — already present in `simulated_orders.py`, should be `except Exception:`
- **Fire-and-forget with no recovery** — `asyncio.create_task()` without wrapping in error-handling coroutine
- **Re-raise from background worker** — `recalculate_all_signals()` raises instead of logging and returning
- **Duplicate news refresh** — two separate news refresh loops (`news_refresh_worker` every 900s and `news_refresh_loop` every 24h) with different error handling

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Task error supervision | Custom try/except per task | `asyncio.TaskGroup` (Python 3.12) | Structured concurrency, automatic cancellation, error propagation |
| Retry logic | Manual retry loops | `tenacity` library | Exponential backoff, jitter, retry conditions, max attempts |
| Circuit breaking | Already built | `common/circuit_breaker.py` | Already exists in project, just needs wider adoption |

**Key insight:** The project already has a `CircuitBreaker` class (`common/circuit_breaker.py`) used only by `TradingAgentsProvider`. It should be applied to Redis connections and DB pool operations as well.

## Runtime State Inventory

Not applicable — this phase is a code-level fix, not a rename/refactor/migration.

## Common Pitfalls

### Pitfall 1: Silent task death from `asyncio.create_task()`
**What goes wrong:** Background tasks raise unhandled exceptions and silently die. The service appears healthy but loses functionality (no daily recalculation, no strategy reload, no news refresh).

**Why it happens:** `asyncio.create_task()` creates a detached task. If it raises, Python logs a warning to stderr but the main loop continues. No restart mechanism exists.

**How to avoid:** Wrap every `asyncio.create_task()` in a "supervisor" coroutine:
```python
async def supervised_task(name: str, coro):
    try:
        await coro
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.critical(f"[SUPERVISOR] Task '{name}' crashed — restarting in 5s", exc_info=True)
        await asyncio.sleep(5)
        # Restart or escalate
```

**Warning signs:** `failed.log` or log files show one-time error messages that never repeat (task died after first error).

### Pitfall 2: `recalculate_all_signals()` re-raise kills parent task
**What goes wrong:** The function raises on failure, killing the `daily_gc_loop` task that called it. After the first failed recalculation, daily GC never runs again.

**Why it happens:** Line 1089-1091 in `live_engine.py`:
```python
except Exception:
    window_manager.set_backfill_status(symbol, "NOT_READY", reason="RECALC_FAILED", updated_at=time.time())
    raise  # ← This kills the caller
```

**How to avoid:** Log and return instead of re-raise. The caller (`daily_gc_loop`) has no error handling.

**Warning signs:** `backfill_status` stuck at "RECALC_FAILED" for a symbol, no recalculation attempts after first failure.

### Pitfall 3: Duplicate news refresh loops with inconsistent protection
**What goes wrong:** Two separate news refresh mechanisms exist with different error handling. One is protected (`news_refresh_worker`), one is not (`news_refresh_loop`).

**Why it happens:** Likely added at different times by different developers. The 900-second worker is used during engine init, the 24-hour loop is a separate background task.

**How to avoid:** Consolidate to a single news refresh mechanism. Remove the unprotected 24h loop.

### Pitfall 4: Pubsub listener crashes on Redis disconnect
**What goes wrong:** `listen_for_reload()` in both engines subscribes to a Redis pubsub channel. If Redis disconnects, `pubsub.listen()` raises and the entire task dies. No reconnection logic.

**Why it happens:** No try/except around the `async for message in pubsub.listen()` loop.

**How to avoid:** Wrap the entire pubsub loop in try/except with reconnection logic.

### Pitfall 5: Exception swallowed by generic `except Exception: pass`
**What goes wrong:** In `live_engine.py` line 369 (warmup signal calculation), exceptions are silently swallowed with `pass`. This masks signal calculation bugs during startup.

**How to avoid:** At minimum log the exception: `logger.error(f"Init signal calc error for {tag}: {e}", exc_info=True)`.

## Code Examples

### Recommended: Supervised background task wrapper
```python
# Source: Pattern adapted from Python 3.11+ asyncio.TaskGroup semantics
async def supervised_background_task(name: str, coro):
    """Wraps a background task with logging, restart, and crash reporting."""
    max_restarts = 5
    restart_count = 0
    while True:
        try:
            await coro
            break  # Task completed normally
        except asyncio.CancelledError:
            logger.info(f"[SUPERVISOR] Task '{name}' cancelled, stopping")
            raise
        except Exception:
            restart_count += 1
            if restart_count > max_restarts:
                logger.critical(
                    f"[SUPERVISOR] Task '{name}' crashed {max_restarts} times — giving up",
                    exc_info=True
                )
                break
            delay = min(2 ** restart_count, 60)  # Exponential backoff, cap at 60s
            logger.warning(
                f"[SUPERVISOR] Task '{name}' crashed (attempt {restart_count}/{max_restarts}), "
                f"restarting in {delay}s",
                exc_info=True
            )
            await asyncio.sleep(delay)
```

### Recommended: Fix `recalculate_all_signals()` to not re-raise
```python
# Current (problematic):
except Exception:
    window_manager.set_backfill_status(symbol, "NOT_READY", reason="RECALC_FAILED", updated_at=time.time())
    raise

# Fixed:
except Exception:
    window_manager.set_backfill_status(symbol, "NOT_READY", reason="RECALC_FAILED", updated_at=time.time())
    logger.error(f"[{symbol}] [recalculate_all_signals] Recalculation failed — will retry on next trigger", exc_info=True)
    # Do NOT re-raise — let the caller's loop continue
```

### Recommended: Wrap `news_refresh_loop` with try/except
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

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Bare `except:` | `except Exception:` with logging | Standard practice | Prevents catching `KeyboardInterrupt` |
| Fire-and-forget `create_task()` | `TaskGroup` (Python 3.11+) | Python 3.11 release | Structured error propagation |
| Manual retry loops | `tenacity` decorator library | Widespread adoption | Exponential backoff with jitter |
| Global try/except around main loop | Supervisor pattern per task | Industry standard | Granular failure isolation |

**Deprecated/outdated:**
- **Bare `except:`** — violates PEP 8, catches `SystemExit`/`KeyboardInterrupt`. Already present in `simulated_orders.py`.
- **`asyncio.get_event_loop()`** — deprecated in Python 3.10+, removed in 3.12. Present in test file `test_story_1_3_verification.py` (causes `RuntimeError`).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `news_refresh_loop()` and `news_refresh_worker()` are both active simultaneously | Pattern 3 | If one replaces the other, the redundancy concern is unfounded |
| A2 | `recalculate_all_signals()` re-raise kills `daily_gc_loop` permanently | Pattern 2 | If the GC loop has restart logic I missed, impact is lower |
| A3 | No process manager (pm2/supervisord) auto-restarts the service on crash | Common Pitfalls 1 | If one exists, crash recovery is partially handled externally |

## Open Questions

1. **Is there an external process manager (pm2, supervisord, Docker restart policy)?**
   - What we know: `Dockerfile` exists in `services/aureus-signal/` [VERIFIED]
   - What's unclear: Whether Docker has `restart: unless-stopped` or similar
   - Recommendation: Check docker-compose.yml or deployment config — if restart policy exists, crash recovery is partially mitigated but functionality degradation (dead tasks) still matters

2. **Are both news refresh loops (`news_refresh_worker` + `news_refresh_loop`) intentionally active?**
   - What we know: Both are spawned via `asyncio.create_task()` in `run_signal_engine()`
   - What's unclear: Whether this is intentional redundancy or accidental duplication
   - Recommendation: Remove the unprotected 24h loop, keep the 900s worker which has proper error handling

3. **Does `TradingAgentsProvider` circuit breaker state persist across restarts?**
   - What we know: `CircuitBreaker` is in-memory only
   - What's unclear: Whether this matters for the service
   - Recommendation: Acceptable — circuit breaker resets on restart, which is standard behavior

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | Runtime | YES | 3.12.9 [VERIFIED] | — |
| pytest | Test execution | YES | 9.0.2 [VERIFIED] | — |
| Redis | Stream consumers, pub/sub, state | Unknown (needs runtime check) | — | Service cannot function without Redis |
| PostgreSQL/TimescaleDB | Candle storage, snapshots, strategies | Unknown (needs runtime check) | — | Service cannot function without DB |
| vLLM/LLM endpoint | AI validation, pulse analysis | Unknown (needs runtime check) | — | AIValidator returns safe fallback [VERIFIED: ai_validator.py:537-542] |
| TradingAgents API | Shadow mode decisions | Unknown (needs runtime check) | — | Circuit breaker + cached responses [VERIFIED: tradingagents.py] |

**Missing dependencies with no fallback:**
- Redis and PostgreSQL are hard dependencies with no code-level fallback. Service requires `restart: always` in Docker or external monitoring.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 [VERIFIED: failed.log] |
| Config file | None detected — uses pytest defaults |
| Quick run command | `pytest tests/ -x -q` |
| Full suite command | `pytest tests/ --cov=engine` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| REQ-39-1 | Strategy executor main loop recovers from unhandled exceptions | unit | `pytest tests/test_strategy_executor_crash.py -x` | ❌ Needs creation |
| REQ-39-2 | Background tasks (news, reload, integrity) don't crash silently | unit | `pytest tests/test_background_task_supervision.py -x` | ❌ Needs creation |
| REQ-39-3 | `recalculate_all_signals()` errors don't kill parent task | unit | `pytest tests/test_recalculate_resilience.py -x` | ❌ Needs creation |
| REQ-39-4 | Pubsub listeners reconnect after Redis disconnect | unit | `pytest tests/test_pubsub_resilience.py -x` | ❌ Needs creation |
| REQ-39-5 | No bare `except:` clauses remain | lint | `grep -rn "except:" engine/ --include="*.py"` | Manual verification |

### Sampling Rate
- **Per task commit:** `pytest tests/test_<specific_file>.py -x`
- **Per wave merge:** `pytest tests/ -x -q`
- **Phase gate:** All new test files pass, grep confirms no bare `except:` remains

### Wave 0 Gaps
- [ ] `tests/test_strategy_executor_crash.py` — covers REQ-39-1: main loop exception recovery
- [ ] `tests/test_background_task_supervision.py` — covers REQ-39-2: supervised background tasks
- [ ] `tests/test_recalculate_resilience.py` — covers REQ-39-3: recalculate error isolation
- [ ] `tests/test_pubsub_resilience.py` — covers REQ-39-4: pubsub reconnection
- [ ] No `conftest.py` with shared fixtures (mock Redis, mock DB pool)

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V5 Input Validation | yes | `json.loads()` wrapped in try/except, `float()` conversions guarded |
| V6 Cryptography | no | No cryptographic operations |
| V8 Error Handling | yes | Logging-based error handling — no stack traces exposed externally |

### Known Threat Patterns for async stream consumers

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Unhandled exception kills consumer | Denial of Service | Supervisor wrapper around background tasks |
| Redis disconnect breaks pubsub | Denial of Service | Reconnection logic with exponential backoff |
| Malformed stream payload crashes parser | Tampering | JSON parsing wrapped in try/except (already present) |
| Exception details leaked in logs | Information Disclosure | Log error messages, not full stack traces to external consumers |

## Sources

### Primary (HIGH confidence)
- [Codebase audit] — All files in `services/aureus-signal/` read and analyzed for exception handling patterns
- `engine/live_engine.py` — 1132 lines, main signal aggregation pipeline [VERIFIED]
- `engine/strategy_executor.py` — 483 lines, strategy evaluation pipeline [VERIFIED]
- `engine/strategies/registry.py` — Strategy evaluation orchestration [VERIFIED]
- `engine/strategies/template.py` — TemplateStrategy implementation [VERIFIED]
- `engine/ai_validator.py` — AI validation with fallback contracts [VERIFIED]
- `engine/orders.py` — SimulatedTradeManager [VERIFIED]
- `engine/state.py` — SymbolState management [VERIFIED]
- `engine/signal_event_publisher.py` — Redis pub/sub publisher [VERIFIED]
- `engine/feature_flags.py` — Redis-backed feature flags [VERIFIED]
- `common/circuit_breaker.py` — CircuitBreaker implementation [VERIFIED]
- `requirements.txt` — Package versions [VERIFIED]

### Secondary (MEDIUM confidence)
- `failed.log` — Existing test failures (6 items, pre-existing) [VERIFIED]
- `strategy.log` — Strategy evaluation test output (2 failures, pre-existing) [VERIFIED]
- Python 3.12.9 runtime [VERIFIED: failed.log header]

### Tertiary (LOW confidence)
- Docker restart policy — Dockerfile exists but docker-compose not checked
- Process manager usage — no evidence of pm2/supervisord in codebase

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — verified against requirements.txt and runtime
- Architecture: HIGH — all source files read and analyzed
- Pitfalls: HIGH — each pitfall traced to specific line numbers in source code
- Environment availability: MEDIUM — Python/pytest verified, runtime services (Redis, DB) not checked

**Research date:** 2026-04-10
**Valid until:** 2026-05-10 (30 days — stable Python async patterns)
