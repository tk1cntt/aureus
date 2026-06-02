---
quick_id: 260602-qu7
status: complete
type: debug-analysis
---

# Quick Task 260602-qu7 Summary

## One-liner

FZ_CONT_BULL/BEAR never trigger because `bos_up`/`bos_down` signal tags have no signal calculator — they are referenced in strategy definitions but never produced by the signal pipeline.

## Root Cause

**`bos_up` and `bos_down` are not implemented.**

- `signal_factory.py` does not register any BOS signal
- No file in `engine/signals/` produces BOS tags
- `structure.py` only produces `choch_up`/`choch_down`
- FZ_CONT strategies require CHOCH then BOS sequence → sequence never completes

## Pipeline Stage Verdict

| Stage | Component | Status |
|-------|-----------|--------|
| Signal Production | BOS signals | ❌ NOT IMPLEMENTED |
| Signal Registration | signal_factory.py | ❌ BOS not registered |
| Sequence Definition | seed_strategies.py | ✅ Correct (choch→bos) |
| Context Filter | template.py | ✅ No filter (empty) |
| Sequence Matching | template.py | ❌ Blocked (no BOS tags) |

## Recommendation

Implement BOS (Break of Structure) detection in `StructureSignal`:
1. Track trend direction from swing points
2. Detect price breaking swing high/low in trend direction
3. Emit `bos_up`/`bos_down` to `transient_signals`
4. Create consumer signals and register in `signal_factory.py`

**Complexity**: Medium-High. Recommend dedicated quick task or phase for implementation.

## Files Changed

None — analysis only, no production fix applied.

## Tests

- Existing FZ_CONT config tests: pass
- No BOS-specific tests exist
