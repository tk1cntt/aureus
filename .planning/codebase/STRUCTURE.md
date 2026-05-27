# Codebase Structure

**Analysis Date:** 2026-05-27

## Directory Layout

```text
D:/Aureus/
├── .agent/                         # Local agent workflows and automation assets
├── .claude/                        # Claude/GitNexus project instructions and skills
├── .github/                        # GitHub workflows and CI config
├── .gitnexus/                      # GitNexus index metadata/cache
├── .planning/                      # Planning artifacts, codebase maps, phases, quick docs
│   └── codebase/                   # Generated reference docs for stack, architecture, quality, concerns
├── data/                           # Local data assets and runtime data dumps
├── docs/                           # Project docs, reports, and runbooks
├── logs/                           # Runtime log mount target for compose services
├── monitoring/                     # Prometheus/Grafana config, dashboards, alert rules
├── mql5/                           # MT5/MQL5 EAs, socket helpers, OpenAlgo integration, samples
├── scripts/                        # Root operational/dev scripts
├── services/                       # Primary application services
│   ├── aureus-gateway/             # MT5/ZMQ/TCP gateway and Redis publisher
│   ├── aureus-signal/              # Signal engine, strategy engine, AI pulse, tests, fixtures
│   ├── aureus-db-writer/           # Redis-stream to TimescaleDB writer and reconciliation
│   ├── aureus-trader/              # Strategy-match to MT5 command dispatcher and journal
│   ├── aureus-nautilus-node/       # Nautilus live node wrapper and runtime clients
│   ├── aureus-nautilus-bridge/     # Order stream to execution event bridge
│   ├── aureus-bridge-metrics-exporter/ # Prometheus metrics exporter for bridge/order streams
│   ├── aureus-dashboard/           # FastAPI API plus Next.js web dashboard
│   ├── aureus-notifier/            # Telegram notification service
│   ├── aureus-trading-agents/      # TradingAgents integration/runtime
│   ├── brain/                      # AI/brain service assets
│   └── nautilus_trader/            # Nautilus-related local package/assets
├── stable/                         # Untracked stable snapshot/work area currently present
├── tpo_project-master/             # TPO project source/vendor assets
├── docker-compose.dev.yml          # Development stack orchestration
├── docker-compose.prod.yml         # Production stack orchestration
├── RUN_SERVICES.md                 # Local run/debug instructions
├── CLAUDE.md                       # Project instructions
├── AGENTS.md                       # Agent instructions
└── QWEN.md                         # Qwen instructions
```

## Directory Purposes

**`D:/Aureus/services/`:**
- Purpose: Primary runtime implementation area. Put service code here by bounded context.
- Contains: Python microservices, dashboard API/web, Dockerfiles, service-local requirements, migrations, tests.
- Key files: `D:/Aureus/services/aureus-gateway/main.py`, `D:/Aureus/services/aureus-signal/main.py`, `D:/Aureus/services/aureus-db-writer/main.py`, `D:/Aureus/services/aureus-trader/main.py`, `D:/Aureus/services/aureus-dashboard/api/main.py`.

**`D:/Aureus/services/aureus-gateway/`:**
- Purpose: Boundary between MT5/ZMQ/TCP clients and internal Redis streams/channels.
- Contains: `main.py`, `Dockerfile`, `requirements.txt`, tests under `D:/Aureus/services/aureus-gateway/tests/`.
- Key files: `D:/Aureus/services/aureus-gateway/main.py`, `D:/Aureus/services/aureus-gateway/tests/test_order_events.py`, `D:/Aureus/services/aureus-gateway/tests/test_tcp_invalid_json_classification.py`.

