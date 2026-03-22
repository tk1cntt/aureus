# Phase 15: Technical Research

## 1. Goal
Unify all strategies into `TemplateStrategy` using JSON config, deprecating legacy hardcoded strategy classes (`OrderFlowDominanceStrategy`, `TrendContinuationStrategy`).

## 2. Current State Analysis
- **`registry.py`**: Currently hardcodes mappings to legacy classes:
  ```python
  strategy_map: Dict[str, Type[BaseStrategy]] = {
      "TREND_CONT": TrendContinuationStrategy,
      "SESSION_SWEEP": TrendContinuationStrategy,
      "ORDER_FLOW_DOM": OrderFlowDominanceStrategy,
  }
  ```
- **`template.py` (`TemplateStrategy`)**: Support Sequence matching via O(1) State Machine flawlessly. However, it **lacks** evaluation logic for the non-event conditions:
  - No `context_filters` logic implemented.
  - No `trade_execution` (risk/sizing) injection into order plans.
- **Legacy Strategies**: 
  - Read `state_obj.htf_trend`, `state_obj.current_session`, `state_obj.obs`
  - Hardcode scoring logic based on `ema_21` slope and OB imbalance.

## 3. required Architecture Updates

### A. TemplateStrategy (`template.py`)
Must be enriched to actively evaluate the 3 pillars required in 15-CONTEXT.md:
1. **Pillar 1: Event Sequence (`sequence`)**: Already implemented.
2. **Pillar 2: Context Filters (`context_filters`)**: 
   - Needs a new `_evaluate_context(state_obj)` method.
   - Must support `trend_alignment` (checks `htf_trend`).
   - Must support `session_active` (checks `current_session`).
   - Must support `ob_imbalance` (computes bull/bear ratio on `state_obj.obs`).
   - Must support `ema_alignment` (checks `state_obj.emas`).
3. **Pillar 3: Trade Execution (`trade_execution`)**:
   - `build_order_plan` (override from `BaseStrategy`) must parse `self.trade_execution` JSON config to dynamically assign `size`, `sl`, `tp`, and `trailing`.

### B. Strategy Registry (`registry.py`)
- Remove the `strategy_map` fallback to legacy classes.
- Make `TemplateStrategy` the universal handler for all dynamically loaded strategy configs.

### C. Seed Strategies (`seed_strategies.py`)
- Update the default seeded JSON configurations in DB to match the new `context_filters` and `trade_execution` schema syntax.

## 4. Deletion targets
The following files are now obsolete and MUST be deleted during execution:
- `engine/strategies/order_flow_dominance.py`
- `engine/strategies/trend_continuation.py`

## 5. Validation Architecture
1. **Validation 1**: `pytest tests/test_strategy_registry.py` - Ensure registry loads purely `TemplateStrategy` instances.
2. **Validation 2**: Unit tests for new context filters (e.g., `test_context_filters.py`) to verify string-based config arrays correctly read underlying `state_obj` indicators.
3. **Validation 3**: DB seeding test to verify JSON shapes.
