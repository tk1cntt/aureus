# Testing Patterns

**Analysis Date:** 2026-05-27

## Test Framework

**Runner:**
- Python signal service uses `unittest` style and pytest-compatible function tests. Tests live in `services/aureus-signal/tests/` and `services/aureus-signal/unittest/`.
- Python gateway declares `pytest>=7.0` and `pytest-asyncio>=0.21` in `services/aureus-gateway/requirements.txt`.
- Gateway pytest async mode is configured with `asyncio_mode = auto` in `services/aureus-gateway/tests/pytest.ini`.
- Frontend uses Vitest `^2.1.9` with React Testing Library `^16.3.0` and jsdom `^26.1.0` in `services/aureus-dashboard/web/package.json`.
- Frontend has a targeted test command for performance contract tests in `services/aureus-dashboard/web/package.json`.

**Assertion Library:**
- Python `unittest.TestCase` assertions: `assertIsNotNone`, `assertAlmostEqual`, `assertEqual` in `services/aureus-signal/tests/test_atr_o1.py`.
- Python plain `assert` statements in pytest-compatible tests: `services/aureus-signal/unittest/test_feature_flags.py`, `services/aureus-signal/unittest/test_orders_events.py`.
- Frontend uses Vitest `expect` and React Testing Library `screen`/`waitFor` in `services/aureus-dashboard/web/src/app/performance/__tests__/page.contract.test.tsx`.

**Run Commands:**
```bash
python -m unittest discover -s services/aureus-signal/tests -p "test_*.py"       # Run signal unittest-style tests
python -m pytest services/aureus-signal/unittest                                # Run signal pytest-compatible tests
python -m pytest services/aureus-gateway/tests                                  # Run gateway tests with pytest-asyncio config
cd services/aureus-dashboard/web && npm run test:performance-contract           # Run frontend performance contract test
cd services/aureus-dashboard/web && npm run lint                                # Run frontend ESLint
```

## Test File Organization

**Location:**
- Signal indicator and regression tests live in `services/aureus-signal/tests/`: `services/aureus-signal/tests/test_atr_o1.py`, `services/aureus-signal/tests/test_ema_o1.py`, `services/aureus-signal/tests/test_zigzag_regression.py`.
- Signal story/unit tests live in `services/aureus-signal/unittest/`: `services/aureus-signal/unittest/test_feature_flags.py`, `services/aureus-signal/unittest/test_orders_events.py`, `services/aureus-signal/unittest/test_event_filter.py`.
- Gateway pytest config lives in `services/aureus-gateway/tests/pytest.ini`; no gateway test files detected in current sampled tree.
- Frontend route contract tests are co-located under route-specific `__tests__`: `services/aureus-dashboard/web/src/app/performance/__tests__/page.contract.test.tsx`.

**Naming:**
- Python tests use `test_*.py` files and `test_*` functions/methods: `test_o1_vs_pandas`, `test_reads_from_redis`, `test_order_opened_event` in `services/aureus-signal/tests/test_atr_o1.py`, `services/aureus-signal/unittest/test_feature_flags.py`, and `services/aureus-signal/unittest/test_orders_events.py`.
- Python unittest classes use `Test*` names: `TestATROptimization` in `services/aureus-signal/tests/test_atr_o1.py`.
- Frontend contract tests use `.contract.test.tsx`: `services/aureus-dashboard/web/src/app/performance/__tests__/page.contract.test.tsx`.
- Frontend suites use domain/route names in `describe`: `describe("/performance contract", ...)` in `services/aureus-dashboard/web/src/app/performance/__tests__/page.contract.test.tsx`.

**Structure:**
```text
services/aureus-signal/
├── tests/                 # Indicator, regression, verification scripts/tests
│   └── test_atr_o1.py
└── unittest/              # Story/unit tests with fakes and contract checks
    ├── test_feature_flags.py
    └── test_orders_events.py

services/aureus-gateway/
└── tests/
    └── pytest.ini         # pytest-asyncio config

services/aureus-dashboard/web/src/app/performance/
└── __tests__/
    └── page.contract.test.tsx
```

