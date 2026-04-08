# Phase 37: Trade Execution Journal - Context

**Gathered:** 2026-04-08T13:00:00+07:00
**Status:** Ready for planning
**Source:** Research + Roadmap + User Requirements

<domain>
## Phase Boundary

Phase 37: Trade Execution Journal — Lưu nhật ký thực thi trade từ strategy trigger → order tạo → order close MT5. Bảng ghi đủ thông tin để phân tích hiệu quả strategy: lý do vào lệnh, signal active, kết quả PnL.

- **Signal Service** ghi journal entry khi strategy match emission
- **Trader Service** update order info khi MT5 execute
- **Gateway/EA** update exit info khi MT5 close
- **API** endpoint `/api/v1/journal` để query, filter, phân tích

</domain>

<decisions>
## Implementation Decisions

### Database Design
- **Bảng mới `aureus_trade_journal`** — tách biệt `aureus_trades`, 1:N trace_id → journal entries cho analysis
- JSONB cho signal context và context filters — linh hoạt cho analysis
- Index cho strategy_id, direction, created_at — query nhanh

### Signal Context Capture (TBJ-02)
- **Signal Service** (`strategy_executor.py` hoặc `signal_emitter.py`) ghi journal entry khi strategy match emit
- Payload: strategy_name, strategy_id, direction, score, active_signals (JSONB), context_filters (JSONB), origin_timestamp
- Redis stream là nguồn chính xác nhất của signal events

### Order Info Update (TBJ-03)
- **Trader Service** (`aureus-trader/dispatcher.py`) update journal khi order dispatch thành công
- Update: order_id (MT5 ticket), position_id, entry_price, entry_time, lot_size, SL, TP

### Exit Info Update (TBJ-04)
- **MT5 EA** gửi event `POSITION_CLOSED` / `ORDER_CLOSED` → Gateway → DB
- DB writer cập nhật journal: exit_price, exit_time, exit_reason, pnl, pnl_pips, duration_seconds
- Exit reasons: "TP_HIT", "SL_HIT", "TRAILING_STOP", "MANUAL_CLOSE", "EARLY_EXIT"

### API Design (TBJ-05)
- `GET /api/v1/journal` với filters: strategy, direction, status, date range, symbol, pnl range
- Summary: aggregated stats per strategy

### the agent's Discretion
- Migration SQL trong services/aureus-db-writer/migrations/
- Journal creation/updates qua asyncpg giống current DB pattern
- 3 checkpoints: TRIGGERED → EXECUTED → CLOSED
- Không dùng trigger trên aureus_trades — journal là separate flow

</decisions>

<canonical_refs>
## Canonical References

### Trade State Management
- `services/aureus-db-writer/db_writer.py` — Current audit table với 6-state audit
- `services/aureus-db-writer/migrations/add_magic_number.sql` — Latest migration

### Signal Execution Pipeline
- `services/aureus-signal/engine/strategy_executor.py` — Strategy executor, read Redis stream, emit matches
- `services/aureus-signal/engine/strategies/template.py` — TemplateStrategy on_bar_close(), build_order_plan()
- `services/aureus-signal/engine/strategies/seed_strategies.py` — 6 seed strategies

### Order Execution
- `services/aureus-trader/dispatcher.py` — Order dispatcher → Gateway TCP
- `services/aureus-trader/order_builder.py` — Build MT5 order commands
- `services/aureus-trader/main.py` — Main trader service

### MT5 Gateway
- `services/aureus-gateway/gateway.py` — TCP server, MT5 order execution
- `services/aureus-gateway/tcp_handler.py` — Handle EA commands, backend responses

### Existing DB Schema
- `aureus_trades` — trace_id, ticket, symbol, magic_number, strategy_id, strategy_name, direction, entry_type, status, entry_price, exit_price, sl, tp, volume, commission, swap, profit, created_at, updated_at, filled_at, closed_at, payload JSONB
- `aureus_execution_events` — hypertable, trace_id, status, event_time, details, symbol
- `aureus_account_snapshots` — balance, equity, margin, profit per symbol

</canonical_refs>

<specifics>
## User Requirements

User: "Khi có một strategy được trigger và tạo order, hãy lưu thông tin strategy và order đó vào db, sau khi order đó trên MT5 close, update lại kết quả vào db."

Thông tin cần lưu:
1. **Thời điểm** — entry_time, exit_time (biết lệnh vào lúc nào)
2. **Context** — session, market condition, HTF trend (tại sao chọn thời điểm này)
3. **Lý do** — strategy name, sequence matched (lý do vào lệnh)
4. **Signal active** — choch, sweep, bos, ob (pattern nào đã trigger)
5. **Kết quả** — pnl, pnl_pips, exit_reason, duration (lệnh hiệu quả không)
6. **Đánh giá** — score, win rate per strategy (chiến lược nào đáng tin)

</specifics>

<deferred>
## Deferred Ideas

None

</deferred>

---

*Phase: 37-trade-execution-journal*
