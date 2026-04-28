---
phase: quick-260429-8th-implement-limit-order-lifecycle-linkage
plan: 01
completed_at: 2026-04-29T06:34:00+07:00
status: completed
tasks: 3
commits:
  - 84b519d
  - f1f5c14
  - 2a79c31
---

# Quick 260429-8th Summary: Implement limit order lifecycle linkage

## Tóm tắt

Đã tách semantic lifecycle cho LIMIT/STOP pending order: pending placement lưu `pending_order_id` riêng và không chuyển journal sang `EXECUTED`; khi MT5 fill thật mới ghi `ticket/position_id` bằng `position_ticket`, `entry_deal_ticket` bằng deal ticket, và close lookup dùng position ticket.

## Task đã hoàn thành

| Task | Kết quả | Commit |
| --- | --- | --- |
| Task 1 | Thêm contract Python/schema/tests cho trace_id, ORDER_PENDING_PLACED, ORDER_FILLED, close lookup bằng position ticket | 84b519d |
| Task 2 | Tách MQL5 event emitters `ORDER_PENDING_PLACED` và `ORDER_FILLED`; pending branch không emit `ORDER_OPENED` | f1f5c14 |
| Task 3 | Thêm script DB E2E thật cho pending placed -> filled -> closed và đã chạy pass trên dev DB | 2a79c31 |

## File thay đổi

- `D:/Aureus/services/aureus-trader/order_builder.py`
- `D:/Aureus/services/aureus-trader/dispatcher.py`
- `D:/Aureus/services/aureus-trader/journal.py`
- `D:/Aureus/services/aureus-trader/tests/test_order_builder.py`
- `D:/Aureus/services/aureus-trader/tests/test_dispatcher.py`
- `D:/Aureus/services/aureus-trader/tests/test_journal.py`
- `D:/Aureus/services/aureus-db-writer/migrations/add_trade_journal.sql`
- `D:/Aureus/mql5/AureusProvider.mq5`
- `D:/Aureus/services/aureus-trader/scripts/verify_limit_order_lifecycle_db_e2e.py`

## GitNexus / impact analysis

GitNexus MCP tools (`gitnexus_impact`, `gitnexus_detect_changes`) không được expose trong phiên executor này, nên không thể chạy impact/detect theo CLAUDE.md. Đã áp dụng fallback có kiểm soát:

- Đọc trực tiếp các symbol theo plan trước khi sửa: `build_order_command`, `OrderDispatcher._extract_mt5_execution_payload`, `OrderDispatcher.dispatch_order`, `OrderDispatcher.event_listener`, `TradeJournalManager.on_order_opened`, `TradeJournalManager.on_order_closed`, `ExecuteOpenOrder`, `PushOrderOpened`, `OnTradeTransaction`.
- Giữ thay đổi surgical trong đúng file plan.
- Trước commit dùng `git diff --stat`, `git status --short`, test unit và DB E2E để xác nhận phạm vi.

Blast radius thực tế quan sát được:

- Python order dispatch path: command payload -> MT5 -> dispatcher result/event listener -> journal persistence.
- Journal DB path: `aureus_trade_journal` và `aureus_trade_signal_snapshots` khi fill thật.
- MQL5 provider event path: pending order accept và `DEAL_ENTRY_IN/OUT` transaction.

## Verification đã chạy

1. Unit/contract tests qua WSL:

```bash
wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus/services/aureus-trader && ../../.venv/bin/python -m pytest tests/test_order_builder.py tests/test_dispatcher.py tests/test_journal.py -x"
```

Kết quả: `102 passed in 1.01s`.

2. DB E2E thật qua WSL/dev TimescaleDB:

```bash
wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus/services/aureus-trader && AUREUS_DB_DSN=postgresql://aureus:aureus_password@localhost:5433/aureus ../../.venv/bin/python scripts/verify_limit_order_lifecycle_db_e2e.py"
```

Kết quả: `PASS limit lifecycle DB E2E trace_id=e2e-limit-2c1d99f82f23 cmd_id=ord-e2e-6ec9fc74`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] WSL path `/mnt/d/Aureus` không tồn tại khi chạy command trực tiếp từ shell hiện tại**
- **Found during:** Task 1 verification
- **Issue:** Lệnh plan dạng `cd /mnt/d/Aureus/...` fail trong shell hiện tại.
- **Fix:** Theo `RUN_SERVICES.md`, chạy backend/test qua `wsl -d Aureus -e bash -lc "..."` và dùng `.venv/bin/python`.
- **Files modified:** Không có.
- **Commit:** N/A

**2. [Rule 3 - Blocking] DB DSN default `aureus-db:5432` không resolve từ WSL host**
- **Found during:** Task 3 DB E2E
- **Issue:** Script chạy từ WSL host không resolve hostname container `aureus-db`; lần thử `localhost:5433` với password mặc định fail.
- **Fix:** Kiểm tra container env và chạy E2E với `AUREUS_DB_DSN=postgresql://aureus:aureus_password@localhost:5433/aureus`.
- **Files modified:** Không có.
- **Commit:** N/A

**3. [Rule 1 - Bug] Synthetic parent `aureus_trades` thiếu NOT NULL columns**
- **Found during:** Task 3 DB E2E
- **Issue:** Insert parent row cho FK thiếu `direction` và `entry_type` nên DB E2E fail NotNullViolation.
- **Fix:** E2E script insert tối thiểu `symbol`, `direction`, `entry_type`, `entry_price`, `status`.
- **Files modified:** `D:/Aureus/services/aureus-trader/scripts/verify_limit_order_lifecycle_db_e2e.py`
- **Commit:** 2a79c31

## Known Stubs

Không phát hiện stub/placeholder ảnh hưởng mục tiêu plan trong các file đã tạo/sửa.

## Threat Flags

Không có threat surface mới ngoài threat model plan. Các thay đổi nằm trong event ingestion/persistence path đã được threat model cover; SQL dùng parameterized queries và fill transition validate ticket/price/time trước khi EXECUTED.

## MT5 manual verification notes

Chưa compile/chạy trực tiếp trong MT5 terminal ở executor. Source MQL5 đã có event emitters riêng và Python consumer/tests/DB E2E đã pass; cần manual MT5 smoke test ở terminal thật để xác nhận broker history fields `DEAL_ORDER`/comment trả đúng như kỳ vọng.

## Self-Check: PASSED

- Summary file tồn tại: `D:/Aureus/.planning/quick/260429-8th-implement-limit-order-lifecycle-linkage-/260429-8th-SUMMARY.md`
- Commits tồn tại: `84b519d`, `f1f5c14`, `2a79c31`
- Code/task commits đã tạo riêng từng task.
- Docs artifacts chưa commit theo constraint của orchestrator.
