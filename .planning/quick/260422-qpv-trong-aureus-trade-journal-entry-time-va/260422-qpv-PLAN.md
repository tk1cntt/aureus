---
plan_id: 260422-qpv
type: quick
objective: "Bắt buộc dùng entry_time/exit_time từ dữ liệu order MT5 cho aureus_trade_journal, không fallback sang nguồn khác"
scope: "services/aureus-trader + test liên quan journal"
autonomous: true
---

<objective>
Đảm bảo dữ liệu thời gian vào/ra lệnh trong `aureus_trade_journal` phản ánh đúng order từ MT5, không bị lệch do cơ chế fallback.

Purpose: Loại bỏ sai lệch dữ liệu journal ảnh hưởng đánh giá chiến lược và báo cáo.
Output: Logic journal chỉ nhận `entry_time`/`exit_time` từ payload order MT5 + test khóa hành vi này.
</objective>

<context>
@D:/Aureus/CLAUDE.md
@D:/Aureus/.planning/STATE.md
@D:/Aureus/services/aureus-trader/journal.py
@D:/Aureus/services/aureus-trader/tests/test_evaluation_pipeline.py
@D:/Aureus/services/aureus-trader/tests/test_signal_snapshot_pipeline.py
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Khóa contract thời gian journal theo order MT5</name>
  <files>D:/Aureus/services/aureus-trader/tests/test_evaluation_pipeline.py, D:/Aureus/services/aureus-trader/tests/test_signal_snapshot_pipeline.py</files>
  <behavior>
    - Test 1: Khi order MT5 có `entry_time` và `exit_time`, journal phải lưu đúng 2 giá trị này.
    - Test 2: Khi thiếu thời gian MT5, pipeline phải fail fast (raise/skip có log rõ), không được tự fallback sang giá trị khác.
  </behavior>
  <action>Thêm/chỉnh test để mô tả rõ invariant: `aureus_trade_journal.entry_time` và `exit_time` chỉ có nguồn từ order MT5. Cấm expectation theo kiểu fallback từ candle/signal timestamp.</action>
  <verify>
    <automated>pytest D:/Aureus/services/aureus-trader/tests/test_evaluation_pipeline.py D:/Aureus/services/aureus-trader/tests/test_signal_snapshot_pipeline.py -x</automated>
  </verify>
  <done>Có test thất bại trước khi sửa logic, và test mô tả rõ rule “MT5-only timestamp”.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Sửa logic journal để loại bỏ fallback thời gian</name>
  <files>D:/Aureus/services/aureus-trader/journal.py</files>
  <behavior>
    - Test 1: Journal mapping dùng trực tiếp `entry_time`/`exit_time` từ order MT5.
    - Test 2: Không tồn tại nhánh fallback sang timestamp khác cho 2 field này.
  </behavior>
  <action>Chỉnh phần mapping/build record trong `journal.py` để chỉ đọc timestamp từ dữ liệu order MT5, bỏ toàn bộ fallback gây sai lệch. Nếu dữ liệu MT5 thiếu thì xử lý theo fail-fast path đã định ở test (không synthesize thời gian giả).</action>
  <verify>
    <automated>pytest D:/Aureus/services/aureus-trader/tests/test_evaluation_pipeline.py D:/Aureus/services/aureus-trader/tests/test_signal_snapshot_pipeline.py -x</automated>
  </verify>
  <done>Mọi test ở Task 1 pass; không còn đường code fallback cho entry/exit time trong journal path.</done>
</task>

<task type="auto">
  <name>Task 3: Hồi quy tối thiểu pipeline trader liên quan journal</name>
  <files>D:/Aureus/services/aureus-trader/tests/conftest.py</files>
  <action>Chạy bộ test trader liên quan pipeline/journal để xác nhận thay đổi không làm sai đường xử lý hiện có. Chỉ chỉnh fixture trong `conftest.py` nếu cần để đồng nhất dữ liệu order MT5 bắt buộc có timestamp.</action>
  <verify>
    <automated>pytest D:/Aureus/services/aureus-trader/tests/test_evaluation_pipeline.py D:/Aureus/services/aureus-trader/tests/test_signal_snapshot_migration.py D:/Aureus/services/aureus-trader/tests/test_signal_snapshot_pipeline.py -x</automated>
  </verify>
  <done>Regression pass, journal time semantics nhất quán MT5 source-only.</done>
</task>

</tasks>

<verification>
- Tất cả test pipeline/journal liên quan pass.
- Không còn hành vi fallback timestamp cho `entry_time`/`exit_time` trong journal logic.
</verification>

<success_criteria>
1. `aureus_trade_journal.entry_time` và `exit_time` luôn truy vết được về order MT5.
2. Trường hợp thiếu timestamp MT5 không tạo dữ liệu thời gian thay thế gây sai lệch.
3. Regression test trader liên quan journal đều pass.
</success_criteria>