**`D:/Aureus/services/aureus-signal/`:**
- Purpose: Core signal/strategy/AI engine for live and replay processing.
- Contains: Entry points, signal engine package, common helpers, migrations, scripts, tests, fixtures, symbol config.
- Key files: `D:/Aureus/services/aureus-signal/main.py`, `D:/Aureus/services/aureus-signal/main_executor.py`, `D:/Aureus/services/aureus-signal/signal_computer.py`, `D:/Aureus/services/aureus-signal/symbols.json`, `D:/Aureus/services/aureus-signal/engine/live_engine.py`, `D:/Aureus/services/aureus-signal/engine/signal_factory.py`.

**`D:/Aureus/services/aureus-signal/engine/`:**
- Purpose: Signal runtime internals. Add signal processing, state, strategy, scoring, provider, and orchestration code here.
- Contains: Live engine, backtest engine, state/window managers, signal calculators, strategy registry/templates, logic gates/judges, providers, scoring, utilities.
- Key files: `D:/Aureus/services/aureus-signal/engine/live_engine.py`, `D:/Aureus/services/aureus-signal/engine/manager.py`, `D:/Aureus/services/aureus-signal/engine/state.py`, `D:/Aureus/services/aureus-signal/engine/state_snapshot.py`, `D:/Aureus/services/aureus-signal/engine/snapshot_utils.py`, `D:/Aureus/services/aureus-signal/engine/ai_validator.py`.

**`D:/Aureus/services/aureus-signal/engine/signals/`:**
- Purpose: Individual technical/context signal calculators.
- Contains: Base signal contract and calculators for pivots, structure, sweeps, CHOCH, FVG, EMA, ATR, CISD, TPO, sessions, trend, volume.
- Key files: `D:/Aureus/services/aureus-signal/engine/signals/base.py`, `D:/Aureus/services/aureus-signal/engine/signals/pivots.py`, `D:/Aureus/services/aureus-signal/engine/signals/structure.py`, `D:/Aureus/services/aureus-signal/engine/signals/tpo.py`, `D:/Aureus/services/aureus-signal/engine/signals/tpo_context.py`, `D:/Aureus/services/aureus-signal/engine/signals/tpo_detectors.py`.

**`D:/Aureus/services/aureus-signal/engine/strategies/`:**
- Purpose: Strategy definitions and registry loading/evaluation.
- Contains: Base strategy, template strategy, registry, seed strategy sync, specialized strategy modules.
- Key files: `D:/Aureus/services/aureus-signal/engine/strategies/base.py`, `D:/Aureus/services/aureus-signal/engine/strategies/registry.py`, `D:/Aureus/services/aureus-signal/engine/strategies/template.py`, `D:/Aureus/services/aureus-signal/engine/strategies/seed_strategies.py`, `D:/Aureus/services/aureus-signal/engine/strategies/smc_trend_scalping.py`.

**`D:/Aureus/services/aureus-signal/engine/logic/`:**
- Purpose: Higher-level confluence audit logic.
- Contains: Orchestrator, gates, judges.
- Key files: `D:/Aureus/services/aureus-signal/engine/logic/orchestrator.py`, `D:/Aureus/services/aureus-signal/engine/logic/gates/base.py`, `D:/Aureus/services/aureus-signal/engine/logic/judges/base.py`.

**`D:/Aureus/services/aureus-signal/tests/`:**
- Purpose: Unit/integration tests and analysis scripts for signal engine behavior.
- Contains: `test_*.py`, fixture CSVs under `D:/Aureus/services/aureus-signal/tests/fixtures/`, debug/capture scripts.
- Key files: `D:/Aureus/services/aureus-signal/tests/test_atr_integration_execute_signals_for_candle.py`, `D:/Aureus/services/aureus-signal/tests/test_tpo_daily_cache.py`, `D:/Aureus/services/aureus-signal/tests/fixtures/candles_XAUUSD.csv`.

**`D:/Aureus/services/aureus-db-writer/`:**
- Purpose: Durable persistence and reconciliation worker.
- Contains: Main batch writer, state machine, schema/migrations/queries/scripts/tests.
- Key files: `D:/Aureus/services/aureus-db-writer/main.py`, `D:/Aureus/services/aureus-db-writer/state_machine.py`, `D:/Aureus/services/aureus-db-writer/schema.sql`, `D:/Aureus/services/aureus-db-writer/migrations/add_trade_journal.sql`, `D:/Aureus/services/aureus-db-writer/migrations/add_trade_signal_snapshots_tpo_d0_d3.sql`.

