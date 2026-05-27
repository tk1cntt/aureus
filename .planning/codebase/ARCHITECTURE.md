# Architecture

**Analysis Date:** 2026-05-27

## Pattern Overview

**Overall:** Service-oriented, event-driven trading platform with Redis Streams/PubSub backbone, TimescaleDB persistence, FastAPI API layer, and Next.js dashboard.

**Key Characteristics:**
- Use Redis as transport/state bus. Core streams and keys use `aureus:*` namespaces in `D:/Aureus/services/aureus-gateway/main.py`, `D:/Aureus/services/aureus-signal/engine/live_engine.py`, `D:/Aureus/services/aureus-db-writer/main.py`, and `D:/Aureus/services/aureus-nautilus-bridge/main.py`.
- Keep services small by runtime responsibility. Container wiring lives in `D:/Aureus/docker-compose.dev.yml`; service entrypoints are `main.py` files under `D:/Aureus/services/*/`.
- Store durable market, signal, trade, AI, and performance data in TimescaleDB/PostgreSQL from `D:/Aureus/services/aureus-db-writer/main.py`, `D:/Aureus/services/aureus-signal/engine/live_engine.py`, `D:/Aureus/services/aureus-trader/journal.py`, and `D:/Aureus/services/aureus-dashboard/api/main.py`.
- Use async Python workers for live processing. Main loops use `asyncio`, `redis.asyncio`, and `asyncpg` in `D:/Aureus/services/aureus-gateway/main.py`, `D:/Aureus/services/aureus-signal/engine/live_engine.py`, `D:/Aureus/services/aureus-trader/main.py`, and `D:/Aureus/services/aureus-nautilus-bridge/main.py`.
- Use dashboard API as read-model stitcher. `D:/Aureus/services/aureus-dashboard/api/main.py` merges Redis live state with TimescaleDB history for chart, strategy, AI, and performance endpoints.

## Layers

**External producer / MT5 layer:**
- Purpose: Send ticks, candles, backfill, order lifecycle, position, and trade history events into Aureus; receive trade commands from Aureus.
- Location: `D:/Aureus/mql5/`, especially `D:/Aureus/mql5/AureusProvider_v2.mq5`, `D:/Aureus/mql5/AureusSocketLib.mqh`, and `D:/Aureus/mql5/OpenAlgo/`.
- Contains: MQL5 EAs, socket/OpenAlgo helpers, build notes, and local historical sample files.
- Depends on: Gateway TCP/ZMQ endpoints in `D:/Aureus/services/aureus-gateway/main.py`.
- Used by: `D:/Aureus/services/aureus-gateway/main.py` via TCP port `5556` and ZMQ port `5555` configured in `D:/Aureus/docker-compose.dev.yml`.

**Gateway ingestion layer:**
- Purpose: Validate inbound market/order events, publish canonical Redis streams/keys, and forward commands back to connected EA clients.
- Location: `D:/Aureus/services/aureus-gateway/`.
- Contains: Pydantic message models, ZMQ listener, TCP listener, command subscriber, Redis atomic publish script.
- Depends on: Redis from `D:/Aureus/docker-compose.dev.yml`; Pydantic schemas in `D:/Aureus/services/aureus-gateway/main.py`.
- Used by: Signal engine (`aureus:stream:{symbol}:candle`), DB writer (`aureus:stream:*:*`), trader (`aureus:mt5:events`), and MT5 command path (`aureus:mt5:commands`).

**Signal and strategy layer:**
- Purpose: Consume candle streams, maintain per-symbol state, compute technical signals, evaluate strategies, publish signal events, write snapshots, and generate AI pulse context.
- Location: `D:/Aureus/services/aureus-signal/`.
- Contains: Live runtime in `D:/Aureus/services/aureus-signal/engine/live_engine.py`; signal calculators in `D:/Aureus/services/aureus-signal/engine/signals/`; strategy registry/templates in `D:/Aureus/services/aureus-signal/engine/strategies/`; logic gates/judges in `D:/Aureus/services/aureus-signal/engine/logic/`.
- Depends on: Redis Streams, TimescaleDB, symbol config `D:/Aureus/services/aureus-signal/symbols.json`, strategy tables, optional LLM/TradingAgents endpoint.
- Used by: Dashboard API, notifier, trader, DB writer, and strategy executor container configured from `D:/Aureus/docker-compose.dev.yml`.

