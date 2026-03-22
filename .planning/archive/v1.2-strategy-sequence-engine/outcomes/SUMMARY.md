# Milestone Summary

## Goal
Migrate Aureus strategy logic to a unified, production-ready sequence evaluation engine. Deprecate legacy hardcoded strategy classes and unify all evaluation under config-driven `TemplateStrategy`.

## Completed
- **O(1) State Machine Engine** — Rebuilt `_evaluate_sequence` from O(N) history scan to O(1) state-based evaluation per candle
- **Complex Sequence Constraints** — `max_wait` (candle timeout), `reset_signals` (counter-signal resets), optional step jumps
- **3-Pillar Strategy Framework** — Strategies answer What (`context_filters`), When (`sequence`), How (`trade_execution`) through JSON
- **Context Filter Evaluator** — 4 filter types: `trend_alignment`, `session_active`, `ob_imbalance`, `ema_alignment`
- **Trade Execution Config** — Dynamic size, sl, tp, trailing, early_exits, capital_risk_pct in order plans
- **Legacy Strategy Deprecation** — Deleted `TrendContinuationStrategy` and `OrderFlowDominanceStrategy`
- **Registry Unification** — `StrategyRegistry` only loads `TemplateStrategy` instances
- **Modern Seed Configs** — DB seeds contain full `context_filters`, `sequence`, `trade_execution` blocks

## Deferred
- **Backtesting & Measurement Engine** — Simulate historical data, mock order execution, output performance reports (Win Rate, PnL, Drawdown). Slated for v1.3.

## Impact
- Tất cả chiến lược trading giờ đều chạy qua `TemplateStrategy` — config-driven, testable, không có hardcoded logic
- Thêm chiến lược mới chỉ cần thêm JSON config vào DB, không cần viết code Python
- Risk management (SL, TP, trailing, early exits) được tích hợp trực tiếp vào order plan
