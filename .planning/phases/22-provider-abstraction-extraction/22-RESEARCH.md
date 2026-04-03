# Phase 22: Provider Abstraction Extraction — Research

**Completed:** 2026-04-03
**Researcher:** Orchestrator (direct codebase analysis)

## Executive Summary

Phase 22 introduces two provider interfaces (`MarketDataProvider`, `DecisionProvider`) into the `aureus-signal` engine and extracts Redis candle consumption into the first concrete implementation (`RedisMarketDataProvider`). The research confirms this is a **pure refactor + interface introduction** with zero behavior change expected.

---

## Codebase Analysis

### 1. Current Candle Contract

**File:** `services/aureus-signal/engine/state.py` (lines 10-40)

```python
@dataclass
class CandleRecord:
    t: int
    price: float
    session: Optional[Dict[str, Any]] = None
    htf_trend: Optional[Dict[str, Any]] = None
    atr_14: Any = None
    zigzag: Optional[Dict[str, Any]] = None
    ema: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    _events_map: Dict[str, Dict[str, Any]] = field(default_factory=dict)
```

`CandleRecord` is **not** the raw OHLCV candle — it's a **signal-enriched record** produced after signal calculation. The raw candle is a plain `dict` with keys: `t`, `o`, `h`, `l`, `c`, `v`, `symbol`.

**Key insight:** The `MarketDataProvider` interface should return the raw candle dict format, not `CandleRecord`. `CandleRecord` is a downstream artifact of signal processing.

### 2. Redis Consumption Point

**File:** `services/aureus-signal/engine/live_engine.py`

The Redis consumption happens at **two levels**:

1. **Stream consumer loop** (lines 536-741): `r.xreadgroup()` that reads from `aureus:stream:{symbol}:candle` and processes entries. This is the **hot path** — where candles enter the engine.

2. **`execute_signals_for_candle()`** (lines 53-80): A standalone function that takes a pre-built DataFrame + state and runs all signal calculators. This function does **not** interact with Redis directly for candle data — it receives data already ingested.

**Current candle ingestion flow:**
```
Redis Stream → xreadgroup → parse dict → window_manager.update() → df, state
→ execute_signals_for_candle(signals, df, state, symbol, redis_client)
```

The `redis_client` parameter in `execute_signals_for_candle` is for **signal calculators** that need Redis access (e.g., reading config), NOT for candle ingestion.

### 3. Extraction Boundaries

The Redis-specific candle ingestion logic is embedded in `run_signal_engine()` between lines 536-741. To create a `RedisMarketDataProvider`, the extraction should capture:

- **Connection setup**: Redis client creation (lines 146-151)
- **Consumer group setup**: `xgroup_create` (lines 229-236)
- **Stream reading**: `xreadgroup` loop (lines 540-544)
- **Candle parsing**: Dict construction from stream entries (lines 556-573)
- **DB insertion**: `executemany` for candle persistence (lines 576-584)

However, **full extraction risks too much disruption** for Phase 22. The safer approach is:

- Define the `MarketDataProvider` ABC with a `get_candles()` or `subscribe()` method
- Create `RedisMarketDataProvider` that wraps the existing Redis stream consumption pattern
- Leave `run_signal_engine()` calling through the provider interface but preserve the same internal behavior

### 4. Places That Create candle_data Dicts

The raw candle dict `{t, o, h, l, c, v, symbol}` is constructed in multiple places:
- `run_signal_engine()` warm-up loop (lines 296-299, 313-316, 354-358)  
- `run_signal_engine()` main loop (lines 617-619)
- `recalculate_all_signals()` (lines 908-913)

All follow the same pattern: reading from DB rows or Redis stream entries and building the canonical dict.

### 5. Downstream Consumers (What NOT to Touch)

- `ContextBuilder.build_market_context()` — uses `state_obj` and DataFrame, no direct candle dependency
- `ContextBuilder.build_pulse_context()` — uses `state.log_signal_normalize`, no direct candle dependency
- `AIValidator` — orchestrates ContextBuilder and AIBrainClient, no candle dependency
- Signal calculators — receive DataFrame and state, no Redis candle dependency
- Strategy registry — receives DataFrame, signals, state

**Conclusion:** Downstream consumers are decoupled from candle ingestion already. The provider abstraction only affects the ingestion layer.

### 6. DecisionProvider Pattern

From the TradingAgents framework analysis:
- `TradingAgentsGraph.propagate(company_name, trade_date)` returns `(final_state, processed_signal)`
- `SignalProcessor.process_signal()` extracts a rating: BUY/OVERWEIGHT/HOLD/UNDERWEIGHT/SELL
- This is a **daily-cadence** operation (not per-tick)

The `DecisionProvider` ABC should model this pattern:
- Input: symbol, date/timestamp
- Output: `DecisionSignal` dataclass with action, confidence, reasoning, timestamp, symbol, source

### 7. Existing Test Surface

60+ test files exist in `services/aureus-signal/tests/`. Key tests importing from `live_engine`:
- 8 tests import `execute_signals_for_candle` directly
- These tests pass `None` as `redis_client` — confirming the function works without Redis for signal calculation
- No tests currently test the Redis stream consumption loop itself (it's an async runtime concern)

### 8. Design Recommendations

1. **Use `abc.ABC`** over `typing.Protocol` — the project is runtime-oriented with dataclasses, not a library exposing type contracts.

2. **MarketDataProvider interface:**
   ```python
   class MarketDataProvider(ABC):
       @abstractmethod
       async def subscribe(self, symbol: str) -> AsyncIterator[Dict[str, Any]]:
           """Yield candle dicts {t, o, h, l, c, v, symbol}."""
       
       @abstractmethod
       async def get_historical(self, symbol: str, limit: int) -> List[Dict[str, Any]]:
           """Fetch historical candles for warm-up."""
   ```

3. **DecisionProvider interface:**
   ```python
   class DecisionProvider(ABC):
       @abstractmethod
       async def get_decision(self, symbol: str, context: Dict[str, Any]) -> Optional[DecisionSignal]:
           """Request a trading decision for a symbol."""
   ```

4. **RedisMarketDataProvider** should wrap the existing stream consumption pattern but expose it through the ABC interface.

5. **Backward compatibility:** The default constructor path in `run_signal_engine()` should instantiate `RedisMarketDataProvider` when no explicit provider is configured.

---

## Validation Architecture

### Test Strategy
- **Unit tests for ABCs:** Verify interface contracts, ensure `RedisMarketDataProvider` implements all abstract methods
- **Behavior regression:** Run existing 60+ test suite — must pass unchanged
- **Integration smoke test:** Verify `RedisMarketDataProvider` can be constructed with same params as current Redis setup

### Risk Assessment
- **LOW RISK:** Pure interface introduction with concrete implementation wrapping existing code
- **Key risk:** Breaking existing imports if `CandleRecord` or signal-related code moves unexpectedly
- **Mitigation:** Keep all existing modules in place; `providers/` is additive only

---

## RESEARCH COMPLETE
