---
phase: 260521-wma-update-2-strategy-trend-cont-bull-va-tre
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - services/aureus-signal/engine/strategies/template.py
  - services/aureus-signal/engine/strategies/seed_strategies.py
  - services/aureus-signal/tests/test_seed_strategies_context_filters.py
  - services/aureus-signal/tests/test_strategy_seed_sync.py
autonomous: true
requirements:
  - QUICK-260521-WMA
must_haves:
  truths:
    - "TREND_CONT_BULL chỉ pass context khi close hôm qua > POC hôm qua, close hiện tại > POC hiện tại, H1 CISD tăng."
    - "TREND_CONT_BEAR chỉ pass context khi close hôm qua < POC hôm qua, close hiện tại < POC hiện tại, H1 CISD giảm."
    - "Thiếu hoặc sai TPO/CISD context làm strategy bị chặn trước sequence, không fallback linh tinh."
    - "Seed DB strategy templates chứa context_filters mới cho đúng 2 strategy TREND_CONT_BULL và TREND_CONT_BEAR."
  artifacts:
    - path: "services/aureus-signal/engine/strategies/template.py"
      provides: "context filter evaluator đọc TPO D0/D1 và H1 CISD từ state/snapshot"
      contains: "trend_cont_poc_cisd"
    - path: "services/aureus-signal/engine/strategies/seed_strategies.py"
      provides: "seed declarations cho TREND_CONT_BULL/TREND_CONT_BEAR"
      contains: "trend_cont_poc_cisd"
    - path: "services/aureus-signal/tests/test_seed_strategies_context_filters.py"
      provides: "focused unit tests cho pass/fail filter bull/bear"
    - path: "services/aureus-signal/tests/test_strategy_seed_sync.py"
      provides: "seed sync contract test xác nhận DB-backed templates có filters mới"
  key_links:
    - from: "services/aureus-signal/engine/strategies/seed_strategies.py"
      to: "services/aureus-signal/engine/strategies/template.py"
      via: "context_filters type trend_cont_poc_cisd"
      pattern: "\"type\": \"trend_cont_poc_cisd\""
    - from: "services/aureus-signal/engine/strategies/template.py"
      to: "state.transient_signals/state.tpo_profile or indicator snapshot data"
      via: "safe extraction of tpo_d0/tpo_d1 POC and H1 CISD direction"
      pattern: "tpo_d0|tpo_d1|cisd_h1"
---

# Objective

Cập nhật đúng 2 strategy `TREND_CONT_BULL` và `TREND_CONT_BEAR` để thêm `context_filters` theo yêu cầu:

- `TREND_CONT_BULL`: close hôm qua > POC hôm qua, close hiện tại > POC hiện tại, H1 CISD tăng.
- `TREND_CONT_BEAR`: ngược lại, close hôm qua < POC hôm qua, close hiện tại < POC hiện tại, H1 CISD giảm.

Purpose: chặn trigger khi trend-cont context chưa đủ mạnh, giữ sequence/entry logic hiện tại.
Output: evaluator filter mới, seed config mới, test unit + seed sync đủ rõ.

# Execution Context

- `D:/Aureus/.claude/get-shit-done/workflows/execute-plan.md`
- `D:/Aureus/.claude/get-shit-done/templates/summary.md`

# Context

- `D:/Aureus/CLAUDE.md`
- `D:/Aureus/.planning/STATE.md`
- `D:/Aureus/services/aureus-signal/engine/strategies/template.py`
- `D:/Aureus/services/aureus-signal/engine/strategies/seed_strategies.py`
- `D:/Aureus/services/aureus-signal/tests/test_seed_strategies_context_filters.py`
- `D:/Aureus/services/aureus-signal/tests/test_strategy_seed_sync.py`

## Interfaces cần dùng

- `TemplateStrategy._evaluate_context(state_obj)` hiện xử lý `context_filters` theo `type`; thêm nhánh mới tại đây, không đổi `_evaluate_sequence` hoặc execution output.
- `seed_system_strategies(pool=None, conn=None)` seed DB-backed strategy templates; `TREND_CONT_BULL` và `TREND_CONT_BEAR` hiện có `context_filters: []`.
- `SymbolState` có `transient_signals`, `log_signal_normalize`, `last_candle`, `prev_candle`, `tracking_vars`; TPO hiện xuất qua các key `tpo_d0`, `tpo_d1`; CISD H1 qua `cisd_h1` hoặc tag dạng `cisd_h1_bullish`/`cisd_h1_bearish`.

