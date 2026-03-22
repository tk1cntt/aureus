# Risks & Follow-ups

## Known Limitations
- **Seed strategies only define BULLISH direction** — BEARISH mirror configs not yet seeded. The `context_filters` support `required_trend: "BEARISH"` but no seeds use it yet.
- **`ob_imbalance` filter relies on `state_obj.obs` list** — If OB tracking is inconsistent, this filter may produce inaccurate ratios.
- **`early_exits` declared but not yet consumed** — The `build_order_plan` emits `early_exits` tags but the live engine doesn't yet read them to force-close positions.

## Technical Debt
- **11 pre-existing test failures in `test_sweep_o1.py`** — Tag duplication bug (`sweep_sweep_bull` prefix). Not caused by v1.2 but should be fixed.
- **No registry-level unit tests** — `test_strategy_registry.py` doesn't exist. Registry loading is only tested implicitly via live engine integration.

## TODO / Next Actions for v1.3
- [ ] **Backtesting & Measurement Engine** — Highest priority deferred item. Simulate historical candles, check SL/TP against H/L, output Win Rate, PnL, Drawdown.
- [ ] **Early Exit Engine** — Implement `early_exits` tag consumption in `live_engine.py` to force-close open positions.
- [ ] **BEARISH seed configs** — Mirror all BULLISH seeds with BEARISH equivalents.
- [ ] **Fix sweep_o1 test tag duplication** — Resolve `sweep_sweep_bull` prefix bug.