**Trade execution layer:**
- Purpose: Convert strategy matches into MT5 commands, dedupe orders, serialize lanes, handle ACK/NACK/result events, and write trade journal data.
- Location: `D:/Aureus/services/aureus-trader/`.
- Contains: Runtime in `D:/Aureus/services/aureus-trader/main.py`, dispatcher in `D:/Aureus/services/aureus-trader/dispatcher.py`, validation in `D:/Aureus/services/aureus-trader/validator.py`, order command builder in `D:/Aureus/services/aureus-trader/order_builder.py`, idempotency in `D:/Aureus/services/aureus-trader/idempotency.py`, journal in `D:/Aureus/services/aureus-trader/journal.py`.
- Depends on: Redis PubSub channels `aureus:signals:{symbol}`, `aureus:mt5:commands`, `aureus:mt5:events`; PostgreSQL for journal storage.
- Used by: MT5 gateway command subscriber and dashboard/performance persistence.

**Nautilus execution adapter layer:**
- Purpose: Provide alternate/simulated Nautilus execution path and normalize order lifecycle into execution streams.
- Location: `D:/Aureus/services/aureus-nautilus-node/` and `D:/Aureus/services/aureus-nautilus-bridge/`.
- Contains: Node lifecycle in `D:/Aureus/services/aureus-nautilus-node/main.py`; config/runners/clients in `D:/Aureus/services/aureus-nautilus-node/config.py`, `D:/Aureus/services/aureus-nautilus-node/execution_client.py`, and `D:/Aureus/services/aureus-nautilus-node/sync_worker.py`; bridge in `D:/Aureus/services/aureus-nautilus-bridge/main.py`, `D:/Aureus/services/aureus-nautilus-bridge/mapper.py`, and `D:/Aureus/services/aureus-nautilus-bridge/reconciliation.py`.
- Depends on: Redis order/lifecycle streams and `nautilus_trader` runtime image declared in `D:/Aureus/docker-compose.dev.yml`.
- Used by: DB writer via `aureus:stream:{symbol}:execution` and metrics exporter via order/execution streams.

**Persistence and reconciliation layer:**
- Purpose: Persist Redis stream events to TimescaleDB, keep database schema ready, recover pending order messages, and reconcile recent trades against MT5 history.
- Location: `D:/Aureus/services/aureus-db-writer/`.
- Contains: Batch writer/reconciliation runtime in `D:/Aureus/services/aureus-db-writer/main.py`, trade status validation in `D:/Aureus/services/aureus-db-writer/state_machine.py`, schema in `D:/Aureus/services/aureus-db-writer/schema.sql`, migrations in `D:/Aureus/services/aureus-db-writer/migrations/`.
- Depends on: Redis Streams and TimescaleDB from `D:/Aureus/docker-compose.dev.yml`.
- Used by: Dashboard API, performance endpoints, AI history, audit/reconciliation workflows.

**API layer:**
- Purpose: Expose live state, charts, strategies, AI status/history, and performance analytics to dashboard clients.
- Location: `D:/Aureus/services/aureus-dashboard/api/`.
- Contains: FastAPI app and endpoints in `D:/Aureus/services/aureus-dashboard/api/main.py`; API tests in `D:/Aureus/services/aureus-dashboard/api/tests/`.
- Depends on: Redis sync/async clients, asyncpg pool, LLM health endpoint, symbol config from `D:/Aureus/services/aureus-signal/symbols.json`.
- Used by: Next.js frontend in `D:/Aureus/services/aureus-dashboard/web/`.

**Presentation layer:**
- Purpose: Render live chart, SMC overlays, AI insights, strategies, backtest, and performance UI.
- Location: `D:/Aureus/services/aureus-dashboard/web/`.
- Contains: Next.js App Router pages in `D:/Aureus/services/aureus-dashboard/web/src/app/`; reusable components in `D:/Aureus/services/aureus-dashboard/web/src/components/`; context in `D:/Aureus/services/aureus-dashboard/web/src/context/SymbolsContext.tsx`; performance page components in `D:/Aureus/services/aureus-dashboard/web/src/app/performance/components/`.
- Depends on: Dashboard API base URL from `NEXT_PUBLIC_API_URL`, React state/effects, localStorage for chart settings and selected symbol.
- Used by: Human operators and tests under `D:/Aureus/services/aureus-dashboard/web/src/app/performance/__tests__/`.

