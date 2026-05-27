# Coding Conventions

**Analysis Date:** 2026-05-27

## Naming Patterns

**Files:**
- Python modules use `snake_case.py`: `services/aureus-signal/engine/feature_flags.py`, `services/aureus-signal/engine/snapshot_utils.py`, `services/aureus-signal/engine/logic/orchestrator.py`.
- Python test files use `test_*.py`: `services/aureus-signal/tests/test_atr_o1.py`, `services/aureus-signal/unittest/test_orders_events.py`, `services/aureus-signal/unittest/test_feature_flags.py`.
- Next.js route files use App Router names: `services/aureus-dashboard/web/src/app/page.tsx`, `services/aureus-dashboard/web/src/app/backtest/page.tsx`, `services/aureus-dashboard/web/src/app/ai-insights/page.tsx`.
- React component files use PascalCase: `services/aureus-dashboard/web/src/components/AIInsights.tsx`, `services/aureus-dashboard/web/src/components/BacktestChart.tsx`, `services/aureus-dashboard/web/src/components/Sidebar.tsx`.
- React context files use PascalCase plus `Context`: `services/aureus-dashboard/web/src/context/SymbolsContext.tsx`.
- Frontend tests use co-located `__tests__` plus `.contract.test.tsx`: `services/aureus-dashboard/web/src/app/performance/__tests__/page.contract.test.tsx`.

**Functions:**
- Python functions and methods use `snake_case`: `get_point_size`, `get_symbol_digits`, `calculate_lot_size`, `process_triggers` in `services/aureus-signal/engine/orders.py`.
- Python private helpers use leading underscore: `_get_default_risk_budget`, `_get_symbol_config`, `_build_trigger_dedupe_key` in `services/aureus-signal/engine/orders.py`.
- React component functions use PascalCase: `DashboardPage` in `services/aureus-dashboard/web/src/app/page.tsx`, `ModelSelector` and `InstitutionalAudit` in `services/aureus-dashboard/web/src/components/AIInsights.tsx`.
- React hooks and local handlers use camelCase: `useSymbols` in `services/aureus-dashboard/web/src/context/SymbolsContext.tsx`, `handleForceRecovery` in `services/aureus-dashboard/web/src/app/page.tsx`, `handleSelect` in `services/aureus-dashboard/web/src/components/AIInsights.tsx`.
- Test helpers use concise snake_case in Python: `_build_tr_series` in `services/aureus-signal/tests/test_atr_o1.py`, `complete_order_plan` in `services/aureus-signal/unittest/test_orders_events.py`.

**Variables:**
- Python local variables use `snake_case`: `trigger_age`, `strategy_name`, `order_plan_snapshot` in `services/aureus-signal/engine/orders.py`.
- Python constants use uppercase: `DEFAULT_CACHE_TTL` in `services/aureus-signal/engine/feature_flags.py`, `PIPELINE_LOG_PREFIX` in `services/aureus-signal/engine/orders.py`, `_ATOMIC_PUBLISH_SCRIPT` in `services/aureus-gateway/main.py`.
- Python Redis keys use `aureus:` namespace and semantic segments: `aureus:config:{key}` in `services/aureus-signal/engine/feature_flags.py`, `aureus:orders:history:{symbol}` in `services/aureus-signal/engine/orders.py`.
- TypeScript state setters use React convention: `selectedSymbol`/`setSelectedSymbol`, `chartData`/`setChartData`, `showSettings`/`setShowSettings` in `services/aureus-dashboard/web/src/app/page.tsx`.
- TypeScript env-derived constants use uppercase local names: `API_BASE` in `services/aureus-dashboard/web/src/app/page.tsx` and `services/aureus-dashboard/web/src/context/SymbolsContext.tsx`.

