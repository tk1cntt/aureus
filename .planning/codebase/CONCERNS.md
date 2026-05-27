# Codebase Concerns

**Analysis Date:** 2026-05-27

## Tech Debt

**Signal engine monolith:**
- Issue: `run_signal_engine` mixes service boot, Redis consumer groups, historical hydration, candle persistence, live signal calculation, strategy execution, AI queueing, checkpointing, sparse snapshot writes, global config listener, news refresh, and integrity recovery in one long async function.
- Files: `D:/Aureus/.claude/worktrees/agent-aa1e45131babea93e/services/aureus-signal/engine/live_engine.py`
- Impact: Small changes to live processing can affect boot recovery, AI jobs, DB persistence, Redis state, and strategy execution. Error handling is broad and makes failures hard to isolate.
- Fix approach: Split into focused modules: bootstrap/hydration, stream consumer, candle persistence, signal evaluation, strategy execution, snapshot writer, AI worker, integrity worker. Keep `run_signal_engine` as orchestration only.

**DB writer duplicated tick insert:**
- Issue: Tick batch path inserts `aureus_ticks` twice for same `data_rows`: first `copy_records_to_table` call before ack setup, second call before ack.
- Files: `D:/Aureus/.claude/worktrees/agent-aa1e45131babea93e/services/aureus-db-writer/main.py`
- Impact: Duplicate tick records or unique-conflict failures can occur depending schema constraints. Redis acks only happen after second insert, so first insert can survive while message remains pending on failure.
- Fix approach: Keep one insert path. If idempotency is required, use `INSERT ... ON CONFLICT` equivalent or stage table flow, then ack only after successful single durable write.

**Backfill code has duplicated variable assignment and deprecated flow:**
- Issue: `process_backfill` assigns `processed = 0` twice and keeps deprecated recalculation command commented in live path.
- Files: `D:/Aureus/.claude/worktrees/agent-aa1e45131babea93e/services/aureus-gateway/main.py`
- Impact: Low direct runtime impact, but command/recalc behavior is unclear when debugging backfill and signal catch-up.
- Fix approach: Remove duplicate assignment and replace deprecated comment block with current ownership contract: gateway only writes stream/latest, signal engine owns integrity and recalculation.

**Nautilus node is mostly lifecycle shell:**
- Issue: `get_node_config` returns empty `TradingNodeConfig()` when Nautilus is installed and only returns useful fallback dict when dependency is missing. `run_live_node` creates node and marks healthy but does not wire data/execution clients or start trading node behavior.
- Files: `D:/Aureus/.claude/worktrees/agent-aa1e45131babea93e/services/aureus-nautilus-node/config.py`, `D:/Aureus/.claude/worktrees/agent-aa1e45131babea93e/services/aureus-nautilus-node/main.py`
- Impact: Service health can be green while no live Nautilus data/execution integration is active. Production rollout can trust a container that is only sleeping in LIVE phase.
- Fix approach: Build real `TradingNodeConfig` from `NautilusNodeSettings`, register data/execution clients, start node explicitly, and expose readiness tied to active subscriptions/orders.

**Execution client hardcodes XAUUSD stream:**
- Issue: `_poll_loop` and `_poll_orders_once` only read `aureus:stream:XAUUSD:orders` even though policy accepts a symbol whitelist.
- Files: `D:/Aureus/.claude/worktrees/agent-aa1e45131babea93e/services/aureus-nautilus-node/execution_client.py`
- Impact: Orders for `BTCUSD`, `ETHUSD`, `USTEC`, `USDJPY`, `EURUSD`, `GBPUSD`, and `AUDUSD` are ignored in Nautilus client path.
- Fix approach: Build stream map from `ExecutionRiskPolicy.symbol_whitelist` and persist `_last_ids` per stream.

**Ad-hoc test scripts mixed with pytest tests:**
- Issue: Some tests use `if __name__ == "__main__"`, `print`, and custom async main instead of pytest assertions/fixtures. Test discovery can skip them.
- Files: `D:/Aureus/.claude/worktrees/agent-aa1e45131babea93e/services/aureus-signal/unittest/test_recalculate_all_signals.py`, `D:/Aureus/.claude/worktrees/agent-aa1e45131babea93e/services/aureus-signal/unittest/test_checkpoint_marker.py`, `D:/Aureus/.claude/worktrees/agent-aa1e45131babea93e/services/aureus-signal/unittest/test_live_sparse_storage.py`
- Impact: CI can pass while checkpoint, sparse storage, or marker behavior is untested.
- Fix approach: Convert script tests to pytest async tests, use `pytest.mark.asyncio`, and add them to CI test command.