**`D:/Aureus/services/aureus-trader/`:**
- Purpose: Live trading command path from strategy signal to MT5 command and trade journal.
- Contains: Runtime, config, validator, order builder, dispatcher, idempotency, journal, embeddings/reasoning, scripts, tests.
- Key files: `D:/Aureus/services/aureus-trader/main.py`, `D:/Aureus/services/aureus-trader/config.py`, `D:/Aureus/services/aureus-trader/dispatcher.py`, `D:/Aureus/services/aureus-trader/order_builder.py`, `D:/Aureus/services/aureus-trader/validator.py`, `D:/Aureus/services/aureus-trader/journal.py`.

**`D:/Aureus/services/aureus-nautilus-node/`:**
- Purpose: Nautilus live node wrapper and integration components.
- Contains: Node lifecycle, settings/config, data/execution clients, rollout gates, sync worker, diagnostics, tests.
- Key files: `D:/Aureus/services/aureus-nautilus-node/main.py`, `D:/Aureus/services/aureus-nautilus-node/config.py`, `D:/Aureus/services/aureus-nautilus-node/execution_client.py`, `D:/Aureus/services/aureus-nautilus-node/sync_worker.py`, `D:/Aureus/services/aureus-nautilus-node/nautilus_runner.py`.

**`D:/Aureus/services/aureus-nautilus-bridge/`:**
- Purpose: Bridge Redis order streams to normalized execution streams.
- Contains: Bridge runtime, mapper, reconciliation helpers, tests.
- Key files: `D:/Aureus/services/aureus-nautilus-bridge/main.py`, `D:/Aureus/services/aureus-nautilus-bridge/mapper.py`, `D:/Aureus/services/aureus-nautilus-bridge/reconciliation.py`, `D:/Aureus/services/aureus-nautilus-bridge/tests/test_mapper.py`.

**`D:/Aureus/services/aureus-dashboard/api/`:**
- Purpose: FastAPI backend for dashboard, strategy management, AI endpoints, and performance analytics.
- Contains: `main.py`, requirements, Dockerfile, tests.
- Key files: `D:/Aureus/services/aureus-dashboard/api/main.py`, `D:/Aureus/services/aureus-dashboard/api/tests/test_performance_contract.py`, `D:/Aureus/services/aureus-dashboard/api/tests/conftest.py`.

**`D:/Aureus/services/aureus-dashboard/web/`:**
- Purpose: Next.js frontend dashboard.
- Contains: App Router pages, components, context, public assets, TypeScript/Next/Vitest config.
- Key files: `D:/Aureus/services/aureus-dashboard/web/src/app/page.tsx`, `D:/Aureus/services/aureus-dashboard/web/src/app/layout.tsx`, `D:/Aureus/services/aureus-dashboard/web/src/context/SymbolsContext.tsx`, `D:/Aureus/services/aureus-dashboard/web/package.json`, `D:/Aureus/services/aureus-dashboard/web/vitest.config.ts`.

**`D:/Aureus/services/aureus-dashboard/web/src/app/`:**
- Purpose: Route-level UI pages.
- Contains: Main dashboard, AI insights, backtest, performance, strategies pages, global CSS/layout.
- Key files: `D:/Aureus/services/aureus-dashboard/web/src/app/page.tsx`, `D:/Aureus/services/aureus-dashboard/web/src/app/ai-insights/page.tsx`, `D:/Aureus/services/aureus-dashboard/web/src/app/backtest/page.tsx`, `D:/Aureus/services/aureus-dashboard/web/src/app/performance/page.tsx`, `D:/Aureus/services/aureus-dashboard/web/src/app/strategies/page.tsx`.

