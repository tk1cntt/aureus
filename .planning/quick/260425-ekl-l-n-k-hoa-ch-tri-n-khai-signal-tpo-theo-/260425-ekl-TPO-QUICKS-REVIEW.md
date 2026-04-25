---
phase: 260425-ekl-l-n-k-hoa-ch-tri-n-khai-signal-tpo-theo-
reviewed: 2026-04-25T00:00:00Z
depth: standard
files_reviewed: 12
files_reviewed_list:
  - services/aureus-signal/engine/signals/tpo_context.py
  - services/aureus-signal/engine/signals/tpo_history.py
  - services/aureus-signal/engine/signals/tpo_detectors.py
  - services/aureus-signal/engine/signals/tpo_strategy.py
  - services/aureus-signal/engine/signals/tpo_replay.py
  - services/aureus-signal/engine/strategies/seed_strategies.py
  - services/aureus-signal/tests/test_tpo_context.py
  - services/aureus-signal/tests/test_tpo_history.py
  - services/aureus-signal/tests/test_tpo_detectors.py
  - services/aureus-signal/tests/test_tpo_strategy_signal.py
  - services/aureus-signal/tests/test_seed_strategies_tpo.py
  - services/aureus-signal/tests/test_tpo_replay.py
findings:
  critical: 0
  warning: 2
  info: 1
  total: 3
status: issues_found
---

# Phase 260425-ekl: Code Review Report

**Reviewed:** 2026-04-25T00:00:00Z
**Depth:** standard
**Files Reviewed:** 12
**Status:** issues_found

## Summary

Reviewed the TPO context/history/detectors/strategy tag bridge/replay harness/seed templates and their tests. The detector/tag contracts are mostly consistent, and the TPO seed template tags match the emitted tags. I found two correctness risks: TPO history uses append order as time order, and strategy seeding logs DB write failures instead of failing the seed operation. There is also one test reliability gap around seed template parsing.

## Warnings

### WR-01: TPO history uses insertion order instead of timestamp order

**File:** `services/aureus-signal/engine/signals/tpo_history.py:22-28`
**Issue:** `append()` only deduplicates by `t` and appends snapshots to the end of the timeframe list. `poc_shift()`, `va_width_change()`, and `freshness_status()` all treat `history[-1]` / the last two items as the latest chronological snapshots. If TPO blocks arrive out of order, a late older block can become the “latest” snapshot, producing stale guards and POC/VA-width shifts from the wrong pair. That can suppress valid TPO candidates or emit candidates using stale context.
**Fix:** Keep each timeframe history sorted by timestamp, then trim the oldest entries. For example:
```python
history.append(snapshot)
history.sort(key=lambda item: item["t"])
if len(history) > self.max_length:
    del history[: len(history) - self.max_length]
```
If `t` may be non-numeric, normalize it in `_build_snapshot()` or explicitly reject unorderable timestamps.

### WR-02: Strategy seeding can silently continue after template upsert failures

**File:** `services/aureus-signal/engine/strategies/seed_strategies.py:512-531`
**Issue:** `_seed_with_conn()` catches every exception during template upsert, logs it, and continues to symbol-strategy activation. If one or more TPO templates fail to insert/update, `name_to_id` simply omits them and the seed run still succeeds, leaving production symbols without the intended TPO strategies while downstream automation sees no failure.
**Fix:** Fail the seed operation after a template upsert error, or collect failures and raise after the loop before syncing symbol strategies. For example:
```python
failures = []
for strat in strategies:
    try:
        ...
    except Exception as e:
        failures.append(strat["name"])
        logger.error(...)
if failures:
    raise RuntimeError(f"Failed to seed strategy templates: {', '.join(failures)}")
```

## Info

### IN-01: Seed-template AST test only finds top-level direct assignments

**File:** `services/aureus-signal/tests/test_seed_strategies_tpo.py:30-39`
**Issue:** `_strategy_templates()` only scans direct statements in `seed_system_strategies()` for a top-level `strategies = ...` assignment. A harmless refactor such as wrapping setup in a helper or adding an `if` block would make the test fail with `strategies literal not found` even if the seed templates remain correct.
**Fix:** Either import a dedicated template-building function, or use `ast.walk()` within the function body to locate the literal assignment more robustly. Keeping seed templates in a module-level constant would also simplify validation.

---

_Reviewed: 2026-04-25T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