## Known Bugs

**Offline signal precompute entrypoint calls missing `main`:**
- Symptoms: Running `python signal_computer.py ...` raises `NameError: name 'main' is not defined` because `asyncio.run(main())` exists but `main` is not declared. Dead code after `return` also references `args` out of scope.
- Files: `D:/Aureus/.claude/worktrees/agent-aa1e45131babea93e/services/aureus-signal/signal_computer.py`
- Trigger: Execute `services/aureus-signal/signal_computer.py` as CLI.
- Workaround: Import and call `precompute_signals(...)` from another script with explicit args.

**Recalculate unit mock expects stale warmup limit:**
- Symptoms: `MockDBPool.fetch` checks for `LIMIT 200`, while live `recalculate_all_signals` queries `LIMIT 1500`; warmup branch in test returns empty data unintentionally.
- Files: `D:/Aureus/.claude/worktrees/agent-aa1e45131babea93e/services/aureus-signal/unittest/test_recalculate_all_signals.py`, `D:/Aureus/.claude/worktrees/agent-aa1e45131babea93e/services/aureus-signal/engine/live_engine.py`
- Trigger: Run script test expecting warmup rows to be included.
- Workaround: Update mock to match `LIMIT 1500` or detect `ORDER BY time DESC` query intent.

**Chart component removes chart in two cleanup effects:**
- Symptoms: `SMCChart` creates chart in one effect and removes it there, then another effect subscribed by symbol also removes `chartRef.current`. Double cleanup and duplicated resize/listener logic can race during symbol changes or React strict-mode remounts.
- Files: `D:/Aureus/.claude/worktrees/agent-aa1e45131babea93e/services/aureus-dashboard/web/src/components/SMCChart.tsx`
- Trigger: Switch symbols, unmount chart, or run React strict mode with effects mounted/unmounted twice.
- Workaround: Keep chart lifecycle in one effect; keep layout persistence subscription separate but never call `chart.remove()` outside owner effect.

**MQL5 candle close detection likely sends wrong bar:**
- Symptoms: `CheckAndSendCandleForSymbol` reads `CopyTime(..., 0, 2, barTimes)` then treats `barTimes[1]` as current and `barTimes[0]` as previous. MQL5 series arrays from `CopyTime` commonly return current bar at index 0 and previous at index 1 unless explicitly handled.
- Files: `D:/Aureus/.claude/worktrees/agent-aa1e45131babea93e/mql5/AureusProvider.mq5`
- Trigger: New M1 candle polling on timer.
- Workaround: Verify array ordering in MT5 log and align `lastCandleTime` update with the candle actually sent by `CopyRates(sym, PERIOD_M1, 1, 1, rates)`.

**Dashboard backtest chart returns live candles even for run_id:**
- Symptoms: `/api/v1/chart/{symbol}?run_id=...` fetches candles only from `aureus_candles`, while backtest code writes isolated table `aureus_backtest_candles` and snapshots from `aureus_backtest_snapshots`.
- Files: `D:/Aureus/.claude/worktrees/agent-aa1e45131babea93e/services/aureus-dashboard/api/main.py`, `D:/Aureus/.claude/worktrees/agent-aa1e45131babea93e/services/aureus-signal/engine/backtest_engine.py`
- Trigger: View backtest run with symbols/time ranges not matching live `aureus_candles`.
- Workaround: Query `aureus_backtest_candles` when `run_id` is supplied, or guarantee backtest candle table mirrors live candle table.

## Security Considerations

**Unauthenticated open gateway ports:**
- Risk: ZMQ and TCP listeners bind to `0.0.0.0` without authentication, authorization, TLS, message signature, or symbol allowlist. Any network peer reaching ports can inject candles/backfills and alter trading state.
- Files: `D:/Aureus/.claude/worktrees/agent-aa1e45131babea93e/services/aureus-gateway/main.py`, `D:/Aureus/.claude/worktrees/agent-aa1e45131babea93e/docker-compose.dev.yml`
- Current mitigation: Pydantic shape validation for message fields. Docker dev network limits some internal access, but ports are published to host.
- Recommendations: Bind to localhost for dev by default, add HMAC or mTLS for EA messages, enforce symbol whitelist, limit backfill sizes, and reject stale/future timestamps.