**`D:/Aureus/services/aureus-dashboard/web/src/components/`:**
- Purpose: Shared React components for dashboard visuals.
- Contains: Charts, sidebar, overlays, AI insights, client-only wrapper.
- Key files: `D:/Aureus/services/aureus-dashboard/web/src/components/SMCChart.tsx`, `D:/Aureus/services/aureus-dashboard/web/src/components/Sidebar.tsx`, `D:/Aureus/services/aureus-dashboard/web/src/components/AIInsights.tsx`, `D:/Aureus/services/aureus-dashboard/web/src/components/MarketPulse.tsx`, `D:/Aureus/services/aureus-dashboard/web/src/components/ConfluenceOverlay.tsx`.

**`D:/Aureus/services/aureus-notifier/`:**
- Purpose: Telegram notification delivery and route/filter management.
- Contains: Runtime, config/filtering, Telegram sender, rate limiter, order reporter, tests if present.
- Key files: `D:/Aureus/services/aureus-notifier/main.py`, `D:/Aureus/services/aureus-notifier/config.py`, `D:/Aureus/services/aureus-notifier/telegram_bot.py`, `D:/Aureus/services/aureus-notifier/rate_limiter.py`, `D:/Aureus/services/aureus-notifier/order_reporter.py`.

**`D:/Aureus/services/aureus-bridge-metrics-exporter/`:**
- Purpose: Prometheus exporter for bridge/order stream metrics.
- Contains: Single-file Python exporter, Dockerfile, requirements.
- Key files: `D:/Aureus/services/aureus-bridge-metrics-exporter/main.py`, `D:/Aureus/services/aureus-bridge-metrics-exporter/requirements.txt`.

**`D:/Aureus/monitoring/`:**
- Purpose: Observability infrastructure config.
- Contains: Prometheus config/rules and Grafana provisioning/dashboards.
- Key files: `D:/Aureus/monitoring/prometheus/prometheus.yml`, `D:/Aureus/monitoring/prometheus/alerts.yml`, `D:/Aureus/monitoring/prometheus/rules/nautilus-alerts.yml`, `D:/Aureus/monitoring/grafana/provisioning/datasources/`, `D:/Aureus/monitoring/grafana/provisioning/dashboards/`, `D:/Aureus/monitoring/grafana/dashboards/`.

**`D:/Aureus/mql5/`:**
- Purpose: MT5 integration assets and EA code.
- Contains: Provider EA, socket library, OpenAlgo headers, build docs, sample XAUUSD data.
- Key files: `D:/Aureus/mql5/AureusProvider_v2.mq5`, `D:/Aureus/mql5/AureusSocketLib.mqh`, `D:/Aureus/mql5/OpenAlgo/OpenAlgoApi.mqh`, `D:/Aureus/mql5/Build_Rules.md`, `D:/Aureus/mql5/XAUUSD/DAT_MT_XAUUSD_M1_202602.csv`.

**`D:/Aureus/.planning/codebase/`:**
- Purpose: Generated codebase reference docs consumed by planning/execution workflows.
- Contains: Architecture, structure, stack, integrations, conventions, testing, concerns markdown files.
- Key files: `D:/Aureus/.planning/codebase/ARCHITECTURE.md`, `D:/Aureus/.planning/codebase/STRUCTURE.md`.

## Key File Locations