**Notification layer:**
- Purpose: Consume signal channels, apply Redis-backed filters/routes, and dispatch Telegram notifications/risk events.
- Location: `D:/Aureus/services/aureus-notifier/`.
- Contains: Runtime in `D:/Aureus/services/aureus-notifier/main.py`, filter/routes config in `D:/Aureus/services/aureus-notifier/config.py`, Telegram transport in `D:/Aureus/services/aureus-notifier/telegram_bot.py`, rate-limited queue in `D:/Aureus/services/aureus-notifier/rate_limiter.py`, order reporting in `D:/Aureus/services/aureus-notifier/order_reporter.py`.
- Depends on: Redis PubSub channels `aureus:signals:{symbol}`, Telegram bot env vars.
- Used by: Operations alerting.

**Observability layer:**
- Purpose: Export Redis/bridge metrics and provide Prometheus/Grafana dashboards.
- Location: `D:/Aureus/monitoring/` and `D:/Aureus/services/aureus-bridge-metrics-exporter/`.
- Contains: Prometheus config in `D:/Aureus/monitoring/prometheus/prometheus.yml`, alert rules in `D:/Aureus/monitoring/prometheus/alerts.yml` and `D:/Aureus/monitoring/prometheus/rules/nautilus-alerts.yml`, Grafana provisioning/dashboards under `D:/Aureus/monitoring/grafana/`, exporter logic in `D:/Aureus/services/aureus-bridge-metrics-exporter/main.py`.
- Depends on: Redis streams and Prometheus/Grafana containers in `D:/Aureus/docker-compose.dev.yml`.
- Used by: Operators for backlog, latency, duplicate trace IDs, PnL, Redis metrics.

## Data Flow

**Live market data to dashboard:**

1. MT5/EAs in `D:/Aureus/mql5/` send newline-delimited JSON via TCP or ZMQ to `D:/Aureus/services/aureus-gateway/main.py`.
2. Gateway validates `TICK`, `CANDLE`, or `BACKFILL` payloads and writes `aureus:latest:{symbol}:{type}` plus `aureus:stream:{symbol}:{type}` using Redis atomic script in `D:/Aureus/services/aureus-gateway/main.py`.
3. `D:/Aureus/services/aureus-signal/engine/live_engine.py` consumes `aureus:stream:{symbol}:candle`, writes/upserts `aureus_candles`, updates per-symbol `WindowManager` state, runs `execute_signals_for_candle`, emits `aureus:stream:{symbol}:signals`, writes `aureus:state:{symbol}`, checkpoints, and DB snapshots.
4. `D:/Aureus/services/aureus-db-writer/main.py` also consumes Redis streams for candles, swing points, execution, positions, account snapshots, and orders, then persists canonical database rows.
5. `D:/Aureus/services/aureus-dashboard/api/main.py` reads candles/swing points from TimescaleDB and stitches latest Redis state (`aureus:state:{symbol}`) for `/api/v1/chart/{symbol}` and `/api/v1/state/{symbol}`.
6. `D:/Aureus/services/aureus-dashboard/web/src/app/page.tsx` polls dashboard API every 2 seconds and renders chart/UI with `D:/Aureus/services/aureus-dashboard/web/src/components/SMCChart.tsx`, `D:/Aureus/services/aureus-dashboard/web/src/components/ConfluenceOverlay.tsx`, and `D:/Aureus/services/aureus-dashboard/web/src/components/MarketPulse.tsx`.

**Signal to order execution:**

