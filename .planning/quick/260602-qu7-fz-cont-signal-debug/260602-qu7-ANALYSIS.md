# FZ_CONT Signal Debug — Root Cause Analysis

## Root Cause: BOS Signals Not Implemented

### Evidence

1. **FZ_CONT_BULL** requires sequence: `choch_up` → `bos_up` (seed_strategies.py lines 78-79)
2. **FZ_CONT_BEAR** requires sequence: `choch_down` → `bos_down` (seed_strategies.py lines 102-103)
3. `choch_up`/`choch_down` ARE produced by `StructureSignal` (structure.py lines 358, 728)
4. **`bos_up`/`bos_down` are NOT produced by ANY signal calculator**
5. `signal_factory.py` does NOT register any BOS signal (lines 142-162)
6. No file in `engine/signals/` contains BOS production logic

### Signal Pipeline Status

| Tag | Producer | Registered | Status |
|-----|----------|------------|--------|
| `choch_up` | StructureSignal | signal_factory.py:149 | ✅ Working |
| `choch_down` | StructureSignal | signal_factory.py:150 | ✅ Working |
| `bos_up` | NONE | NONE | ❌ Missing |
| `bos_down` | NONE | NONE | ❌ Missing |

### SMC Theory

- **CHOCH** (Change of Character): Trend reversal signal. Price breaks swing high in downtrend (bullish) or swing low in uptrend (bearish).
- **BOS** (Break of Structure): Trend continuation signal. Price breaks swing high in uptrend (bullish) or swing low in downtrend (bearish).

The structure processor already detects swing points and CHOCH. BOS detection requires:
1. Determine current trend direction (from recent swing points)
2. Detect when price breaks a swing high/low **in the direction of the trend**
3. Emit `bos_up` or `bos_down` tag

### Why FZ_CONT Strategies Never Trigger

FZ_CONT strategies require BOTH `choch_up` AND `bos_up` (or `choch_down` AND `bos_down`). Since `bos_up`/`bos_down` are never emitted, the sequence can never complete. Step 1 (`choch_up`) may match, but step 2 (`bos_up`) never fires → sequence resets on timeout (max_wait=30 candles).

## Implementation Recommendation

BOS signals should be implemented in `StructureSignal` (structure.py) alongside CHOCH detection:

1. Track trend direction based on swing point sequence (HH/HL = bullish, LH/LL = bearish)
2. When price breaks a swing high in bullish trend → emit `bos_up`
3. When price breaks a swing low in bearish trend → emit `bos_down`
4. Store in `state.transient_signals['bos_up']` / `state.transient_signals['bos_down']`
5. Create consumer signals `BOSUpSignal` / `BOSDownSignal` (like CHOCH consumers)
6. Register in `signal_factory.py`

**Complexity**: Medium-High. Requires trend state tracking and careful integration with existing CHOCH logic to avoid conflicts.

## Existing Tests

- `test_strategy_choch_triggers.py` — tests CHOCH triggers (should still pass)
- `test_seed_strategies_fz_cont.py` — tests FZ config (passes, but doesn't test live BOS emission)
- No existing BOS tests
