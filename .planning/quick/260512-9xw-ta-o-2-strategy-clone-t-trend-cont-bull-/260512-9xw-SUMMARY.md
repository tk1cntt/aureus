# Quick Task 260512-9xw — Summary

**Task:** Tạo 2 strategy clone từ `TREND_CONT_BULL` và `TREND_CONT_BEAR`; chỉ vào lệnh `LIMIT` tại FVG đầu tiên sau pivot HH/LL tương ứng khi có CHOCH; không có FVG thì không vào lệnh.

## Kết quả

- Thêm entry method `ENTRY_FVG_FROM_CHOCH_PIVOT` vào whitelist.
- Live order routing hỗ trợ `_entry_fvg_from_choch_pivot`:
  - BUY dùng pivot `LL`.
  - SELL dùng pivot `HH`.
  - Lọc FVG cùng hướng, chưa broken, timestamp sau pivot.
  - Entry price dùng midpoint FVG.
  - Không pivot/FVG hợp lệ trả `None`, khiến order reject `ENTRY_PRICE_UNAVAILABLE`.
- Simulated/backtest routing hỗ trợ cùng entry method.
- Thêm seed strategies:
  - `TREND_CONT_FVG_BULL`
  - `TREND_CONT_FVG_BEAR`
- Strategy gốc `TREND_CONT_BULL` / `TREND_CONT_BEAR` giữ nguyên semantic.

## Files đổi

- `services/aureus-signal/engine/snapshot_utils.py`
- `services/aureus-signal/engine/orders.py`
- `services/aureus-signal/engine/simulated_orders.py`
- `services/aureus-signal/engine/strategies/seed_strategies.py`
- `services/aureus-signal/tests/test_entry_price_methods.py`
- `services/aureus-signal/tests/test_strategy_seed_sync.py`

## GitNexus impact

- `VALID_ENTRY_METHODS`: GitNexus CLI không tìm thấy constant trong index.
- `_calculate_entry_price`: GitNexus match nhầm test symbol; risk `LOW`, direct callers `0`, affected processes `0`.
- `seed_system_strategies`: risk `CRITICAL`; direct callers `8`; affected processes `14`.
  - d1 callers: `scripts/seed_strategies.py:run`, `strategy_seed_sync_dryrun._run`, `strategy_executor.run_strategy_executor`, `strategy_executor.listen_for_reload`, `live_engine.run_signal_engine`, `live_engine.listen_for_reload`, `backtest_engine.run_backtest_engine`, `seed_strategies.py:run`.
  - Mitigation: chỉ thêm clone seed mới, không đổi seed cũ; regression tests assert strategy cũ vẫn `MARKET/CURRENT`.

## Detect changes

GitNexus CLI hiện không expose command `detect-changes`. Scope check thay thế:

```bash
git diff --name-only 1c7b397..HEAD
```

Kết quả chỉ gồm 6 file expected ở trên.

## Tests

```bash
wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus && ./.venv/bin/python -m pytest services/aureus-signal/tests/test_entry_price_methods.py services/aureus-signal/tests/test_strategy_seed_sync.py -q"
```

Kết quả: `34 passed, 1 failed`.

Failure unrelated tới quick task:

```text
services/aureus-signal/tests/test_strategy_seed_sync.py::test_runbook_contract
AssertionError: missing runbook
/mnt/d/Aureus/.planning/phases/46-strategy-seed-sync/46-ROLLBACK-RUNBOOK.md
```

Các tests entry/FVG/seed clone mới pass trước failure unrelated.

## Commit code

- `02b559f feat(260512-9xw): add FVG CHOCH pivot limit strategies`
