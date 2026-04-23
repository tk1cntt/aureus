# Quick Task 260423-t4w Summary

## Mục tiêu
Tối ưu payload `OPEN_ORDER` gửi sang MT5: chỉ giữ field execution cần thiết, loại bỏ payload nặng như `signal_snapshot` khỏi message publish sang `aureus:mt5:commands`.

## Blast Radius (Impact đã ghi nhận trước khi edit)
- `build_order_command` (upstream)
  - d=1 direct caller: `run_trader` (`services/aureus-trader/main.py`)
  - d=2: `main.py`
  - Affected process group: `Run_trader` (các bước dispatch/retry/wait response)
  - Risk level: **CRITICAL**
- `dispatch_order` (upstream)
  - d=1 direct caller: `dispatch_loop`
  - d=2: `run_trader`
  - d=3: `main.py`
  - Affected process group: `Run_trader`
  - Risk level: **CRITICAL**

## Thay đổi đã thực hiện
1. `services/aureus-trader/order_builder.py`
   - Không còn đưa `trace_id` và `signal_snapshot` vào command payload dùng cho MT5 execution.
2. `services/aureus-trader/dispatcher.py`
   - `dispatch_order` publish `mt5_order = _extract_mt5_execution_payload(order)` thay vì publish toàn bộ `order`.
   - Bổ sung `_extract_mt5_execution_payload` whitelist field cho MT5:
     - `type, symbol, cmd_id, direction, order_type, volume, price, sl, tp, magic, comment, tp_rr_ratio, size_mode, risk_amount`.
   - Giữ nguyên khả năng enrich event nội bộ cho journal sau khi nhận `ORDER_OPENED`.
3. Tests contract/payload:
   - `services/aureus-trader/tests/test_order_builder.py`
   - `services/aureus-trader/tests/test_dispatcher.py`
   - Khóa contract để đảm bảo payload gửi MT5 không chứa `signal_snapshot`, `score_breakdown`, `weights_snapshot`, v.v.

## Kết quả verify
- Unit tests:
  - `wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus && ./.venv/bin/python -m pytest services/aureus-trader/tests/test_order_builder.py services/aureus-trader/tests/test_dispatcher.py -q"`
  - Kết quả: **29 passed**.
- E2E files theo plan:
  - `pytest services/aureus-trader/tests/test_e2e_trader.py services/aureus-trader/tests/test_e2e_mt5_orders.py -q`
  - Kết quả: **no tests ran** (file e2e theo dạng script/manual flow, không phải pytest test function).

## Scope check trước commit
Do CLI hiện tại không có `gitnexus_detect_changes` subcommand trong môi trường này, dùng scope check tương đương bằng `git diff --cached --name-only` và chỉ stage đúng file thuộc quick task.

## Kết luận
Payload `OPEN_ORDER` publish sang MT5 đã được thu gọn theo whitelist execution fields; `signal_snapshot` không còn đi vào command channel MT5.