---
quick_id: 260610-rut
mode: quick-full
must_haves:
  - "ORDER_PLAN_INCOMPLETE will not occur for FZ_CONT strategies when SECOND_HIGH_LOW_PIVOT SL type exists"
  - "bos_up/bos_down flags are set on pivot points in structure.py when BOS detected"
  - "CISD H1 fallback in trend_cont_poc_cisd filter allows TREND_CONT to pass without CISD multi-TF config"
  - "TPO context filter passes when TPO H1/M30 data is unavailable but D1 bias exists"
  - "All existing tests pass (no regression)"
---

# Fixbug FZ_CONT, TREND_CONT, TPO Strategy Pipeline

Fix 4 bugs in signal → entry → SL/TP pipeline discovered by full pipeline trace.

## Tasks

### Task 1: Fix SL type `SECOND_HIGH_LOW_PIVOT` not implemented

- **files**: `services/aureus-signal/engine/orders.py`
- **action**: Add `SECOND_HIGH_LOW_PIVOT` handler in `_calculate_sl_tp()` — it's logically identical to `PIVOT_POINT` but selects the 2nd pivot (pivot_index=2) instead of the 1st. Simple: aliased to `PIVOT_POINT` with `pivot_index=2` override.
- **verify**: FZ_CONT_BULL/BEAR SL config `{"type": "SECOND_HIGH_LOW_PIVOT", "offset_pips": 1}` resolves SL successfully instead of None
- **done**: `_calculate_sl_tp()` handles `SECOND_HIGH_LOW_PIVOT` → SL computed

### Task 2: Set `bos_up`/`bos_down` flags on pivot points in structure.py

- **files**: `services/aureus-signal/engine/signals/structure.py`
- **action**: In `_process_choch` (dòng 713) and `_process_choch_numpy` (dòng 308), when BOS detected, add `points[pivot_idx]['bos_up'] = True` (cho bos_up) or `points[pivot_idx]['bos_down'] = True` (cho bos_down)
- **verify**: Entry method `FIRST_HIGH_LOW_PIVOT` can find pivot with `bos_up=True`, `FIRST_LOW_HIGH_PIVOT` can find pivot with `bos_down=True`
- **done**: structure.py sets `bos_up`/`bos_down` flags on BOS detection

### Task 3: Fix CISD H1 fallback in `trend_cont_poc_cisd` filter

- **files**: `services/aureus-signal/engine/strategies/template.py`
- **action**: In `_h1_cisd_matches()`, add fallback: if no CISD H1 tags exist in transient_signals, check for M1 CISD direction via `cisd` tag. If still no CISD data, return True (pass-through — don't block when data unavailable).
- **verify**: TREND_CONT_BULL/BEAR context filter passes even without CISD multi-TF config in symbols.json
- **done**: CISD H1 fallback allows TREND_CONT to pass

### Task 4: Fix TPO context fallback when H1/M30 data missing

- **files**: `services/aureus-signal/engine/strategies/template.py`
- **action**: In `tpo_context` filter branch (dòng 306), add guard: if `timeframes` dict from `TPOContextBuilder` is missing H1/M30 but D1 exists, use D1-only bias check instead of failing.
- **verify**: TPO strategies pass context filter even when H1/M30 TPO data is temporarily unavailable
- **done**: TPO context filter has D1-only fallback
