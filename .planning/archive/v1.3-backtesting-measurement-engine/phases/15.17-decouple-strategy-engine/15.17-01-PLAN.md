---
wave: 1
depends_on: []
files_modified:
  - services/aureus-signal/engine/live_engine.py
  - services/aureus-signal/engine/strategy_executor.py
autonomous: true
---

<objective>
Refactor the monolithic signal engine into two decoupled components: `aureus-signal-aggregator` and `aureus-strategy-executor`. The aggregator calculates signals and pushes them to a new per-symbol Redis stream. The executor consumes this stream to evaluate strategies asynchronously without building candle data.
</objective>

<requirements>
- PARITY-01
- PARITY-02
- PARITY-03
</requirements>

<must_haves>
- `live_engine.py` (Aggregator) retains State Persistence and TimescaleDB Snapshotting logic.
- `live_engine.py` (Aggregator) pushes serialized signal contexts to `aureus:stream:{symbol}:signals`.
- `strategy_executor.py` (Executor) independently consumes the signals stream and processes `evaluate_all`.
- `strategy_executor.py` retains Observability metadata handling, AI queuing, and Trade Manager simulation.
</must_haves>

<features>

<task>
<description>Create the asynchronous Strategy Executor worker</description>
<read_first>
- services/aureus-signal/engine/live_engine.py
</read_first>
<action>
1. Create a new file `services/aureus-signal/engine/strategy_executor.py`.
2. Implement a new class/worker `StrategyExecutorActor` or standalone async process that connects to Redis.
3. Set up a consumer group on Redis for stream `aureus:stream:{symbol}:signals`.
4. Migrate the strategy evaluation block from `live_engine.py` (lines 692+) into this worker:
   - Call `symbol_strategies[symbol].evaluate_all(...)`.
   - Call `trade_manager` update logic and AI trigger (`ai_queue`).
   - Emit rejection logs to `aureus:stream:{symbol}:orders`.
5. Ensure the worker does NOT build internal candle structures, relying instead purely on the deserialized signal payload from the stream.
</action>
<acceptance_criteria>
- `services/aureus-signal/engine/strategy_executor.py` exists and contains an async loop consuming `aureus:stream:{symbol}:signals`.
- The words `evaluate_all`, `ai_queue`, and `trade_manager` exist in `strategy_executor.py`.
</acceptance_criteria>
</task>

<task>
<description>Update Signal Aggregator to emit signal stream and remove executor logic</description>
<read_first>
- services/aureus-signal/engine/live_engine.py
</read_first>
<action>
1. In `services/aureus-signal/engine/live_engine.py`, locate the processing block inside the main event loop (around line ~692+).
2. Remove the calls to `strategy_results = symbol_strategies[symbol].evaluate_all(...)`, trade manager updates, AI queuing, and order rejection publishing.
3. Instead of evaluating strategies natively, serialize `log_signal_normalize` and relevant `Structure` or `Indicator` variables needed by the strategy evaluator into a JSON payload.
4. Execute `redis_client.xadd(f"aureus:stream:{symbol}:signals", {"payload": json_data}, maxlen=1000)` right after signal tracking and state persistence.
5. Retain all logic that saves `aureus:state:{symbol}` to Redis and TimescaleDB snapshotting.
</action>
<acceptance_criteria>
- `services/aureus-signal/engine/live_engine.py` no longer contains the call `evaluate_all`.
- `services/aureus-signal/engine/live_engine.py` contains `xadd(f"aureus:stream:{symbol}:signals"`.
- Features like `TimescaleDB` persistence and `aureus:state` updates remain untouched in `live_engine.py`.
</acceptance_criteria>
</task>

</features>

<verification>
### Unit Tests (Aggregator Stream)
```bash
pytest services/aureus-signal/tests/test_strategy_choch_triggers.py -v
```
Will demonstrate whether the core parsing of candle states still works natively before emission.

### Integration Validation (End-to-end Decoupled Parity)
```bash
pytest services/aureus-signal/tests -v
```
Run `test_structure_integration_execute_signals_for_candle.py` or new tests to prove the decoupling returns identical simulated outcomes.
</verification>