1. Strategy matching originates from signal/strategy runtime under `D:/Aureus/services/aureus-signal/engine/live_engine.py` and `D:/Aureus/services/aureus-signal/engine/strategies/registry.py`.
2. Trader listens to symbol channels `aureus:signals:{symbol}` in `D:/Aureus/services/aureus-trader/main.py` and only processes `STRATEGY_MATCH` events.
3. Trader validates events in `D:/Aureus/services/aureus-trader/validator.py`, builds MT5 command payloads in `D:/Aureus/services/aureus-trader/order_builder.py`, applies idempotency in `D:/Aureus/services/aureus-trader/idempotency.py`, and enqueues dispatch through `D:/Aureus/services/aureus-trader/dispatcher.py`.
4. Dispatcher publishes commands to `aureus:mt5:commands`; gateway subscriber in `D:/Aureus/services/aureus-gateway/main.py` forwards them to active TCP EA writers by symbol.
5. Gateway validates EA lifecycle responses (`ACK`, `NACK`, `ORDER_OPENED`, `ORDER_FILLED`, `ORDER_CLOSED`, `ORDER_FAILED`) and publishes them to `aureus:mt5:events`.
6. Dispatcher resolves pending futures from `aureus:mt5:events`, handles retry/reconcile paths, and calls journal handlers in `D:/Aureus/services/aureus-trader/journal.py`.
7. DB writer persists order/execution/account/position records from streams in `D:/Aureus/services/aureus-db-writer/main.py`.

**Nautilus bridge path:**

1. Orders appear on `aureus:stream:{symbol}:orders`.
2. `D:/Aureus/services/aureus-nautilus-bridge/main.py` discovers order streams, maps payloads through `D:/Aureus/services/aureus-nautilus-bridge/mapper.py`, and normalizes lifecycle reports with `D:/Aureus/services/aureus-nautilus-bridge/reconciliation.py`.
3. Bridge publishes normalized execution events to `aureus:stream:{symbol}:execution`.
4. `D:/Aureus/services/aureus-db-writer/main.py` persists those events into `aureus_execution_events`.
5. `D:/Aureus/services/aureus-bridge-metrics-exporter/main.py` tracks order/execution stream deltas and exposes Prometheus metrics.

**AI and strategy management:**

1. Dashboard API strategy endpoints in `D:/Aureus/services/aureus-dashboard/api/main.py` create/update/delete strategy templates in TimescaleDB.
2. API publishes refresh notifications to `aureus:cmd:refresh_strategies`; `D:/Aureus/services/aureus-signal/engine/live_engine.py` reloads `StrategyRegistry` for affected symbols.
3. AI model updates are written to `aureus:config:llm_model` and streamed via `aureus:sys:config`; signal engine global command listener updates `AIValidator` model.
4. AI pulse analysis is queued in `D:/Aureus/services/aureus-signal/engine/live_engine.py`, generated through validator/brain providers, stored to Redis `aureus:ai:latest:{symbol}`, and persisted to `aureus_ai_analysis`.
5. Dashboard API exposes latest/history endpoints from Redis/TimescaleDB in `D:/Aureus/services/aureus-dashboard/api/main.py`.

**State Management:**
- Redis holds volatile live state: `aureus:state:{symbol}`, `aureus:latest:{symbol}:candle`, `aureus:checkpoint:{symbol}`, `aureus:ai:latest:{symbol}`, `aureus:config:llm_model`, and PubSub channels.
- Redis Streams provide replayable event queues: `aureus:stream:{symbol}:candle`, `aureus:stream:{symbol}:signals`, `aureus:stream:{symbol}:orders`, `aureus:stream:{symbol}:execution`, `aureus:sys:config`.
- TimescaleDB/PostgreSQL stores durable rows: candles, swing points, signal snapshots, strategies, trades, execution events, account/position snapshots, AI analysis, reconciliation logs, and performance data.
- Signal runtime owns in-memory per-symbol state through `WindowManager` and `SymbolState` from `D:/Aureus/services/aureus-signal/engine/manager.py` and `D:/Aureus/services/aureus-signal/engine/state.py`.
- Frontend state is component-local React state plus localStorage settings in `D:/Aureus/services/aureus-dashboard/web/src/app/page.tsx`.

## Key Abstractions

