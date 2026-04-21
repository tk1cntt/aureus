---
phase: 54-strategy-scoring-framework
plan: 02
status: completed
updated_at: 2026-04-21
---

# 54-02 Summary — Strategy Executor Scoring Wiring

## Kết quả thực thi

Đã hoàn tất wiring scoring theo phạm vi plan 54-02 với thay đổi tối thiểu và tương thích:

- Tạo module aggregate scorer:
  - `services/aureus-signal/engine/scoring/aggregate.py`
  - API: `update_aggregate_score(records, strategy_name, symbol, timeframe, score_version)`
  - Trả về: `aggregate_score`, `trade_count`, `score_version`, `group_key` và dimensions.

- Tạo scoring compute contract tối thiểu cho executor consume:
  - `services/aureus-signal/engine/scoring/compute.py`
  - API: `compute_trade_score(input_payload, score_version, weights_snapshot)`
  - Output gồm các key audit: `gate`, `score_version`, `weights_snapshot`, `criteria`, `missing_data_policy`, `score_total`.

- Wiring vào executor:
  - `services/aureus-signal/engine/strategy_executor.py`
  - Thêm call `compute_trade_score(...)` trong `enrich_strategy_decisions_with_contract_metadata(...)` để gắn:
    - `score_total`
    - `score_breakdown`
    - `score_version`
    - `weights_snapshot`
    - `missing_data_policy`
  - Chuẩn hóa precision nội bộ 6 decimals cho `score_total` và `criteria[*].normalized`.
  - Thêm call `update_aggregate_score(...)` trong flow `run_strategy_executor(...)`.
  - Aggregate artifact khóa đúng dimension `strategy/symbol/timeframe` thông qua group key `"{strategy}|{symbol}|{timeframe}"`.

- Tạo tests:
  - `services/aureus-signal/tests/test_strategy_scoring_aggregate.py`
  - `services/aureus-signal/tests/test_strategy_scoring_e2e.py`
  - Assert đầy đủ key contract audit + precision 6 decimals + dimension aggregate.

## Verification

### Fast subset (plan task-level)
Command:

`wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus/services/aureus-signal && ../../.venv/bin/python -m pytest tests/test_strategy_scoring_aggregate.py tests/test_strategy_scoring_e2e.py -q"`

Result: **4 passed**

### Full signal suite (phase gate)
Command:

`wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus/services/aureus-signal && ../../.venv/bin/python -m pytest tests -x -q"`

Result: **failed ngoài scope thay đổi** tại `tests/test_cisd.py::TestBearishCISD::test_value_is_positive` (expected 5.0, actual 112.5).

=> Failure này thuộc vùng CISD hiện hữu, không nằm trong các file/symbol được chỉnh của plan 54-02.

## Impact analysis đã thực hiện trước chỉnh sửa

- `enrich_strategy_decisions_with_contract_metadata` (upstream): risk **CRITICAL**, direct caller `run_strategy_executor`, d=2 `main_executor.py`.
- `run_strategy_executor` (upstream): risk **LOW**, direct caller `main_executor.py`.

Thay đổi được giữ backward-compatible với interface executor hiện tại.

## Ghi chú phạm vi

- Không tạo migration/new table/schema.
- Persistence cho scoring ở mức runtime payload contract tại executor (phù hợp D-13).