## Test Structure

**Suite Organization:**
```python
class TestATROptimization(unittest.TestCase):
    def setUp(self):
        np.random.seed(42)
        self.df = pd.DataFrame(data)
        self.period = 14
        self.signal = ATRSignal(self.period)

    def test_o1_vs_pandas(self):
        state = MockState()
        res = self.signal.calculate(warmup_df, state)
        self.assertIsNotNone(res)
```
- Use this class-based pattern for stateful numeric signal tests in `services/aureus-signal/tests/test_atr_o1.py`.

```python
def test_reads_from_redis():
    r = FakeRedis({"aureus:config:snapshot_mode": "SPARSE"})
    flags = FeatureFlags(r, ttl=60)
    result = run(flags.get("snapshot_mode", "FULL"))
    assert result == "SPARSE"
```
- Use this function-based pattern for focused service-unit tests with fakes in `services/aureus-signal/unittest/test_feature_flags.py`.

```typescript
describe("/performance contract", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    cleanup();
    localStorage.clear();
  });

  it("uses same filter params for metrics/trades/equity and renders success data", async () => {
    global.fetch = fetchMock as unknown as typeof fetch;
    render(<PerformancePage />);
    await screen.findByText("Performance Dashboard");
  });
});
```
- Use this Vitest + Testing Library pattern for frontend route contract tests in `services/aureus-dashboard/web/src/app/performance/__tests__/page.contract.test.tsx`.

**Patterns:**
- Setup pattern: use `setUp` for `unittest.TestCase` numeric tests in `services/aureus-signal/tests/test_atr_o1.py`; use `beforeEach`/`afterEach` for Vitest tests in `services/aureus-dashboard/web/src/app/performance/__tests__/page.contract.test.tsx`.
- Teardown pattern: restore global browser APIs after frontend tests via `global.fetch = originalFetch` in `services/aureus-dashboard/web/src/app/performance/__tests__/page.contract.test.tsx`; close manually-created event loops in `run(coro)` helpers in `services/aureus-signal/unittest/test_feature_flags.py`.
- Assertion pattern: assert output contracts and state mutation, not only return values. Examples: `res['tag']`, `res['value']`, and `res['t']` in `services/aureus-signal/tests/test_atr_o1.py`; `state.simulated_orders` and Redis stream payload fields in `services/aureus-signal/unittest/test_orders_events.py`.
- Contract pattern: verify structured error rendering and query parameter consistency in frontend tests in `services/aureus-dashboard/web/src/app/performance/__tests__/page.contract.test.tsx`.

## Mocking

**Framework:**
- Python tests use hand-written fake classes rather than `unittest.mock` in sampled signal tests: `FakeRedis`, `BrokenRedis`, `MockState` in `services/aureus-signal/unittest/test_feature_flags.py` and `services/aureus-signal/unittest/test_orders_events.py`.
- Frontend tests use Vitest `vi.mock` and `vi.fn` in `services/aureus-dashboard/web/src/app/performance/__tests__/page.contract.test.tsx`.

**Patterns:**
```python
class FakeRedis:
    """Minimal async Redis mock for testing."""
    def __init__(self, data=None):
        self._data = data or {}

    async def get(self, key):
        return self._data.get(key)
```
- Use minimal async fake methods matching only the Redis methods under test in `services/aureus-signal/unittest/test_feature_flags.py`.

```python
class MockState:
    def __init__(self):
        self.last_candle = {'c': '2000.00', 't': '1709300000', 'o': '1999', 'h': '2001', 'l': '1998', 'v': '100'}
        self.simulated_orders = []
        self.transient_signals = {}
        self.symbol = "XAUUSD"
        self.swing_points = []
        self.atr = 5.0
```
- Use tiny domain state fakes with only accessed attributes for trade/order tests in `services/aureus-signal/unittest/test_orders_events.py`.