**Entry Points:**
- `D:/Aureus/docker-compose.dev.yml`: Development stack wiring, service dependencies, ports, env vars, volumes.
- `D:/Aureus/docker-compose.prod.yml`: Production stack wiring.
- `D:/Aureus/services/aureus-gateway/main.py`: Gateway runtime for ZMQ/TCP/command forwarding.
- `D:/Aureus/services/aureus-signal/main.py`: Signal engine entrypoint.
- `D:/Aureus/services/aureus-signal/main_executor.py`: Strategy executor entrypoint.
- `D:/Aureus/services/aureus-db-writer/main.py`: DB writer/reconciliation entrypoint.
- `D:/Aureus/services/aureus-trader/main.py`: Trader command dispatcher entrypoint.
- `D:/Aureus/services/aureus-nautilus-node/main.py`: Nautilus node lifecycle entrypoint.
- `D:/Aureus/services/aureus-nautilus-bridge/main.py`: Nautilus bridge entrypoint.
- `D:/Aureus/services/aureus-dashboard/api/main.py`: FastAPI API entrypoint.
- `D:/Aureus/services/aureus-dashboard/web/src/app/page.tsx`: Main dashboard page.
- `D:/Aureus/services/aureus-notifier/main.py`: Telegram notifier entrypoint.
- `D:/Aureus/services/aureus-bridge-metrics-exporter/main.py`: Prometheus exporter entrypoint.

**Configuration:**
- `D:/Aureus/services/aureus-signal/symbols.json`: Symbol metadata and signal parameters.
- `D:/Aureus/services/aureus-trader/config.py`: Trader env/config constants and Redis channel names.
- `D:/Aureus/services/aureus-nautilus-node/config.py`: Nautilus node config builder.
- `D:/Aureus/services/aureus-nautilus-node/settings.py`: Nautilus node settings.
- `D:/Aureus/services/aureus-dashboard/web/package.json`: Frontend scripts/dependencies.
- `D:/Aureus/services/aureus-dashboard/web/tsconfig.json`: Frontend TypeScript config and aliases.
- `D:/Aureus/services/aureus-dashboard/web/next.config.ts`: Next.js config.
- `D:/Aureus/services/aureus-dashboard/web/eslint.config.mjs`: Frontend lint config.
- `D:/Aureus/services/aureus-dashboard/web/vitest.config.ts`: Frontend test config.
- `D:/Aureus/RUN_SERVICES.md`: Local service run commands and troubleshooting guidance.
- `D:/Aureus/.env.example`: Example env configuration; do not read or quote real `.env` values.

**Core Logic:**
- `D:/Aureus/services/aureus-gateway/main.py`: Message validation, Redis stream publishing, TCP/ZMQ listeners.
- `D:/Aureus/services/aureus-signal/engine/live_engine.py`: Main signal processing loop, state hydration, strategy reload, AI queue, snapshots.
- `D:/Aureus/services/aureus-signal/engine/signal_factory.py`: Signal registration and normalized snapshot contract.
- `D:/Aureus/services/aureus-signal/engine/strategies/registry.py`: Strategy loading/evaluation orchestration.
- `D:/Aureus/services/aureus-signal/engine/logic/orchestrator.py`: Gate/judge confluence audit.
- `D:/Aureus/services/aureus-db-writer/main.py`: Batch persistence and reconciliation.
- `D:/Aureus/services/aureus-db-writer/state_machine.py`: Valid trade state transitions.
- `D:/Aureus/services/aureus-trader/dispatcher.py`: Order dispatch/retry/result handling.
- `D:/Aureus/services/aureus-trader/journal.py`: Trade journal persistence.
- `D:/Aureus/services/aureus-dashboard/api/main.py`: Dashboard API and performance query logic.

**Testing:**
- `D:/Aureus/services/aureus-signal/tests/`: Signal tests and fixtures.
- `D:/Aureus/services/aureus-trader/tests/`: Trader/order/journal/evaluation tests.
- `D:/Aureus/services/aureus-db-writer/tests/`: DB writer and migration/state-machine tests.
- `D:/Aureus/services/aureus-gateway/tests/`: Gateway order/TCP tests.
- `D:/Aureus/services/aureus-nautilus-bridge/tests/`: Bridge mapper/idempotency/lineage tests.
- `D:/Aureus/services/aureus-nautilus-node/tests/`: Nautilus node tests if tracked.
- `D:/Aureus/services/aureus-dashboard/api/tests/`: FastAPI performance contract tests.
- `D:/Aureus/services/aureus-dashboard/web/src/app/performance/__tests__/page.contract.test.tsx`: Frontend performance page contract test.

