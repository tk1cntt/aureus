---
gsd_state_version: 1.0
milestone: v1.3
milestone_name: Backtesting & Measurement Engine
status: Executing Phase 15.10
last_updated: "2026-03-27T19:08:25+07:00"
progress:
  total_phases: 11
  completed_phases: 2
  total_plans: 9
  completed_plans: 2
---

# STATE

## Current Position

Phase: 15.10 (Pydantic Signal History Refactoring) — EXECUTING (reopened)
Plan: 1 of 1

## Architecture Decision

**Nautilus BacktestEngine Integration** (decided 2026-03-23):

- Nautilus handles: order execution, SL/TP matching (O→H→L→C), fill models, slippage, portfolio P&L
- Aureus handles: signal pipeline (18 signals via `AureusSignalActor`), strategy evaluation (via `AureusStrategyAdapter`)
- Output: TimescaleDB (backtest results) → Custom UI (primary) + Grafana (supplementary)
- Existing infra leveraged: `aureus-nautilus-node`, `aureus-nautilus-bridge`, TimescaleDB, Grafana, Prometheus

## Accumulated Context

### Roadmap Evolution

- Phase 15.7 added: Sequence enabled but no-entry trigger diagnosis
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