**Dashboard mutation endpoints lack authentication:**
- Risk: Strategy create/update/delete/toggle, forced recovery, and LLM model changes are exposed as API endpoints without auth.
- Files: `D:/Aureus/.claude/worktrees/agent-aa1e45131babea93e/services/aureus-dashboard/api/main.py`
- Current mitigation: CORS origin list limits browser origins only; non-browser clients can call endpoints directly.
- Recommendations: Add API auth for all non-GET or operational endpoints, require admin role for strategy/model/recovery mutations, and audit changes to DB.

**Default credentials and secrets in configs:**
- Risk: Development compose uses fallback database URL password `aureus_password`; Grafana admin password is literal `admin`; DB writer defaults `POSTGRES_PASSWORD` to `aureus_secure_pass`.
- Files: `D:/Aureus/.claude/worktrees/agent-aa1e45131babea93e/docker-compose.dev.yml`, `D:/Aureus/.claude/worktrees/agent-aa1e45131babea93e/services/aureus-db-writer/main.py`, `D:/Aureus/.claude/worktrees/agent-aa1e45131babea93e/services/aureus-dashboard/api/main.py`, `D:/Aureus/.claude/worktrees/agent-aa1e45131babea93e/services/aureus-signal/engine/live_engine.py`
- Current mitigation: `${DB_PASSWORD}` is supported for some services. `.env` file exists but contents were not read.
- Recommendations: Remove hardcoded production-capable defaults, fail fast if passwords are unset outside dev, and use per-service secret injection.

**Dynamic table names in snapshot inserts:**
- Risk: `insert_single_snapshot` and `batch_insert_snapshots` interpolate `table_name` into SQL. Current callers pass internal constants, but future external input could become SQL injection.
- Files: `D:/Aureus/.claude/worktrees/agent-aa1e45131babea93e/services/aureus-signal/engine/snapshot_utils.py`, `D:/Aureus/.claude/worktrees/agent-aa1e45131babea93e/services/aureus-signal/engine/backtest_engine.py`
- Current mitigation: Values are internal strings `aureus_signal_snapshots` and `aureus_backtest_snapshots`.
- Recommendations: Validate `table_name` against explicit allowlist before formatting SQL.

**AI prompt and response payload persistence can store sensitive data:**
- Risk: `request_payload`, `response_payload`, and raw LLM outputs are stored in `aureus_ai_analysis`; prompts include market state, order context, and possibly account/trade details.
- Files: `D:/Aureus/.claude/worktrees/agent-aa1e45131babea93e/services/aureus-signal/engine/live_engine.py`, `D:/Aureus/.claude/worktrees/agent-aa1e45131babea93e/services/aureus-signal/engine/ai_validator.py`, `D:/Aureus/.claude/worktrees/agent-aa1e45131babea93e/services/aureus-dashboard/api/main.py`
- Current mitigation: Not detected.
- Recommendations: Redact account identifiers, position sizes if sensitive, and raw model reasoning unless explicitly needed for audit.

## Performance Bottlenecks

**Per-candle DataFrame rebuild:**
- Problem: Every candle update rebuilds `pd.DataFrame(window)` from full in-memory window.
- Files: `D:/Aureus/.claude/worktrees/agent-aa1e45131babea93e/services/aureus-signal/engine/manager.py`
- Cause: `WindowManager.update` stores list of candles and recreates DataFrame on each message for every symbol.
- Improvement path: Keep rolling arrays/deques, append/update DataFrame incrementally, or let signal calculators consume typed lists/NumPy arrays. Benchmark with 8 symbols and `max_window=2000`.

**Full ZigZag recalculation by default:**
- Problem: `ZigZagPro.update` defaults `incremental=False`, clears buffers, and recalculates entire rate window. Live code generally calls signal calculators every candle; if ZigZag signal uses default mode, cost is O(window) per candle.
- Files: `D:/Aureus/.claude/worktrees/agent-aa1e45131babea93e/services/aureus-signal/engine/common/zigzag_pro2.py`, `D:/Aureus/.claude/worktrees/agent-aa1e45131babea93e/services/aureus-signal/engine/live_engine.py`
- Cause: Full recalculation chosen for stability with sliding windows; incremental mode has extra drift assumptions.
- Improvement path: Enable incremental mode only after regression coverage for sliding window drift, outside bars, inside bars, and pivot replacement. Keep full mode as fallback on gap/recovery.