**Gateway message models:**
- Purpose: Validate and normalize inbound/outbound MT5 market/order contracts.
- Examples: `D:/Aureus/services/aureus-gateway/main.py` classes `TickMessage`, `CandleMessage`, `BackfillMessage`, `OrderOpenedEvent`, `OrderClosedEvent`, `OrderFilledEvent`, `PositionReportEvent`, `TradeHistoryEvent`.
- Pattern: Pydantic models with `Literal` event types, then routing in `process_message`.

**WindowManager and SymbolState:**
- Purpose: Maintain per-symbol candle windows, derived state, transient signals, swing points, order blocks, tracking vars, and snapshots.
- Examples: `D:/Aureus/services/aureus-signal/engine/manager.py`, `D:/Aureus/services/aureus-signal/engine/state.py`, `D:/Aureus/services/aureus-signal/engine/state_snapshot.py`.
- Pattern: In-memory state hydrated from DB snapshots/checkpoints, updated per candle, serialized to Redis and TimescaleDB.

**Signal calculators:**
- Purpose: Compute technical and market-context signals from DataFrame + state.
- Examples: `D:/Aureus/services/aureus-signal/engine/signal_factory.py`, `D:/Aureus/services/aureus-signal/engine/signals/pivots.py`, `D:/Aureus/services/aureus-signal/engine/signals/structure.py`, `D:/Aureus/services/aureus-signal/engine/signals/tpo.py`, `D:/Aureus/services/aureus-signal/engine/signals/cisd.py`.
- Pattern: Factory builds ordered dict of signal instances. Order matters in `create_signal_set`, especially `structure_processor` before CHOCH outlets.

**StrategyRegistry and TemplateStrategy:**
- Purpose: Load active strategy templates from DB, enforce compatibility, run phased `on_bar_close → validate_entry → build_order_plan`, and return accepted decisions.
- Examples: `D:/Aureus/services/aureus-signal/engine/strategies/registry.py`, `D:/Aureus/services/aureus-signal/engine/strategies/template.py`, `D:/Aureus/services/aureus-signal/engine/strategies/base.py`.
- Pattern: Registry-per-symbol with rejection recording and decision matrix logging.

**HybridOrchestrator / gates / judges:**
- Purpose: Coordinate fail-fast gates and weighted scoring judges for trade setup audits.
- Examples: `D:/Aureus/services/aureus-signal/engine/logic/orchestrator.py`, `D:/Aureus/services/aureus-signal/engine/logic/gates/`, `D:/Aureus/services/aureus-signal/engine/logic/judges/`.
- Pattern: Boolean gates reject immediately; judges score and may veto/override.

**AIValidator / providers:**
- Purpose: Build AI contexts, call LLM/TradingAgents providers, and persist/serve AI decisions.
- Examples: `D:/Aureus/services/aureus-signal/engine/ai_validator.py`, `D:/Aureus/services/aureus-signal/engine/providers/tradingagents.py`, `D:/Aureus/services/aureus-signal/engine/live_engine.py`.
- Pattern: Background priority queue with Redis latest state and DB history writes.

**OrderDispatcher:**
- Purpose: Serialize order dispatch by lane, manage in-flight commands, wait for ACK/results, retry selectively, and publish rejection/reconcile alerts.
- Examples: `D:/Aureus/services/aureus-trader/dispatcher.py`, `D:/Aureus/services/aureus-trader/main.py`.
- Pattern: Redis list queue plus per-lane in-memory deques and futures keyed by `cmd_id`.

**TradeJournalManager:**
- Purpose: Persist strategy/order lifecycle and signal snapshots for audit and evaluation.
- Examples: `D:/Aureus/services/aureus-trader/journal.py`, `D:/Aureus/services/aureus-trader/reasoning_embedding_worker.py`, `D:/Aureus/services/aureus-trader/reasoning_embeddings.py`.
- Pattern: Async DB writes from dispatcher event callbacks; Redis queue/worker for embeddings.

**BridgeProcessor / NautilusAdapter:**
- Purpose: Map orders to intents and normalize adapter/lifecycle reports into execution events.
- Examples: `D:/Aureus/services/aureus-nautilus-bridge/main.py`, `D:/Aureus/services/aureus-nautilus-bridge/mapper.py`, `D:/Aureus/services/aureus-nautilus-bridge/reconciliation.py`.
- Pattern: Processor owns status-by-trace state; adapter can be simulated or stream-driven.

