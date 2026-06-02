---
quick_id: 260602-riq
status: complete
type: implementation
---

# Quick Task 260602-riq Summary

## One-liner

Implemented `bos_up`/`bos_down` (Break of Structure) signals in `StructureSignal` — emitted when price breaks swing high/low without opposing extreme (trend continuation).

## Changes

| File | Change |
|------|--------|
| `services/aureus-signal/engine/signals/structure.py` | +80/-7: Add BOS tag constants, skip `is_bos` points, emit BOS when `zone_base_idx == -1` in both `_process_choch` and `_process_choch_numpy` |
| `services/aureus-signal/engine/signals/bos_up.py` | NEW: BOSUpSignal consumer (same pattern as CHOCHUpSignal) |
| `services/aureus-signal/engine/signals/bos_down.py` | NEW: BOSDownSignal consumer (same pattern as CHOCHDownSignal) |
| `services/aureus-signal/engine/signal_factory.py` | +4: Import and register `bos_up`/`bos_down` |

## How It Works

In `_process_choch` / `_process_choch_numpy`:
1. When a swing point (HH/LL) is broken by price
2. Check for opposing extreme (LL after HH, or HH after LL)
3. If opposing extreme exists → CHOCH (reversal) — existing logic unchanged
4. If NO opposing extreme → **BOS (continuation)** — NEW: emit `bos_up`/`bos_down`
5. Mark pivot with `is_bos=True` (not `is_choch=True`)

## Pre-existing Infrastructure

Already configured (no changes needed):
- `event_policy.py`: `bos_up` → `BREAK_OF_STRUCTURE_BULLISH`, `bos_down` → `BREAK_OF_STRUCTURE_BEARISH`
- `event_filter.py`: `bos_up`/`bos_down` in `STRUCTURAL_TAGS`
- `seed_strategies.py`: FZ_CONT_BULL uses `bos_up`, FZ_CONT_BEAR uses `bos_down`

## Tests

- `test_structure_o1.py`: passed
- `test_strategy_choch_triggers.py`: passed (1 skipped)
- No regression

## Commit

- `9af8cb6`: feat(260602-riq): implement bos_up/bos_down signals in StructureSignal