# Tasks

## Task 1: Thêm filter evaluator `trend_cont_poc_cisd`

`type`: auto, `tdd`: true

`files`:
- `D:/Aureus/services/aureus-signal/engine/strategies/template.py`
- `D:/Aureus/services/aureus-signal/tests/test_seed_strategies_context_filters.py`

`behavior`:
- Bull pass khi previous_close > tpo_d1.POC, current_close > tpo_d0.POC, H1 CISD bullish/up.
- Bear pass khi previous_close < tpo_d1.POC, current_close < tpo_d0.POC, H1 CISD bearish/down.
- Equal POC không pass vì yêu cầu dùng `>` và `<`.
- Missing/không parse được close/POC/CISD phải fail filter với detail rõ, không pass ngầm.

`action`:
Trước khi sửa symbol, executor phải chạy GitNexus impact upstream cho `TemplateStrategy._evaluate_context` hoặc symbol index tương ứng, báo direct callers/affected flows/risk. Sau đó thêm nhánh `elif f_type == "trend_cont_poc_cisd"` trong `_evaluate_context`.

Thiết kế config tối thiểu:

```python
{"type": "trend_cont_poc_cisd", "direction": "bullish"}
{"type": "trend_cont_poc_cisd", "direction": "bearish"}
```

Evaluator phải tự discover dữ liệu từ state theo thứ tự ít rủi ro, không đổi pipeline data nếu chưa cần:

1. current close: ưu tiên `state_obj.last_candle["c"]`, fallback record cuối trong `log_signal_normalize` có `price` hoặc `close`, fallback `state_obj.current_signal["close"]` nếu có.
2. previous close: ưu tiên `state_obj.prev_candle["c"]`, fallback record liền trước trong `log_signal_normalize` có `price` hoặc `close`.
3. POC hiện tại: `tpo_d0.POC` hoặc `tpo_d0.poc` từ `state_obj.tpo_profile`, `state_obj.current_signal["indicator_snapshot"]`, hoặc `state_obj.indicator_snapshot` nếu tồn tại.
4. POC hôm qua: `tpo_d1.POC` hoặc `tpo_d1.poc` cùng nguồn.
5. H1 CISD: pass khi transient có `cisd_h1_bullish`/`cisd_h1_bearish`, hoặc key `cisd_h1` có value/direction/status là bullish/up hoặc bearish/down. Không invent CISD từ candle color.

Giữ surgical: helper private nhỏ trong `_evaluate_context` hoặc local nested helper được phép, nhưng không refactor toàn class. Không sửa sequence matching. Không thêm fallback đảo chiều.

`verify`:
```bash
cd D:/Aureus/services/aureus-signal && python -m pytest tests/test_seed_strategies_context_filters.py -q
```

`done`:
- Unit tests chứng minh bull/bear pass đúng và fail đúng khi đổi dấu POC/CISD hoặc thiếu dữ liệu.
- `_evaluate_context` trả `failed_filters` chứa `trend_cont_poc_cisd:<direction>` khi fail.

## Task 2: Seed đúng 2 strategy và cập nhật seed sync contract

`type`: auto, `tdd`: true

`files`:
- `D:/Aureus/services/aureus-signal/engine/strategies/seed_strategies.py`
- `D:/Aureus/services/aureus-signal/tests/test_strategy_seed_sync.py`
- `D:/Aureus/services/aureus-signal/tests/test_seed_strategies_context_filters.py`

`behavior`:
- `TREND_CONT_BULL` seed config có đúng filter `{"type": "trend_cont_poc_cisd", "direction": "bullish"}`.
- `TREND_CONT_BEAR` seed config có đúng filter `{"type": "trend_cont_poc_cisd", "direction": "bearish"}`.
- Không tự thêm filter này cho `TREND_CONT_LIMIT_*`, `TREND_CONT_FVG_*`, hoặc strategy khác.
- Existing trade_execution giữ nguyên: bull market current BUY, bear market current SELL.

`action`:
Trước khi sửa symbol, executor phải chạy GitNexus impact upstream cho `seed_system_strategies` và báo blast radius. Sau đó cập nhật `context_filters` của đúng 2 seed declarations đầu file. Cập nhật test cũ đang assert seed strategies không có context_filters: đổi thành assert chỉ `TREND_CONT_BULL`/`TREND_CONT_BEAR` có filter mới, các strategy còn lại trong test vẫn không có filter nếu hiện tại đúng. Cập nhật `test_strategy_seed_sync.py` để FakePool/FakeConn seed path xác nhận DB-backed config được upsert với context_filters mới.

