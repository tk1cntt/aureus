# Phase 23: TradingAgents Adapter Implementation - Research

## Objective
Research how to implement Phase 23: tradingagents-adapter-implementation

## Knowledge Gathered
1. **Interface Target**: 
   The adapter must implement the `DecisionProvider` abstract base class from `services/aureus-signal/engine/providers/base.py`.
   - `get_decision(symbol: str, context: Optional[Dict]) -> Optional[DecisionSignal]`
   - `setup()` and `teardown()`

2. **Symbol Mapping**:
   The current configuration is located at `services/aureus-signal/symbols.json`. 
   The adapter will need to parse these strings, optionally fallback to a default translation pattern (e.g. adding separators if TradingAgents requires "XAU-USD" vs "XAUUSD"), or define static mappings for the symbol names.

3. **Cache & Backoff**:
   We must implement an in-memory dictionary with TTL. The cache prevents hitting external HTTP limits for every cycle within a short period (e.g., polling every 10 seconds).

4. **Error & Fallback Handling**:
   Catch generic internal exceptions and HTTP errors (429, 500) and yield `None`. This lets `aureus-signal` gracefully continue back to normal pipelines.

## Validation Architecture
- **Adapter Logic Tests**: Ensure the TTL cache respects time thresholds. Mock `httpx` or external call to simulate timeout/500/429 scenarios, expecting a graceful `None` output.
- **Symbol Mapping Tests**: Assert symbol conversions are processed directly and correctly mapped. 
- **Interface Checks**: Assert that the TradingAgents adapter is a valid subclass of `DecisionProvider`.