**Types:**
- Python classes use PascalCase: `FeatureFlags` in `services/aureus-signal/engine/feature_flags.py`, `SimulatedTradeManager` in `services/aureus-signal/engine/orders.py`, `HybridOrchestrator` in `services/aureus-signal/engine/logic/orchestrator.py`.
- Python dataclasses use PascalCase with result suffix where useful: `JudgeResult` in `services/aureus-signal/engine/logic/judges/base.py`.
- Pydantic models use PascalCase plus domain suffix: `TickMessage`, `CandleMessage`, `OrderOpenedEvent`, `TradeHistoryEvent` in `services/aureus-gateway/main.py`.
- TypeScript interfaces use PascalCase: `Candle`, `SwingPoint`, `OrderBlock`, `AiAudit`, `SymbolsContextType` in `services/aureus-dashboard/web/src/app/page.tsx` and `services/aureus-dashboard/web/src/context/SymbolsContext.tsx`.
- TypeScript union literals use uppercase domain strings when matching backend contracts: `side: "BUY" | "SELL"` in `services/aureus-dashboard/web/src/app/page.tsx`, `type: Literal['TICK', 'CANDLE']` in `services/aureus-gateway/main.py`.

## Code Style

**Formatting:**
- Frontend uses TypeScript/React formatting with two-space indentation in `services/aureus-dashboard/web/src/app/page.tsx` and `services/aureus-dashboard/web/src/app/performance/__tests__/page.contract.test.tsx`.
- Some frontend component files use four-space indentation; when editing existing component files, preserve local style in `services/aureus-dashboard/web/src/components/AIInsights.tsx` and `services/aureus-dashboard/web/src/components/BacktestChart.tsx`.
- Python uses four-space indentation and PEP 8 naming. Preserve compact guard clauses and early returns in `services/aureus-signal/engine/orders.py`.
- No Prettier config detected in inspected paths. Use existing formatting rather than introducing global reformatting.

**Linting:**
- Frontend lint command is `npm run lint` in `services/aureus-dashboard/web/package.json`.
- Frontend ESLint config uses Next.js core web vitals and TypeScript presets in `services/aureus-dashboard/web/eslint.config.mjs`.
- ESLint ignores `.next/**`, `out/**`, `build/**`, and `next-env.d.ts` in `services/aureus-dashboard/web/eslint.config.mjs`.
- Python lint config not detected in current inspected signal/gateway paths. Match existing Python style manually.

## Import Organization

**Order:**
1. Standard library imports first: `asyncio`, `json`, `logging`, `os`, `time`, `collections` in `services/aureus-gateway/main.py`, `services/aureus-signal/engine/orders.py`, `services/aureus-signal/engine/feature_flags.py`.
2. Third-party imports next: `pandas`, `numpy`, `redis.asyncio`, `pydantic`, `zmq` in `services/aureus-signal/tests/test_atr_o1.py` and `services/aureus-gateway/main.py`.
3. Local imports last: `from engine.logging_common import get_logger` in `services/aureus-signal/engine/orders.py`, `from .gates.base import BaseGate` in `services/aureus-signal/engine/logic/orchestrator.py`.
4. React imports first, third-party UI/libs next, app aliases after: `react`, `lucide-react`, then `@/context/SymbolsContext` and `@/components/Sidebar` in `services/aureus-dashboard/web/src/app/page.tsx`.

**Path Aliases:**
- Frontend uses `@/` alias for `src`: `@/context/SymbolsContext`, `@/components/Sidebar`, `@/components/SMCChart` in `services/aureus-dashboard/web/src/app/page.tsx`.
- Python service tests often mutate `sys.path` to import service modules: `sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))` in `services/aureus-signal/tests/test_atr_o1.py` and `sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))` in `services/aureus-signal/unittest/test_feature_flags.py`.
- Python package-relative imports are used inside logic packages: `from .gates.base import BaseGate` and `from .judges.base import BaseJudge` in `services/aureus-signal/engine/logic/orchestrator.py`.

## Error Handling

