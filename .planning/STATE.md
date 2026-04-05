---
gsd_state_version: 1.0
milestone: v1.4
milestone_name: TradingAgents Market Data Integration
status: verifying
last_updated: "2026-04-05T05:09:09.342Z"
last_activity: 2026-04-05
progress:
  total_phases: 8
  completed_phases: 7
  total_plans: 9
  completed_plans: 9
---

# STATE

## Current Position

Phase: 25 (rollout-gates-safe-fallback) — EXECUTING
Plan: 1 of 1
Status: Phase complete — ready for verification
Last activity: 2026-04-05

## Architecture Decision

**Nautilus BacktestEngine Integration** (decided 2026-03-23):

- Nautilus handles: order execution, SL/TP matching (O→H→L→C), fill models, slippage, portfolio P&L
- Aureus handles: signal pipeline (18 signals via `AureusSignalActor`), strategy evaluation (via `AureusStrategyAdapter`)
- Output: TimescaleDB (backtest results) → Custom UI (primary) + Grafana (supplementary)
- Existing infra leveraged: `aureus-nautilus-node`, `aureus-nautilus-bridge`, TimescaleDB, Grafana, Prometheus

## Accumulated Context

### Roadmap Evolution

- Phase 21.1.1 inserted after Phase 21.1: Patch TradingAgents Source Code for LLM Proxy Support (URGENT)
- Phase 21.1 inserted after Phase 21: TradingAgents LLM Proxy Configuration Fix Gap (URGENT)
- Phase 15.7 added: Sequence enabled but no-entry trigger diagnosis
- Phase 15.12 inserted after Phase 15.11: Improve strategy quality using log_signal_normalize instead of signal_history (URGENT)
- Phase 15.13 inserted after Phase 15.12: Sweep signal gap analysis (URGENT)
- Phase 15.14 inserted after Phase 15.13: Suspicious sweep event reconciliation (URGENT)
- Phase 15.15 inserted after Phase 15.14.1: Align strategy with new tags (URGENT)
- Phase 15.16 inserted after Phase 15.15: Investigate CHOCH-strategy backtest mismatch (URGENT)
- Phase 15.17 inserted after Phase 15.16: Decouple Strategy Engine into 2 microservices (URGENT)
- 2026-03-27: Phase 15.10 được mở lại để đồng bộ contract `signal_history/log_signal` sau khi rollback một phần.
- `SymbolState.log_signal` hiện ở legacy signature (`tag`, `timestamp`, `value`, `data`) nhưng nhiều call-site vẫn truyền metadata kwargs (`category`, `explain`, `inputs`) trong:
  - `services/aureus-signal/engine/live_engine.py`
  - `services/aureus-signal/engine/backtest_engine.py`
  - `services/aureus-signal/signal_computer.py`
- Quick verification hiện tại: `pytest tests/test_decision_trace_schema.py tests/test_signal_contract_normalization.py -q` → `19 passed` (chưa phủ đầy đủ runtime loop live/backtest).

- v1.1 Signal Optimization: Toàn bộ tín hiệu lõi modular hóa, 100% test coverage
- v1.2 Strategy Sequence Engine: O(1) state machine, 3-pillar framework, legacy deprecated
- All strategies run through TemplateStrategy with context_filters, sequence, trade_execution
- Existing Nautilus live integration: AureusMarketDataClient, AureusExecutionClient, SyncWorker, NautilusBridge
- Strategy QA Decision (2026-03-23): Must validate strategy quality independently before Nautilus integration — otherwise poor backtest results cannot be attributed (strategy vs integration)
- Backlog items: Early Exit Engine, BEARISH seeds, sweep_o1 tag fix (deferred to future)

### Pending Todos

- [2026-03-28-remove-market-regime-use-htf-trend](file:///D:/Aureus/.planning/todos/pending/2026-03-28-remove-market-regime-use-htf-trend.md)
- [2026-03-28-investigate-sweep-triggers-after-broken-pending](file:///D:/Aureus/.planning/todos/pending/2026-03-28-investigate-sweep-triggers-after-broken-pending.md)