**Fire-and-forget snapshot writes can pile up:**
- Problem: Live loop creates untracked tasks for every snapshot write and never awaits or backpressures them.
- Files: `D:/Aureus/.claude/worktrees/agent-aa1e45131babea93e/services/aureus-signal/engine/live_engine.py`, `D:/Aureus/.claude/worktrees/agent-aa1e45131babea93e/services/aureus-signal/engine/snapshot_utils.py`
- Cause: `asyncio.create_task(insert_single_snapshot(...))` is used inside candle processing.
- Improvement path: Use bounded async queue with one/few snapshot writer workers, batch writes, track failures, and expose queue depth metrics.

**Redis/DB scans in dashboard and workers:**
- Problem: Symbol listing scans Redis patterns; DB writer and Nautilus bridge scan Redis streams repeatedly; metrics exporter polls every symbol and stream every interval.
- Files: `D:/Aureus/.claude/worktrees/agent-aa1e45131babea93e/services/aureus-dashboard/api/main.py`, `D:/Aureus/.claude/worktrees/agent-aa1e45131babea93e/services/aureus-db-writer/main.py`, `D:/Aureus/.claude/worktrees/agent-aa1e45131babea93e/services/aureus-nautilus-bridge/main.py`, `D:/Aureus/.claude/worktrees/agent-aa1e45131babea93e/services/aureus-bridge-metrics-exporter/main.py`
- Cause: Dynamic discovery uses `SCAN` in hot paths; metrics uses stream lengths and latest ranges repeatedly.
- Improvement path: Maintain symbol/stream registry keys, discover on pubsub/config change, and reduce dashboard Redis scan frequency with short cache TTL.

**Chart overlays recreate many series on each update:**
- Problem: `SMCChart` removes and recreates CHOCH and OB series every `smcState`/`data` update; OB rendering builds candle data by iterating all candles for every OB.
- Files: `D:/Aureus/.claude/worktrees/agent-aa1e45131babea93e/services/aureus-dashboard/web/src/components/SMCChart.tsx`
- Cause: Overlay state is represented as many lightweight-chart series instead of stable series pool keyed by OB/CHOCH id.
- Improvement path: Reuse series by object id/time range, diff overlay changes, cap displayed OBs, and precompute candle time index for range slicing.

## Fragile Areas

**Checkpoint plus sparse snapshot recovery:**
- Files: `D:/Aureus/.claude/worktrees/agent-aa1e45131babea93e/services/aureus-signal/engine/live_engine.py`, `D:/Aureus/.claude/worktrees/agent-aa1e45131babea93e/services/aureus-signal/engine/state_snapshot.py`, `D:/Aureus/.claude/worktrees/agent-aa1e45131babea93e/services/aureus-signal/unittest/test_recalculate_all_signals.py`
- Why fragile: Startup and recalculation choose `effective_start_time` from checkpoint if newer than last snapshot. With sparse snapshots, checkpoint can skip candles that never produced snapshots, and hydration uses latest snapshot state plus delta after checkpoint.
- Safe modification: Test combinations of `snapshot_mode=FULL` and sparse mode, checkpoint older/newer than snapshot, service downtime with no structural events, and gap backfill replay.
- Test coverage: Partial script-style unit exists; needs DB-backed e2e with real `aureus_candles`, `aureus_signal_snapshots`, and Redis checkpoint.

**Backfill command parsing in MQL5:**
- Files: `D:/Aureus/.claude/worktrees/agent-aa1e45131babea93e/mql5/AureusProvider.mq5`, `D:/Aureus/.claude/worktrees/agent-aa1e45131babea93e/mql5/AureusSocketLib.mqh`, `D:/Aureus/.claude/worktrees/agent-aa1e45131babea93e/services/aureus-gateway/main.py`
- Why fragile: Commands are parsed with string search and substring extraction, socket receive reads available bytes once, and newline/multiple command framing is not handled as a buffer.
- Safe modification: Add line-buffered receive in `AureusSocket`, parse one JSON command at a time, and add malformed/partial command tests in MT5 or simulator.
- Test coverage: Not detected for MQL5 command parsing.