```typescript
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  useSearchParams: () => ({ get: (_key: string) => null }),
}));

vi.mock("@/components/Sidebar", () => ({
  Sidebar: () => <div data-testid="sidebar" />,
}));
```
- Use `vi.mock` for Next.js navigation, context hooks, and heavy child components in `services/aureus-dashboard/web/src/app/performance/__tests__/page.contract.test.tsx`.

**What to Mock:**
- Mock Redis for unit tests that verify caching, default behavior, stream writes, set membership, and event lists: `services/aureus-signal/unittest/test_feature_flags.py`, `services/aureus-signal/unittest/test_orders_events.py`.
- Mock state objects for signal/trade code when full `SymbolState` construction is unnecessary: `services/aureus-signal/tests/test_atr_o1.py`, `services/aureus-signal/unittest/test_orders_events.py`.
- Mock browser/global APIs such as `fetch`, `localStorage` state, and Next navigation in frontend contract tests: `services/aureus-dashboard/web/src/app/performance/__tests__/page.contract.test.tsx`.
- Mock expensive visual components when route contract is about API behavior and text rendering: `EquityChart`, `PerformanceTable`, `MetricCard` in `services/aureus-dashboard/web/src/app/performance/__tests__/page.contract.test.tsx`.

**What NOT to Mock:**
- Do not mock pure calculation internals when checking numerical parity. `services/aureus-signal/tests/test_atr_o1.py` compares `ATRSignal.calculate` against pandas EWM truth.
- Do not mock the function under test. Use `FeatureFlags` directly in `services/aureus-signal/unittest/test_feature_flags.py` and `SimulatedTradeManager` directly in `services/aureus-signal/unittest/test_orders_events.py`.
- Do not mock URL construction in frontend route contract tests; inspect actual fetch URLs and search params in `services/aureus-dashboard/web/src/app/performance/__tests__/page.contract.test.tsx`.

## Fixtures and Factories

**Test Data:**
```python
def complete_order_plan(entry_method='CURRENT'):
    return {
        'entry_type': 'MARKET',
        'entry_method': entry_method,
        'entry_value': 0,
        'entry_policy': 'IMMEDIATE',
        'size_mode': 'FIXED_UNITS',
        'size': 0.01,
        'sl': {'mode': 'FIXED_PIPS', 'value': 500},
        'tp': {'mode': 'RR', 'value': 2.0},
    }
```
- Use small factory functions for repeated order trigger payloads in `services/aureus-signal/unittest/test_orders_events.py`.

```python
np.random.seed(42)
data = {
    't': np.arange(100),
    'h': np.random.uniform(2050, 2100, 100),
    'l': np.random.uniform(2000, 2049, 100),
    'c': np.random.uniform(2000, 2100, 100),
}
self.df = pd.DataFrame(data)
```
- Seed random generators for deterministic numeric tests in `services/aureus-signal/tests/test_atr_o1.py`.

```typescript
const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
  const url = String(input);
  if (url.includes("/performance/metrics")) {
    return { ok: true, status: 200, json: async () => ({ metrics: {...}, meta: {...} }) } as Response;
  }
  return { ok: true, status: 200, json: async () => ({ data: [...], meta: {...} }) } as Response;
});
```
- Use URL-driven fetch mock branches for route-level API contract tests in `services/aureus-dashboard/web/src/app/performance/__tests__/page.contract.test.tsx`.

**Location:**
- No shared fixture directory detected. Keep fixtures local to test files unless reused across many tests.
- Python fakes live in the same test file as tests: `services/aureus-signal/unittest/test_feature_flags.py`, `services/aureus-signal/unittest/test_orders_events.py`.
- Frontend mocks live at top of the test file before `describe`: `services/aureus-dashboard/web/src/app/performance/__tests__/page.contract.test.tsx`.

