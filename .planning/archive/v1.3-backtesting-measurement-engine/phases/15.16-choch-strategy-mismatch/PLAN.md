---
wave: 1
depends_on: []
files_modified:
  - services/aureus-signal/tests/test_strategy_choch_triggers.py
  - services/aureus-signal/engine/event_policy.py
  - services/aureus-signal/engine/strategies/seed_strategies.py
autonomous: false
---

# Plan 01: Audit pipeline and align CHOCH tags to fix strategy triggers

<objective>
Điều tra định lượng và vá lỗi pipeline khiến event CHOCH có trong data raw nhưng strategy không sinh ra Trade Intent. Tạo bài test đo đạc Control Benchmark và áp dụng fix để đảm bảo trigger rate > 0 trên thư viện data mẫu.
</objective>

<requirements>
PHASE-15.16
</requirements>

<must_haves>
- Tồn tại script test định lượng chẩn đoán được vì sao CHOCH bị block.
- Có vòng Control Benchmark (chạy strategy tắt bớt context_filters) để tìm gốc rễ point of failure.
- Áp dụng code fix (alias, normalize hoặc strategy config).
- Test suite pass 100% chứng minh strategy thực sự bắn ra được trigger (Trade Intent) khi ăn dữ liệu nến chứa CHOCH.
</must_haves>

<step>
<task>Tạo script test chẩn đoán (Diagnostic Control Benchmark)</task>
<read_first>
- `data-test.json` (để lấy mock nến thực tế đang gây ra missed triggers)
- `services/aureus-signal/engine/strategies/seed_strategies.py` (cấu trúc config)
- `services/aureus-signal/engine/event_policy.py` (từ điển mapping)
</read_first>
<action>
Tạo bài test `services/aureus-signal/tests/test_strategy_choch_triggers.py`.
Nội dung bài test:
1. Load nội dung raw list từ `d:\Aureus\data-test.json`. Mock thành các `SymbolState` / nến.
2. Tìm tay hoặc filter một số nến có signal tag CHOCH.
3. Chạy các nến này qua `event_policy.evaluate_ai_trigger_events(transient_signals)`.
4. Gọi `TemplateStrategy` cho các setup như `TREND_CONT_BULL` (đang thiết lập chờ `choch_up`). 
5. Thực hiện 2 vòng: Vòng 1 (Control - override xoá hết `context_filters`), Vòng 2 (Full Gating gốc).
6. Assert kiểm tra xem `strategy.evaluate_sequence(events)` có pass sinh ra order_plan không. 
Yêu cầu ban đầu script có thể rớt (Fail) để khẳng định đây đúng là bug hiện tại. Đặt assert expect trigger > 0 để lộ lỗi ra.
</action>
<acceptance_criteria>
- File `services/aureus-signal/tests/test_strategy_choch_triggers.py` được setup hoàn chỉnh.
- Lệnh `pytest services/aureus-signal/tests/test_strategy_choch_triggers.py` chạy qua nhưng lộ ra lỗi assert trigger count == 0. (Hoặc nếu đã pass thì có log giải thích rõ nguyên nhân trước kia).
- Script có sử dụng data từ file `data-test.json`.
</acceptance_criteria>
</step>

<step>
<task>Fix code Mapping/Tag Drift và xác nhận Trigger Test Pass</task>
<read_first>
- Output pytest lỗi từ bước 1.
- `services/aureus-signal/engine/strategies/seed_strategies.py`
- `services/aureus-signal/engine/event_policy.py`
</read_first>
<action>
Dựa trên console output của test ở Step 1, xác định xem tag trong `data-test.json` bắn ra là dạng gì (`choch`, `CHANGE_OF_CHARACTER_BULLISH` hay gì khác), và vì sao nó không khớp với sequence matcher chờ `choch_up`.
Chỉnh sửa một trong 2 file:
1. `services/aureus-signal/engine/event_policy.py` (thêm dictionary alias vào `_AI_TAG_TO_TRIGGER` dể normalize tag raw về mã chuẩn của event).
2. Hoặc cấu hình `tag` array trong `seed_strategies.py` để match đúng string sau normalize.
Sau khi sửa, update bài test ở Step 1 để assert chính xác rằng: Với data mẫu, vòng Control bắt buộc phải sinh Trade Intents (Trigger > 0).
</action>
<acceptance_criteria>
- File mapping / config sửa đúng string matcher dựa trên json dump log.
- Lệnh `pytest services/aureus-signal/tests/test_strategy_choch_triggers.py -v` hoàn toàn PASSED mà không báo thiếu event.
</acceptance_criteria>
</step>