**Redis stream ack on parse failures:**
- Files: `D:/Aureus/.claude/worktrees/agent-aa1e45131babea93e/services/aureus-db-writer/main.py`, `D:/Aureus/.claude/worktrees/agent-aa1e45131babea93e/services/aureus-nautilus-bridge/main.py`, `D:/Aureus/.claude/worktrees/agent-aa1e45131babea93e/services/aureus-signal/engine/live_engine.py`
- Why fragile: Different services ack failed messages differently. Bridge acks in exception path, live engine acks malformed processing entries, DB writer only acks rows that parse and write; failed parsed messages can stay pending without dead-letter policy.
- Safe modification: Standardize error policy: validate, dead-letter malformed messages with reason, ack dead-lettered entries, and retry transient DB/Redis failures with bounded attempts.
- Test coverage: Tests cover some DB writer happy paths only.

**AI audit dependency in trade path:**
- Files: `D:/Aureus/.claude/worktrees/agent-aa1e45131babea93e/services/aureus-signal/engine/live_engine.py`, `D:/Aureus/.claude/worktrees/agent-aa1e45131babea93e/services/aureus-signal/engine/ai_validator.py`
- Why fragile: Trade triggers enqueue audit tasks with references/copies of `df`, `state`, and `order`; failures are logged but do not guarantee operator visibility. Model selection is mutable via Redis/API.
- Safe modification: Treat algorithmic reject/accept path as deterministic baseline, persist audit task status, expose queue length/failures, and require auth for model changes.
- Test coverage: Not detected for full AI queue plus order decision e2e.

**Backtest/live divergence:**
- Files: `D:/Aureus/.claude/worktrees/agent-aa1e45131babea93e/services/aureus-signal/engine/backtest_engine.py`, `D:/Aureus/.claude/worktrees/agent-aa1e45131babea93e/services/aureus-signal/engine/live_engine.py`, `D:/Aureus/.claude/worktrees/agent-aa1e45131babea93e/services/aureus-dashboard/api/main.py`
- Why fragile: Backtest has separate consumer loop, tables, trade manager, event cleanup, and Redis key prefixing. Dashboard partly reads backtest snapshots but live candles. Fixes in live engine may not reach backtest engine.
- Safe modification: Share candle-to-signal pipeline function between live and backtest; keep only IO isolation separate.
- Test coverage: Some backtest behavior relies on manual scripts; not detected for dashboard backtest render e2e.

## Scaling Limits

**In-memory per-symbol windows:**
- Current capacity: Live signal engine uses `WindowManager(max_window=2000)` for each symbol; default config lists 8 symbols in `docker-compose.dev.yml`.
- Limit: DataFrame rebuild and full signal recalculation cost grows with `symbols * max_window * signals`. More symbols/timeframes can saturate event loop.
- Scaling path: Partition symbols across worker processes, avoid per-candle DataFrame rebuild, and make signal calculators incremental.

**Redis stream maxlen and consumer pending entries:**
- Current capacity: Gateway writes candle/tick/backfill streams with `maxlen=5000 approximate`; live signal reads `count=500`; DB writer reads `BATCH_SIZE` default 50.
- Limit: Backfill bursts can trim streams before slow consumers process all entries; pending failed messages can accumulate without `XAUTOCLAIM`/dead-letter handling.
- Scaling path: Use consumer lag metrics, tune maxlen per stream, add pending recovery, and use separate high-volume backfill channel or DB direct ingest.

**AI worker throughput:**
- Current capacity: Two brain workers, LLM calls timeout 45-60 seconds, pulse cooldown per symbol 60 seconds.
- Limit: Multi-symbol structural events can queue audits/pulses faster than workers complete, delaying trade decisions or market pulse updates.
- Scaling path: Separate audit and pulse worker pools, drop/coalesce stale pulse tasks, preserve audit priority, and expose queue depth/age metrics.

**Dashboard API DB connections:**
- Current capacity: Most endpoints call `asyncpg.connect` per request and close after query.
- Limit: Chart and AI history endpoints can create many short-lived connections under dashboard refresh/load.
- Scaling path: Use app lifespan-managed asyncpg pool and Redis connection health lifecycle.

## Dependencies at Risk

**Nautilus Trader nightly image:**
- Risk: Dev compose uses `ghcr.io/nautechsystems/nautilus_trader:nightly`, which can change behavior without code changes.
- Impact: `TradingNodeConfig`, `LiveTradingNode`, and execution client integration can break unexpectedly.
- Migration plan: Pin a known Nautilus version/tag and run `services/aureus-nautilus-node/tests` in CI before upgrades.

**TimescaleDB latest image:**
- Risk: Dev compose uses `timescale/timescaledb:latest-pg15`.
- Impact: Schema migration, extension behavior, or image changes can break local/dev DB startup.
- Migration plan: Pin exact TimescaleDB image version and document upgrade path with DB e2e validation.