**RuntimeHealth:**
- Purpose: Track Nautilus node lifecycle phase, health, and last error.
- Examples: `D:/Aureus/services/aureus-nautilus-node/main.py`.
- Pattern: Dataclass returned by `run_live_node`, with signal-handler-driven shutdown.

**FastAPI Pydantic models and helpers:**
- Purpose: Shape request/response contracts and normalize filters/errors.
- Examples: `D:/Aureus/services/aureus-dashboard/api/main.py` classes `StrategyCreate`, `BacktestRequest`, `TradeResponse`, plus helpers `_normalize_performance_filters`, `_error_envelope`, `_performance_cache_key`.
- Pattern: Endpoint-local Pydantic models and procedural SQL helpers.

**Frontend components/context:**
- Purpose: Render dashboard views and share symbol metadata.
- Examples: `D:/Aureus/services/aureus-dashboard/web/src/app/page.tsx`, `D:/Aureus/services/aureus-dashboard/web/src/context/SymbolsContext.tsx`, `D:/Aureus/services/aureus-dashboard/web/src/components/SMCChart.tsx`, `D:/Aureus/services/aureus-dashboard/web/src/app/performance/components/EquityChart.tsx`.
- Pattern: Next.js App Router pages with client components and fetch polling.

## Entry Points

**Development stack:**
- Location: `D:/Aureus/docker-compose.dev.yml`
- Triggers: `docker compose -f docker-compose.dev.yml up` or service-specific commands from `D:/Aureus/RUN_SERVICES.md`.
- Responsibilities: Start Redis, TimescaleDB, gateway, db writer, signal engine, strategy executor, Nautilus services, metrics, dashboard API, notifier, trader, Prometheus, and Grafana.

**Gateway service:**
- Location: `D:/Aureus/services/aureus-gateway/main.py`
- Triggers: Container `aureus-gateway-dev` or direct `python main.py`.
- Responsibilities: Run ZMQ listener, TCP listener, command subscriber; publish market/order events to Redis.

**Signal engine service:**
- Location: `D:/Aureus/services/aureus-signal/main.py`
- Triggers: Container `aureus-signal-dev` or direct `python main.py`.
- Responsibilities: Call `run_signal_engine`, consume candle streams, compute signals, maintain state, seed/reload strategies, produce signal/AI/snapshot outputs.

**Strategy executor service:**
- Location: `D:/Aureus/services/aureus-signal/main_executor.py`
- Triggers: Container `aureus-strategy-executor-dev` command `python main_executor.py`.
- Responsibilities: Run strategy execution sidecar from signal service codebase.

**DB writer service:**
- Location: `D:/Aureus/services/aureus-db-writer/main.py`
- Triggers: Container `aureus-db-writer-dev` or direct `python main.py`.
- Responsibilities: Create/verify schema, discover Redis streams, batch persist events, recover XPENDING, reconcile recent trades.

**Trader service:**
- Location: `D:/Aureus/services/aureus-trader/main.py`
- Triggers: Container `aureus-trader-dev` or direct `python main.py`.
- Responsibilities: Subscribe to strategy signal channels, validate/dedupe/build commands, run dispatcher and event listener.

**Nautilus node service:**
- Location: `D:/Aureus/services/aureus-nautilus-node/main.py`
- Triggers: Container `aureus-nautilus-node-dev` or direct `python main.py`.
- Responsibilities: Load Nautilus node config, create live node, track lifecycle, handle graceful shutdown.

**Nautilus bridge service:**
- Location: `D:/Aureus/services/aureus-nautilus-bridge/main.py`
- Triggers: Container `aureus-nautilus-bridge-dev` or direct `python main.py`.
- Responsibilities: Discover order/lifecycle streams, normalize execution reports, publish execution stream events.

**Dashboard API:**
- Location: `D:/Aureus/services/aureus-dashboard/api/main.py`
- Triggers: Container `aureus-dashboard-api-dev` or Uvicorn block at file bottom.
- Responsibilities: Serve `/api/v1/*` endpoints for symbols, charts, state, strategies, AI, performance.