**Patterns:**
- Use early returns for invalid runtime state: `if (!selectedSymbol) return;` in `services/aureus-dashboard/web/src/app/page.tsx`, `if not origin_t: ... continue` in `services/aureus-signal/engine/orders.py`.
- Wrap network and persistence calls with `try`/`catch` or `try`/`except`, log errors, and keep app/service alive: `fetchData` in `services/aureus-dashboard/web/src/app/page.tsx`, `FeatureFlags.get` in `services/aureus-signal/engine/feature_flags.py`.
- Raise user-facing errors for frontend context misuse: `throw new Error('useSymbols must be used within a SymbolsProvider')` in `services/aureus-dashboard/web/src/context/SymbolsContext.tsx`.
- Return safe defaults on infrastructure failure where feature flags or optional config are non-critical: `FeatureFlags.get` returns default in `services/aureus-signal/engine/feature_flags.py`, symbol config helpers fallback in `services/aureus-signal/engine/orders.py`.
- Use Pydantic models for inbound contract validation in gateway: `BaseMessage`, `TickMessage`, `CandleMessage`, `OrderOpenedEvent` in `services/aureus-gateway/main.py`.
- Preserve domain decisions as structured dictionaries rather than exceptions in signal orchestration: `HybridOrchestrator.audit` returns `decision`, `aci`, `reason`, and `breakdown` in `services/aureus-signal/engine/logic/orchestrator.py`.

## Logging

**Framework:**
- Python signal modules use project logger helper: `get_logger(__name__)` in `services/aureus-signal/engine/feature_flags.py`, `services/aureus-signal/engine/orders.py`, `services/aureus-signal/engine/logic/orchestrator.py`.
- Gateway configures standard Python logging with env-driven `LOG_LEVEL` and optional `LOG_FILE` in `services/aureus-gateway/main.py`.
- Frontend uses `console.error` for fetch and parsing failures in `services/aureus-dashboard/web/src/app/page.tsx`, `services/aureus-dashboard/web/src/components/AIInsights.tsx`, and `services/aureus-dashboard/web/src/context/SymbolsContext.tsx`.

**Patterns:**
- Use structured bracket prefixes for pipeline diagnostics in signal code: `PIPELINE_LOG_PREFIX = "[PIPELINE]"` and messages like `[D][process_triggers][candidate]` in `services/aureus-signal/engine/orders.py`.
- Include symbol, strategy, trace_id, and reason_code in trade pipeline logs in `services/aureus-signal/engine/orders.py`.
- Use `logger.warning` for recoverable but important fallback behavior: Redis feature flag read failure in `services/aureus-signal/engine/feature_flags.py`, missing symbol config in `services/aureus-signal/engine/orders.py`.
- Use `logger.info` for audit decisions and consensus/veto events in `services/aureus-signal/engine/logic/orchestrator.py`.
- Use frontend `console.error` only around user-visible fetch/update failures, not normal empty states, in `services/aureus-dashboard/web/src/app/page.tsx` and `services/aureus-dashboard/web/src/context/SymbolsContext.tsx`.

## Comments

**When to Comment:**
- Comment domain formulas and contract rationale: lot sizing formula in `services/aureus-signal/engine/orders.py`, feature flag Redis keys in `services/aureus-signal/engine/feature_flags.py`.
- Comment phase/story acceptance criteria in tests where behavior maps to requirements: `services/aureus-signal/unittest/test_feature_flags.py`, `services/aureus-signal/unittest/test_orders_events.py`.
- Comment UI chart steps for multi-stage rendering logic: numbered chart setup in `services/aureus-dashboard/web/src/components/BacktestChart.tsx` and data fetch stages in `services/aureus-dashboard/web/src/app/page.tsx`.
- Avoid comments that restate single-line code; keep comments for business rules, protocol contracts, and non-obvious fallbacks.

**JSDoc/TSDoc:**
- Python docstrings are common on public classes and methods: `FeatureFlags`, `BaseSignal`, `BaseJudge`, `calculate_lot_size` in `services/aureus-signal/engine/feature_flags.py`, `services/aureus-signal/engine/signals/base.py`, `services/aureus-signal/engine/logic/judges/base.py`, `services/aureus-signal/engine/orders.py`.
- TypeScript components mostly rely on interfaces and inline types rather than TSDoc: `services/aureus-dashboard/web/src/components/AIInsights.tsx`, `services/aureus-dashboard/web/src/components/BacktestChart.tsx`.