**Redis stream behavior relied on across services:**
- Risk: Gateway, signal engine, DB writer, bridge, and metrics exporter all rely on Redis streams with different consumer patterns.
- Impact: Stream trim, pending entries, duplicate IDs, or restart ordering can cause data loss, duplicate writes, or stale metrics.
- Migration plan: Add stream contract tests and standard client wrapper for xadd/xreadgroup/xack/dead-letter behavior.

## Missing Critical Features

**Authentication/authorization:**
- Problem: No auth exists for gateway message ingestion or dashboard operational mutations.
- Blocks: Safe deployment beyond isolated trusted host/network.

**Schema migrations:**
- Problem: DB writer executes `schema.sql` at startup from working directory; no versioned migration framework is detected.
- Blocks: Safe production schema evolution and rollback.

**Dead-letter queues and replay tooling for malformed streams:**
- Problem: Services log parse failures and either ack, skip, or leave pending depending component.
- Blocks: Reliable recovery from malformed EA messages, adapter lifecycle reports, or DB write failures.

**Operational readiness health checks:**
- Problem: Nautilus dev healthcheck writes a temp file and prints `ok`; dashboard/gateway/signal readiness does not validate Redis/DB/stream subscriptions deeply.
- Blocks: Automated rollout decisions based on real service readiness.

## Test Coverage Gaps

**Gateway security and framing:**
- What's not tested: TCP/ZMQ auth absence, malformed JSON floods, partial/multiple line framing, oversized backfill payloads, symbol allowlist.
- Files: `D:/Aureus/.claude/worktrees/agent-aa1e45131babea93e/services/aureus-gateway/main.py`, `D:/Aureus/.claude/worktrees/agent-aa1e45131babea93e/mql5/AureusSocketLib.mqh`
- Risk: Bad or hostile messages can corrupt streams or exhaust resources unnoticed.
- Priority: High

**DB writer duplicate tick insert and failure semantics:**
- What's not tested: Tick path duplicate insert, ack behavior when first/second insert fails, parse errors with pending messages.
- Files: `D:/Aureus/.claude/worktrees/agent-aa1e45131babea93e/services/aureus-db-writer/main.py`, `D:/Aureus/.claude/worktrees/agent-aa1e45131babea93e/services/aureus-db-writer/tests/test_position_account_ingest.py`
- Risk: Duplicate ticks and stuck pending Redis messages.
- Priority: High

**Signal recovery with real DB/Redis:**
- What's not tested: Full startup hydration, checkpoint, sparse snapshots, gap detection, backfill command, recalculation, and state persistence using actual TimescaleDB/Redis.
- Files: `D:/Aureus/.claude/worktrees/agent-aa1e45131babea93e/services/aureus-signal/engine/live_engine.py`, `D:/Aureus/.claude/worktrees/agent-aa1e45131babea93e/services/aureus-signal/engine/gap_detector.py`, `D:/Aureus/.claude/worktrees/agent-aa1e45131babea93e/services/aureus-signal/engine/state_snapshot.py`
- Risk: Service restart or broker disconnect can silently lose signal state continuity.
- Priority: High

**Dashboard mutation endpoints:**
- What's not tested: Strategy CRUD authorization, validation, Redis refresh publish, model changes, forced recovery endpoint.
- Files: `D:/Aureus/.claude/worktrees/agent-aa1e45131babea93e/services/aureus-dashboard/api/main.py`
- Risk: UI/API changes can break live strategy refresh or expose unsafe operations.
- Priority: Medium

**Nautilus real integration:**
- What's not tested: Real `TradingNodeConfig`, live node start, multi-symbol stream polling, execution lifecycle in stream adapter mode.
- Files: `D:/Aureus/.claude/worktrees/agent-aa1e45131babea93e/services/aureus-nautilus-node/main.py`, `D:/Aureus/.claude/worktrees/agent-aa1e45131babea93e/services/aureus-nautilus-node/config.py`, `D:/Aureus/.claude/worktrees/agent-aa1e45131babea93e/services/aureus-nautilus-node/execution_client.py`, `D:/Aureus/.claude/worktrees/agent-aa1e45131babea93e/services/aureus-nautilus-bridge/main.py`
- Risk: Simulated tests pass while real trading adapter path does not submit or reconcile orders.
- Priority: High

---

*Concerns audit: 2026-05-27*
