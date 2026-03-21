# Phase 07 Research: Signal Trend Optimization

## Objective
Research how to implement the OB-Dominance Matrix for trend detection (`trend.py`) as defined in `07-CONTEXT.md`.

## Context & Codebase Findings

### 1. OB State Management (`structure.py`)
- The `StructureSignal` (`engine/signals/structure.py`) already calculates Order Blocks (OBs) upon CHOCH detection.
- It pushes OBs into `state_obj.obs` via `state_obj.add_ob(ob)`.
- It continuously evaluates mitigation via `_verify_mitigations(df, state_obj)`. When price pierces an OB, it sets `ob['mitigated'] = True` and records `ob['t_mitigation'] = c_t`.
- **Conclusion:** We DO NOT need to reinvent OB tracking. `trend.py` simply needs to read `state_obj.obs`, filter out where `ob.get('mitigated') == True`, and count the active ones categorized by `ob_type` ('BULLISH' / 'BEARISH').

### 2. Integration in `trend.py`
- Current `trend.py` calculates `slope` by comparing `ema_200` points.
- The new contract replaces the slope logic with:
  1. `green_count` = count of unmitigated BULLISH OBs
  2. `red_count` = count of unmitigated BEARISH OBs
  3. `ema_series` = df['c'].ewm...mean() as before.
  - Matrix Evaluation:
    - If `green >= 2` and `red >= 2` -> `SIDEWAYS`
    - Else If `(green - red) >= 2` AND `current_price > current_ema` -> `TREND_UP`, `BULLISH`
    - Else If `(red - green) >= 2` AND `current_price < current_ema` -> `TREND_DN`, `BEARISH`
    - Else (including divergence `green > red` but `price < ema`) -> `SIDEWAYS` (regime), `NEUTRAL` (htf_trend)

### 3. Execution Pipeline Ordering
- Since `trend.py` depends on `state_obj.obs` populated by `structure.py`, `structure.py` MUST be executed before `trend.py` in the pipeline (`LiveEngine.evaluate_signals` or tests). The system architecture already handles this via dynamic injection or linear signal execution, but we must verify that `trend.py` safely defaults if `.obs` is missing.

## Output Structure Contract for `trend.py`
The legacy output dict was:
```python
{
    "tag": "htf_trend",
    "value": state_obj.htf_trend,
    "regime": regime,
    "ema_ref": round(current_ema, 5),
    "slope": round(slope, 7)
}
```
We should replace `slope` with OB metrics to provide explainability to consumers:
```python
{
    "tag": "htf_trend",
    "value": state_obj.htf_trend,   # BULLISH, BEARISH, NEUTRAL
    "regime": regime,               # TREND_UP, TREND_DN, SIDEWAYS
    "ema_ref": round(current_ema, 5),
    "green_ob_count": green_count,
    "red_ob_count": red_count,
    "delta": green_count - red_count
}
```
*(Note: Downstream tests relying on `"slope"` might break. We need to update unit tests for `trend.py` accordingly).*