## Function Design

**Size:**
- Prefer small helpers for reusable calculations: `_get_symbol_config`, `get_point_size`, `get_contract_size`, `calculate_lot_size` in `services/aureus-signal/engine/orders.py`.
- Large orchestration methods exist for domain flows; when changing them, keep edits surgical and add tests around behavior: `process_triggers` in `services/aureus-signal/engine/orders.py`, `fetchData` flow in `services/aureus-dashboard/web/src/app/page.tsx`.
- Use early exits to reduce nesting: `HybridOrchestrator.audit` gate rejection in `services/aureus-signal/engine/logic/orchestrator.py`, `dedupeAndSort` in `services/aureus-dashboard/web/src/components/BacktestChart.tsx`.

**Parameters:**
- Python service methods accept domain objects and optional context explicitly: `BaseSignal.calculate(self, df, state_obj, **kwargs)` in `services/aureus-signal/engine/signals/base.py`, `SimulatedTradeManager.process_triggers(..., ai_validator=None, execution_mode="simulated", recent_candles=None)` in `services/aureus-signal/engine/orders.py`.
- TypeScript component props use interfaces for larger prop sets: `BacktestChartProps` in `services/aureus-dashboard/web/src/components/BacktestChart.tsx`, `AIInsightsProps` in `services/aureus-dashboard/web/src/components/AIInsights.tsx`.
- Keep environment configuration read near module or component scope: `API_BASE` in `services/aureus-dashboard/web/src/context/SymbolsContext.tsx`, `log_level`/`log_file` in `services/aureus-gateway/main.py`.

**Return Values:**
- Signal calculators return `dict` metadata or `None` for inactive/insufficient data: `BaseSignal.calculate` in `services/aureus-signal/engine/signals/base.py`, `ATRSignal.calculate` tested by `services/aureus-signal/tests/test_atr_o1.py`.
- Orchestration returns structured decision dictionaries with stable keys: `HybridOrchestrator.audit` in `services/aureus-signal/engine/logic/orchestrator.py`.
- Async gateway processors return booleans to indicate processed/skipped messages: `process_message` in `services/aureus-gateway/main.py`.
- React components return `null` for intentionally hidden UI: `InstitutionalAudit` returns null when audit data missing in `services/aureus-dashboard/web/src/components/AIInsights.tsx`.

## Module Design

**Exports:**
- Python modules export classes/functions directly; no central barrel pattern detected in sampled signal modules: `services/aureus-signal/engine/feature_flags.py`, `services/aureus-signal/engine/orders.py`, `services/aureus-signal/engine/logic/judges/base.py`.
- React components use named exports for multiple components in one file: `ModelSelector`, `AIConfidenceMeter`, `InstitutionalAudit` in `services/aureus-dashboard/web/src/components/AIInsights.tsx`.
- React components use default export when file maps to one main component or route: `DashboardPage` in `services/aureus-dashboard/web/src/app/page.tsx`, `BacktestChart` in `services/aureus-dashboard/web/src/components/BacktestChart.tsx`.
- Context modules export provider and hook together: `SymbolsProvider` and `useSymbols` in `services/aureus-dashboard/web/src/context/SymbolsContext.tsx`.

**Barrel Files:**
- Python package `__init__.py` files exist for packages but no broad barrel export pattern detected in sampled logic paths: `services/aureus-signal/engine/logic/__init__.py`, `services/aureus-signal/engine/logic/gates/__init__.py`, `services/aureus-signal/engine/logic/judges/__init__.py`.
- Frontend imports components directly by file path using `@/components/...`; no `index.ts` barrel pattern detected in sampled dashboard paths.

---

*Convention analysis: 2026-05-27*