**Database:**
- `D:/Aureus/services/aureus-db-writer/schema.sql`: Base schema applied by DB writer.
- `D:/Aureus/services/aureus-db-writer/migrations/`: DB migrations.
- `D:/Aureus/services/aureus-signal/migrations/add_magic_number.sql`: Signal/trading strategy migration.
- `D:/Aureus/check_journal.sql`: Root journal check script.
- `D:/Aureus/fix_ai_analysis.sql`: Root AI analysis fix script.

**Operations and Observability:**
- `D:/Aureus/monitoring/prometheus/prometheus.yml`: Prometheus scrape config.
- `D:/Aureus/monitoring/prometheus/alerts.yml`: Alert definitions.
- `D:/Aureus/monitoring/prometheus/rules/nautilus-alerts.yml`: Nautilus alert rules.
- `D:/Aureus/monitoring/grafana/dashboards/`: Grafana dashboards.
- `D:/Aureus/logs/`: Runtime logs mounted from services.
- `D:/Aureus/restart_signal_services.bat`: Windows restart helper.
- `D:/Aureus/start-telegram-relay.bat`: Telegram relay helper.

## Naming Conventions

**Files:**
- Use `main.py` for Python service entrypoints: `D:/Aureus/services/aureus-gateway/main.py`, `D:/Aureus/services/aureus-signal/main.py`, `D:/Aureus/services/aureus-db-writer/main.py`.
- Use snake_case for Python modules: `D:/Aureus/services/aureus-trader/order_builder.py`, `D:/Aureus/services/aureus-signal/engine/signal_factory.py`, `D:/Aureus/services/aureus-nautilus-bridge/reconciliation.py`.
- Use `test_*.py` for Python tests: `D:/Aureus/services/aureus-trader/tests/test_dispatcher.py`, `D:/Aureus/services/aureus-db-writer/tests/test_state_machine.py`.
- Use PascalCase for React component files: `D:/Aureus/services/aureus-dashboard/web/src/components/SMCChart.tsx`, `D:/Aureus/services/aureus-dashboard/web/src/app/performance/components/MetricCard.tsx`.
- Use lowercase route files `page.tsx` and `layout.tsx` in Next.js App Router: `D:/Aureus/services/aureus-dashboard/web/src/app/performance/page.tsx`, `D:/Aureus/services/aureus-dashboard/web/src/app/layout.tsx`.
- Use `.sql` files for migrations and queries: `D:/Aureus/services/aureus-db-writer/migrations/add_trade_journal.sql`, `D:/Aureus/services/aureus-db-writer/queries/magic_number_filters.sql`.

**Directories:**
- Use service prefix `aureus-*` under `D:/Aureus/services/`: `D:/Aureus/services/aureus-gateway/`, `D:/Aureus/services/aureus-signal/`, `D:/Aureus/services/aureus-trader/`.
- Keep tests service-local under `tests/`: `D:/Aureus/services/aureus-signal/tests/`, `D:/Aureus/services/aureus-trader/tests/`.
- Keep Next.js route pages under `src/app/{route}/page.tsx`: `D:/Aureus/services/aureus-dashboard/web/src/app/strategies/page.tsx`.
- Keep page-specific components under route-local `components/` when scoped to one page: `D:/Aureus/services/aureus-dashboard/web/src/app/performance/components/`.
- Keep shared frontend components under `src/components/`: `D:/Aureus/services/aureus-dashboard/web/src/components/`.

## Where to Add New Code

**New gateway message type:**
- Primary code: Add/modify Pydantic model and routing in `D:/Aureus/services/aureus-gateway/main.py`.
- Tests: Add tests in `D:/Aureus/services/aureus-gateway/tests/`.
- Downstream persistence: Add stream handling in `D:/Aureus/services/aureus-db-writer/main.py` if event needs durable storage.

