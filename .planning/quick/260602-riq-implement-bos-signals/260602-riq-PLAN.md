---
quick_id: 260602-riq
mode: quick-full
status: planned
must_haves:
  truths:
    - BOS = break swing high/low WITHOUT opposing extreme (trend continuation)
    - CHOCH = break swing high/low WITH opposing extreme (trend reversal) — already implemented
    - When `zone_base_idx == -1` in structure.py, emit `bos_up` or `bos_down` instead of returning None
    - Need consumer signals + signal_factory registration
    - Must not break existing CHOCH logic
  artifacts:
    - services/aureus-signal/engine/signals/structure.py
    - services/aureus-signal/engine/signals/bos_up.py
    - services/aureus-signal/engine/signals/bos_down.py
    - services/aureus-signal/engine/signal_factory.py
    - services/aureus-signal/tests/test_bos_signals.py
    - .planning/quick/260602-riq-implement-bos-signals/260602-riq-SUMMARY.md
  key_links:
    - services/aureus-signal/engine/signals/structure.py
    - services/aureus-signal/engine/signals/choch_up.py
    - services/aureus-signal/engine/signals/choch_down.py
    - services/aureus-signal/engine/signal_factory.py
---

# Quick Task 260602-riq Plan

## Goal

Implement `bos_up`/`bos_down` signals cho FZ_CONT_BULL/FZ_CONT_BEAR strategies.

## Tasks

### Task 1 — Emit BOS signals in StructureSignal

files:
- `services/aureus-signal/engine/signals/structure.py`

action:
- Before editing, run `gitnexus_impact({target: "StructureSignal", direction: "upstream"})`. If unavailable, stop.
- Add `TAG_BOS_UP = "bos_up"` and `TAG_BOS_DN = "bos_down"` constants
- In `_process_choch` (line 686): when `zone_base_idx == -1`, emit BOS signal instead of returning None
  - Mark pivot as BOS (not CHOCH): `points[pivot_idx]['is_bos'] = True`
  - Store in `transient_signals`: `transient[tag] = signal`
  - Return BOS signal dict
- In `_process_choch_numpy` (line 304): same change for numpy path
- In `_calculate_default_path` (line 116): handle BOS signals same as CHOCH
- In `_calculate_optimized_path`: handle BOS signals same as CHOCH

verify:
- Existing CHOCH tests still pass
- BOS signals emitted when no opposing extreme

done:
- `bos_up`/`bos_down` stored in `transient_signals` by structure processor

### Task 2 — Create consumer signals and register

files:
- `services/aureus-signal/engine/signals/bos_up.py` (new)
- `services/aureus-signal/engine/signals/bos_down.py` (new)
- `services/aureus-signal/engine/signal_factory.py`

action:
- Create `BOSUpSignal` consumer (same pattern as `CHOCHUpSignal`)
- Create `BOSDownSignal` consumer (same pattern as `CHOCHDownSignal`)
- Register in `signal_factory.py` after `choch_down`

verify:
- `cd D:/Aureus/services/aureus-signal && pytest tests/test_bos_signals.py -q`

done:
- BOS signals registered and consumable

### Task 3 — Add tests and verify FZ_CONT integration

files:
- `services/aureus-signal/tests/test_bos_signals.py` (new)

action:
- Test BOS up: bullish trend (HH exists), break swing high, no LL after → should emit `bos_up`
- Test BOS down: bearish trend (LL exists), break swing low, no HH after → should emit `bos_down`
- Test CHOCH still works: break with opposing extreme → should emit CHOCH not BOS
- Run existing tests to verify no regression

verify:
- `cd D:/Aureus/services/aureus-signal && pytest tests/test_bos_signals.py tests/test_structure_o1.py tests/test_strategy_choch_triggers.py -q`

done:
- Tests pass, no regression