**Dashboard web:**
- Location: `D:/Aureus/services/aureus-dashboard/web/src/app/page.tsx` and `D:/Aureus/services/aureus-dashboard/web/package.json`
- Triggers: Next.js dev/build scripts.
- Responsibilities: Render operator UI and poll Dashboard API.

**Notifier service:**
- Location: `D:/Aureus/services/aureus-notifier/main.py`
- Triggers: Container `aureus-notifier-dev` or direct `python main.py`.
- Responsibilities: Subscribe to signal channels, filter events, send Telegram notifications.

**Bridge metrics exporter:**
- Location: `D:/Aureus/services/aureus-bridge-metrics-exporter/main.py`
- Triggers: Container `aureus-bridge-metrics-dev` or direct `python main.py`.
- Responsibilities: Poll Redis order/execution/position streams and expose Prometheus metrics.

## Error Handling

**Strategy:** Log-and-continue for stream workers, explicit reject/ack for invalid messages, retry or reconciliation for ambiguous execution, and fail-fast validation at boundaries.

**Patterns:**
- Pydantic validation rejects malformed gateway messages in `D:/Aureus/services/aureus-gateway/main.py` without publishing invalid events.
- Redis stream consumers ACK processed or rejected messages to prevent stuck queues in `D:/Aureus/services/aureus-db-writer/main.py` and `D:/Aureus/services/aureus-nautilus-bridge/main.py`.
- Signal background work uses supervised wrappers and safe insert wrappers in `D:/Aureus/services/aureus-signal/engine/live_engine.py`.
- Signal runtime recreates missing Redis consumer groups on `NOGROUP` in `D:/Aureus/services/aureus-signal/engine/live_engine.py`.
- Trader dispatcher classifies retryable/non-retryable NACK/ORDER_FAILED reasons in `D:/Aureus/services/aureus-trader/dispatcher.py`.
- Trader publishes `ORDER_REJECTED` and `RECONCILE_NEEDED` alerts instead of silently dropping ambiguous outcomes in `D:/Aureus/services/aureus-trader/dispatcher.py`.
- Dashboard API wraps HTTP and generic exceptions into an error envelope in `D:/Aureus/services/aureus-dashboard/api/main.py`.
- DB writer uses trade state-machine validation from `D:/Aureus/services/aureus-db-writer/state_machine.py` before updating `aureus_trades`.

## Cross-Cutting Concerns

**Logging:** Use Python `logging` across services. Gateway, DB writer, dashboard API, signal engine, trader, notifier, and metrics exporter configure log level from `LOG_LEVEL`; several services optionally write `LOG_FILE` mounted to `D:/Aureus/logs/` via `D:/Aureus/docker-compose.dev.yml`.

**Validation:** Use Pydantic at gateway/API boundaries (`D:/Aureus/services/aureus-gateway/main.py`, `D:/Aureus/services/aureus-dashboard/api/main.py`), explicit event validation in trader (`D:/Aureus/services/aureus-trader/validator.py`), state transition validation in DB writer (`D:/Aureus/services/aureus-db-writer/state_machine.py`), and strategy compatibility validation in registry (`D:/Aureus/services/aureus-signal/engine/strategies/registry.py`).

**Authentication:** No application user auth detected in dashboard API or web. Internal auth relies on network/container boundary and secret env vars for DB/Telegram/LLM. Telegram bot tokens are read by `D:/Aureus/services/aureus-notifier/main.py`. Database credentials are supplied via env in `D:/Aureus/docker-compose.dev.yml`.

**Configuration:** Use env vars from compose plus service-local config modules/files: `D:/Aureus/services/aureus-signal/symbols.json`, `D:/Aureus/services/aureus-trader/config.py`, `D:/Aureus/services/aureus-nautilus-node/config.py`, `D:/Aureus/services/aureus-dashboard/web/next.config.ts`.

**Observability:** Use Prometheus exporter service `D:/Aureus/services/aureus-bridge-metrics-exporter/main.py`, redis-exporter image, Prometheus files under `D:/Aureus/monitoring/prometheus/`, Grafana provisioning under `D:/Aureus/monitoring/grafana/`, and pipeline/debug logs throughout signal/trader services.

---

*Architecture analysis: 2026-05-27*