**New signal calculator:**
- Implementation: Add module in `D:/Aureus/services/aureus-signal/engine/signals/` and register in `D:/Aureus/services/aureus-signal/engine/signal_factory.py`.
- Tests: Add `test_*.py` in `D:/Aureus/services/aureus-signal/tests/`; use fixture CSVs from `D:/Aureus/services/aureus-signal/tests/fixtures/` when candle data needed.
- Config: Add symbol-specific params to `D:/Aureus/services/aureus-signal/symbols.json` only if signal needs per-symbol tuning.

**New strategy/template behavior:**
- Implementation: Prefer template-compatible changes in `D:/Aureus/services/aureus-signal/engine/strategies/template.py` or registry orchestration in `D:/Aureus/services/aureus-signal/engine/strategies/registry.py`.
- Seed data: Add/update seed logic in `D:/Aureus/services/aureus-signal/engine/strategies/seed_strategies.py`.
- Tests: Add tests under `D:/Aureus/services/aureus-signal/tests/`.

**New confluence gate or judge:**
- Gate implementation: `D:/Aureus/services/aureus-signal/engine/logic/gates/`.
- Judge implementation: `D:/Aureus/services/aureus-signal/engine/logic/judges/`.
- Orchestration changes: `D:/Aureus/services/aureus-signal/engine/logic/orchestrator.py`.

**New Redis stream persisted to DB:**
- Primary code: Add discovery pattern and buffer handling to `D:/Aureus/services/aureus-db-writer/main.py`.
- Schema: Add table/columns to `D:/Aureus/services/aureus-db-writer/schema.sql` and migration under `D:/Aureus/services/aureus-db-writer/migrations/`.
- Tests: Add migration/writer test under `D:/Aureus/services/aureus-db-writer/tests/`.

**New trade command or order validation:**
- Validation: `D:/Aureus/services/aureus-trader/validator.py`.
- Command shape: `D:/Aureus/services/aureus-trader/order_builder.py`.
- Dispatch/retry behavior: `D:/Aureus/services/aureus-trader/dispatcher.py`.
- Journal persistence: `D:/Aureus/services/aureus-trader/journal.py`.
- Tests: `D:/Aureus/services/aureus-trader/tests/`.

**New dashboard API endpoint:**
- Implementation: Add route/helper/model in `D:/Aureus/services/aureus-dashboard/api/main.py` unless it grows large enough to justify splitting within `D:/Aureus/services/aureus-dashboard/api/`.
- Tests: Add contract/API tests under `D:/Aureus/services/aureus-dashboard/api/tests/`.
- Frontend consumer: Add/modify route or component under `D:/Aureus/services/aureus-dashboard/web/src/app/` or `D:/Aureus/services/aureus-dashboard/web/src/components/`.

**New dashboard page:**
- Page implementation: `D:/Aureus/services/aureus-dashboard/web/src/app/{route}/page.tsx`.
- Page-specific components: `D:/Aureus/services/aureus-dashboard/web/src/app/{route}/components/`.
- Shared components: `D:/Aureus/services/aureus-dashboard/web/src/components/`.
- Tests: Co-locate in `__tests__/` under route, following `D:/Aureus/services/aureus-dashboard/web/src/app/performance/__tests__/page.contract.test.tsx`.

**New frontend shared state:**
- Implementation: Add context/provider under `D:/Aureus/services/aureus-dashboard/web/src/context/`.
- Usage: Wrap in `D:/Aureus/services/aureus-dashboard/web/src/app/layout.tsx` if global.

**New Nautilus bridge feature:**
- Mapper changes: `D:/Aureus/services/aureus-nautilus-bridge/mapper.py`.
- Reconciliation/status normalization: `D:/Aureus/services/aureus-nautilus-bridge/reconciliation.py`.
- Stream orchestration: `D:/Aureus/services/aureus-nautilus-bridge/main.py`.
- Tests: `D:/Aureus/services/aureus-nautilus-bridge/tests/`.