Nếu phát hiện seed sync có script apply DB riêng, không sửa script trừ khi test fail chỉ ra contract thiếu; plan này chỉ đổi source seed + tests.

`verify`:
```bash
cd D:/Aureus/services/aureus-signal && python -m pytest tests/test_strategy_seed_sync.py tests/test_seed_strategies_context_filters.py -q
```

`done`:
- Tests xác nhận seed config mới đúng 2 strategy.
- Không thay đổi entry type/method, direction, SL/TP/trailing hiện tại.

## Task 3: DB/config verification cho strategy template data

`type`: auto

`files`:
- `D:/Aureus/services/aureus-signal/engine/strategies/seed_strategies.py`
- `D:/Aureus/services/aureus-signal/tests/test_strategy_seed_sync.py`

`action`:
Vì strategy templates DB-backed, executor phải chạy verification ở mức DB/config theo cách hiện có trong repo. Trước tiên đọc test/fixture seed DB hiện có trong `tests/test_strategy_seed_sync.py` và scripts liên quan mà test nhắc tới. Nếu repo có dry-run seed sync command, chạy dry-run để thấy payload `TREND_CONT_BULL`/`TREND_CONT_BEAR` chứa filter mới. Nếu có DB test command trong repo, chạy focused DB/config E2E đó. Nếu local DB không sẵn, chạy fake DB upsert test ở Task 2 và ghi rõ blocked DB runtime trong summary, kèm command cần user chạy.

Bắt buộc chạy `gitnexus_detect_changes()` trước khi commit hoặc trước summary cuối, kiểm tra chỉ ảnh hưởng expected symbols/flows.

`verify`:
```bash
cd D:/Aureus/services/aureus-signal && python -m pytest tests/test_strategy_seed_sync.py -q
```

`done`:
- Có bằng chứng config DB-backed seed path upsert context_filters mới.
- Nếu DB thật chạy được: query hoặc dry-run output xác nhận 2 templates có filters mới.
- Nếu DB thật không chạy được: summary nêu rõ lý do và command DB verification còn lại.

# Threat Model

## Trust Boundaries

| Boundary | Description |
|---|---|
| strategy config DB -> TemplateStrategy | DB JSON config điều khiển filter logic runtime |
| market signal state -> strategy evaluator | dữ liệu TPO/CISD/close từ pipeline vào quyết định order |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|---|---|---|---|---|
| T-260521-WMA-01 | Tampering | `context_filters` JSON | mitigate | Chỉ support `trend_cont_poc_cisd` với `direction` bullish/bearish; unknown/missing data fail closed. |
| T-260521-WMA-02 | Denial of Service | `_evaluate_context` per-candle path | mitigate | O(1) extraction từ state/snapshot, không scan DataFrame lớn, không DB call trong evaluator. |
| T-260521-WMA-03 | Repudiation | filter rejection reason | mitigate | Populate `failed_filters` và `details` rõ POC/CISD condition fail để logs/rejections truy vết được. |
| T-260521-WMA-04 | Elevation of Privilege | strategy trigger bypass | mitigate | Missing TPO/CISD/close fail closed, không fallback pass. |

# Verification

Chạy tối thiểu:

```bash
cd D:/Aureus/services/aureus-signal && python -m pytest tests/test_seed_strategies_context_filters.py tests/test_strategy_seed_sync.py -q
```

Nếu command lỗi do service/env, đọc `D:/Aureus/RUN_SERVICES.md` rồi retry theo hướng dẫn dự án.

Trước kết thúc code task, chạy GitNexus detect changes theo project rule.

# Success Criteria

- `TREND_CONT_BULL` có context filter yêu cầu previous close > D1 previous POC, current close > D0/current POC, H1 CISD bullish/up.
- `TREND_CONT_BEAR` có context filter mirror bearish/down.
- Filter fail closed khi thiếu dữ liệu.
- Tests focused pass.
- Seed sync/fake DB config verification pass; DB thật được verify hoặc summary nêu blocker cụ thể.

# Output

Sau khi xong, tạo summary tại:

`D:/Aureus/.planning/quick/260521-wma-update-2-strategy-trend-cont-bull-va-tre/260521-wma-SUMMARY.md`
