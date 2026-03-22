# Phase 15: Strategy Migration & Unification - Context

**Gathered:** 2026-03-22
**Status:** Ready for planning

<domain>
## Phase Boundary
Migrate legacy hardcoded strategies (`TrendContinuationStrategy`, `OrderFlowDominanceStrategy`) to `TemplateStrategy` JSON sequences, and unify `StrategyRegistry` execution entirely under `TemplateStrategy`. Ensure dynamic strategy concepts (sessions, trend, order flow) are accommodated cleanly via a standard configuration format. Expand the configuration model to encapsulate complete Trade Execution logic (Risk Sizing, SL, TP, Early Exits).
</domain>

<decisions>
## Implementation Decisions

### Dynamic Calculations (Order Flow)
- **D-01:** Extract OB-counting ratio logic from `OrderFlowDominanceStrategy`. Inject it directly into the state update phase (e.g., `live_engine.py` or a pure `state.py` function) to populate `state_obj.of_dominance = 'BULLISH'/'BEARISH'/'NEUTRAL'` on each candle close.

### Context Filters
- **D-02:** Introduce a `"context_filters"` dictionary inside strategy templates. Example:
  `{"htf_trend": "BULLISH", "of_dominance": "BULLISH", "allowed_sessions": ["LONDON", "NEW_YORK"]}`
- **D-03:** `TemplateStrategy` must evaluate these context filters first on `on_bar_close()`. If the prevailing state violates the context filter, the sequence engine evaluates poorly or zeroes the score, ensuring sequence safety.

### Registry & DB Migration
- **D-04:** Purge all custom classes (`TrendContinuationStrategy`, `OrderFlowDominanceStrategy`) and hardcoded fallback Maps (`strategy_map`) out of `registry.py`. All strategies default back to runtime instantiations of `TemplateStrategy()`.
- **D-05:** Write an explicit SQL DB seeder script to directly update `config` blobs of existing `aureus_strategy_templates` rows in PostgreSQL, converting them into the modern format representing the sequences of those legacy strategies.

### Trade Execution (The HOW)
- **D-06:** Add `"trade_execution"` JSON block to all configurations to enforce standardized risk and exit management natively within `TemplateStrategy.build_order_plan()`.
- **D-07:** Enable dynamic Stop Loss via `"sl_anchor"`. The engine must resolve anchors (e.g., `recent_swing_low`, `ob_bottom`) against `state_obj` market structure data instead of using static pips.
- **D-08:** Implement `tp_targets` config. Allow Risk/Reward ratio-based targeting calculated automatically from the dynamic SL distance.
- **D-09:** Configurable Position Sizing via `"capital_risk_pct"`, ensuring maximum Risk per trade is centrally defined in the JSON strategy.
- **D-10:** Add `"early_exits"` array supporting Sequence Tag invalidation (e.g., `["choch_bear"]`). If an early exit tag triggers while a position is open, the engine actively Force Closes the trade rather than passively waiting for SL.

### the agent's Discretion
- The robust internal format for checking dictionary fields in `TemplateStrategy` against `state_obj` arbitrary properties (the agent designs the Context Filter runtime implementation).

### Folded Todos
N/A

### Deferred Ideas
- **Backtesting & Measurement Engine:** A capability to simulate historical data, mock order execution (using H/L checking for SL/TP parsing), and output performance reports (Win Rate, PnL, Drawdown). Slated for a future phase (e.g. Phase 16) to avoid scope creep here.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Strategy Implementation
- `services/aureus-signal/engine/strategies/template.py` — Location for contextual JSON filters integration.
- `services/aureus-signal/engine/strategies/registry.py` — Target for removing class fallback overrides.
- `services/aureus-signal/engine/live_engine.py` — Target for embedding newly extracted State Domain logic (Order Flow).

### Reference Legacy Source
- `services/aureus-signal/engine/strategies/order_flow_dominance.py`
- `services/aureus-signal/engine/strategies/trend_continuation.py`

</canonical_refs>