## Coverage

**Requirements:**
- No repository-wide coverage threshold detected in inspected config.
- Frontend has one explicit targeted contract command, not a full test suite command, in `services/aureus-dashboard/web/package.json`.
- Gateway declares pytest dependencies and config, but current sampled tree has no gateway test files besides `services/aureus-gateway/tests/pytest.ini`.

**View Coverage:**
```bash
python -m pytest services/aureus-signal --cov=engine              # Possible if pytest-cov installed; not declared in inspected requirements
cd services/aureus-dashboard/web && npx vitest run --coverage     # Possible if coverage provider installed; not declared in inspected package.json
```

## Test Types

**Unit Tests:**
- Signal calculation unit tests validate indicator math, output contract, insufficient data behavior, and deterministic repeatability in `services/aureus-signal/tests/test_atr_o1.py`.
- Feature flag unit tests validate Redis key prefixing, TTL cache, default fallback, Redis failure behavior, invalidation, and `get_all` in `services/aureus-signal/unittest/test_feature_flags.py`.
- Order manager unit tests validate event tracking, bridge payload fields, pullback entry logic, duplicate behavior, and order lifecycle state in `services/aureus-signal/unittest/test_orders_events.py`.

**Integration Tests:**
- Frontend route contract test exercises `PerformancePage` with mocked network responses and real rendering assertions in `services/aureus-dashboard/web/src/app/performance/__tests__/page.contract.test.tsx`.
- Signal tests include Redis-flow scripts under `scripts/`: `scripts/test_nautilus_redis_flow.py`, `scripts/test_nautilus_redis_flow_v2.py`. Treat these as manual/integration scripts unless wired into CI.
- Manual E2E checklist script exists at `scripts/manual_e2e_checklist.py`.

**E2E Tests:**
- No browser E2E framework detected in inspected frontend package: `services/aureus-dashboard/web/package.json`.
- Database/Redis E2E appears script-based, not framework-based, via `scripts/test_nautilus_redis_flow.py` and `scripts/manual_e2e_checklist.py`.

## Common Patterns

**Async Testing:**
```python
def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()
```
- Use this helper pattern for async service APIs in synchronous pytest-style tests in `services/aureus-signal/unittest/test_feature_flags.py` and `services/aureus-signal/unittest/test_orders_events.py`.

```typescript
render(<PerformancePage />);
await screen.findByText("Performance Dashboard");
await waitFor(() => {
  expect(fetchMock.mock.calls.length).toBeGreaterThanOrEqual(3);
});
```
- Use React Testing Library async queries and `waitFor` for UI fetch/render flows in `services/aureus-dashboard/web/src/app/performance/__tests__/page.contract.test.tsx`.

**Error Testing:**
```python
class BrokenRedis:
    async def get(self, key):
        raise ConnectionError("Redis connection refused")

def test_no_crash_on_redis_error():
    r = BrokenRedis()
    flags = FeatureFlags(r, ttl=60)
    result = run(flags.get("snapshot_mode", "FULL"))
    assert result == "FULL"
```
- Use fake failing dependencies to verify safe fallback paths in `services/aureus-signal/unittest/test_feature_flags.py`.

```typescript
if (url.includes("/performance/metrics")) {
  return {
    ok: false,
    status: 400,
    json: async () => ({
      error: "start must be less than or equal to end",
      code: "INVALID_DATE_RANGE",
      details: { start: "2026-04-07T00:00", end: "2026-04-01T00:00" },
    }),
  } as Response;
}

expect(await screen.findByText("Invalid filter: start must be less than or equal to end")).toBeTruthy();
```
- Use structured API error mocks and assert explicit error UI in `services/aureus-dashboard/web/src/app/performance/__tests__/page.contract.test.tsx`.

---

*Testing analysis: 2026-05-27*
