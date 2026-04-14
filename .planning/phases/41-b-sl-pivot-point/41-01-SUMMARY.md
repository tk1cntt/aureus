---
plan_id: "41-01"
status: complete
completed_at: "2026-04-14T02:28:00"
commits:
  - "0f590ab - feat(phase-41): add PIVOT_POINT SL mechanism with swing point HH/LL support"
---

# 41-01: PIVOT_POINT SL Implementation - Summary

## What was built

PIVOT_POINT SL mechanism — a new stop-loss type that places SL based on swing points (HH for SELL, LL for BUY) instead of fixed pips.

## Tasks completed

| Task | Description | Status |
|------|-------------|--------|
| 1 | `_find_pivot_for_sl()` method — finds valid LL/HH from swing_points | ✓ |
| 2 | `PIVOT_POINT` branch in `_calculate_sl_tp()` — calculates SL with offset | ✓ |
| 3 | Seed strategies — TREND_CONT_BULL/BEAR now use PIVOT_POINT | ✓ |
| 4 | 12 unit tests — 6 pivot lookup + 6 SL calculation tests | ✓ |
| 5 | Tests pass (12/12), DB seeded, service restarted | ✓ |

## Key files changed

- `services/aureus-signal/engine/orders.py` — +27 lines (new method + new branch)
- `services/aureus-signal/engine/strategies/seed_strategies.py` — 2 lines changed (SL type)
- `services/aureus-signal/tests/test_pivot_sl.py` — new file, 12 tests

## Verification results

- 12/12 tests passed via `.venv/bin/python -m pytest`
- DB verified: TREND_CONT_BULL/BEAR show `{"type": "PIVOT_POINT", "offset_pips": 5}`
- 6 remaining strategies still show `{"type": "FIXED_PIPS"}` (backward compatible)
- Service restarted successfully, no errors in logs

## Design decisions honored (from CONTEXT.md)

- GA-1: Config `{"type": "PIVOT_POINT", "offset_pips": 5}` — offset is optional, default 0
- GA-2: No fallback to FIXED_PIPS — returns None, None if no pivot found
- GA-3: Strict SMC — only HH for SELL, only LL for BUY, skip broken pivots