**New Nautilus node runtime feature:**
- Config/settings: `D:/Aureus/services/aureus-nautilus-node/config.py` or `D:/Aureus/services/aureus-nautilus-node/settings.py`.
- Runtime loop/lifecycle: `D:/Aureus/services/aureus-nautilus-node/main.py`.
- Client/sync behavior: `D:/Aureus/services/aureus-nautilus-node/execution_client.py`, `D:/Aureus/services/aureus-nautilus-node/data_client.py`, or `D:/Aureus/services/aureus-nautilus-node/sync_worker.py`.

**New notification route/type:**
- Filtering/routing config: `D:/Aureus/services/aureus-notifier/config.py`.
- Main subscription/event logic: `D:/Aureus/services/aureus-notifier/main.py`.
- Dispatch behavior: `D:/Aureus/services/aureus-notifier/rate_limiter.py` or `D:/Aureus/services/aureus-notifier/telegram_bot.py`.

**New observability metric:**
- Exporter metric: `D:/Aureus/services/aureus-bridge-metrics-exporter/main.py`.
- Prometheus config/alerts: `D:/Aureus/monitoring/prometheus/prometheus.yml`, `D:/Aureus/monitoring/prometheus/alerts.yml`, or `D:/Aureus/monitoring/prometheus/rules/`.
- Grafana dashboard: `D:/Aureus/monitoring/grafana/dashboards/`.

**Utilities:**
- Service-local one-off scripts: `D:/Aureus/services/{service}/scripts/`.
- Root operational scripts that span services: `D:/Aureus/scripts/`.
- Avoid adding shared cross-service library until two or more services need same code and import path/runtime packaging is clear.

## Special Directories

**`D:/Aureus/logs/`:**
- Purpose: Runtime logs mounted by compose services.
- Generated: Yes.
- Committed: No expected runtime log contents.

**`D:/Aureus/.planning/`:**
- Purpose: Planning, milestones, quick investigations, codebase maps, debug artifacts.
- Generated: Partly.
- Committed: Mixed; treat current task outputs under `D:/Aureus/.planning/codebase/` as expected generated docs.

**`D:/Aureus/.gitnexus/`:**
- Purpose: GitNexus code intelligence index.
- Generated: Yes.
- Committed: Project-specific metadata may exist; do not hand-edit generated index files.

**`D:/Aureus/services/aureus-signal/tests/fixtures/`:**
- Purpose: Deterministic candle fixtures for signal tests.
- Generated: No for checked-in fixture CSVs; some debug outputs may be generated by scripts.
- Committed: Yes for listed fixtures.

**`D:/Aureus/services/aureus-db-writer/migrations/`:**
- Purpose: Database schema evolution.
- Generated: No.
- Committed: Yes. Add new migration files here for DB schema changes.

**`D:/Aureus/services/aureus-trader/scripts/` and `D:/Aureus/services/aureus-signal/scripts/`:**
- Purpose: E2E verification, backfill, replay, migration support, and diagnostics.
- Generated: No for scripts; scripts may produce generated outputs.
- Committed: Yes for scripts.

**`D:/Aureus/services/aureus-dashboard/web/public/`:**
- Purpose: Static frontend assets.
- Generated: No.
- Committed: Yes.

**`D:/Aureus/monitoring/grafana/provisioning/`:**
- Purpose: Grafana auto-provisioned datasources and dashboards.
- Generated: No.
- Committed: Yes.

**`D:/Aureus/stable/`:**
- Purpose: Untracked stable snapshot/work area currently present in working tree.
- Generated: Unknown.
- Committed: No in current git status. Do not rely on it for primary architecture unless explicitly asked.

**`D:/Aureus/services/aureus-signal/scripts/snapshots/`:**
- Purpose: Untracked snapshot output area currently present in working tree.
- Generated: Yes.
- Committed: No in current git status. Do not use for source-of-truth code.

---

*Structure analysis: 2026-05-27*
