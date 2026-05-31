# Quick Task 260531-n2h: FZ_CONT_BULL/FZ_CONT_BEAR CHOCH→BOS→LIMIT Logic

## Summary

Fixed FZ_CONT_BULL and FZ_CONT_BEAR strategy definitions and implemented entry methods for CHOCH→BOS→LIMIT trading logic.

## Changes

### Task 1: Fix FZ_CONT_BULL syntax and FZ_CONT_BEAR bos_down sequence

**File:** `services/aureus-signal/engine/strategies/seed_strategies.py`

- Fixed FZ_CONT_BULL line 78: added missing comma after `choch_up` dict
- Added `bos_up` sequence step to FZ_CONT_BULL (required for BOS confirmation)
- Added `bos_down` sequence step to FZ_CONT_BEAR (was missing)

**BUY logic (FZ_CONT_BULL):**
1. CHOCH_up occurs
2. Price breaks above CHOCH high = BOS_up
3. BUY LIMIT at low that created BOS high
4. SL at next swing low or nearest LL if no HL

**SELL logic (FZ_CONT_BEAR):**
1. CHOCH_down occurs
2. Price breaks below CHOCH low = BOS_down
3. SELL LIMIT at high that created BOS low
4. SL at next swing high or nearest HH if no LH

### Task 2: Implement FIRST_HIGH_LOW_PIVOT and FIRST_LOW_HIGH_PIVOT entry methods

**File:** `services/aureus-signal/engine/orders.py`

- Added `FIRST_HIGH_LOW_PIVOT` for BUY entry at LL pivot that created BOS_up
- Added `FIRST_LOW_HIGH_PIVOT` for SELL entry at HH pivot that created BOS_down
- Both methods check for BOS marker in swing_points, fallback to first valid pivot

### Task 3: Verify strategy seed

- Python AST validation passed
- FZ_CONT_BULL and FZ_CONT_BEAR both found with correct sequence

## Verification

| Check | Status |
|-------|--------|
| FZ_CONT_BULL choch_up+bos_up sequence | PASS |
| FZ_CONT_BEAR choch_down+bos_down sequence | PASS |
| FIRST_HIGH_LOW_PIVOT entry method | IMPLEMENTED |
| FIRST_LOW_HIGH_PIVOT entry method | IMPLEMENTED |
| seed_strategies.py syntax valid | PASS |

## Commits

- `fix(seed): FZ_CONT_BULL syntax and FZ_CONT_BEAR bos_down sequence`
- `feat(orders): implement FIRST_HIGH_LOW_PIVOT and FIRST_LOW_HIGH_PIVOT entry methods`