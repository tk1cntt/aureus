---
phase: quick-260424-qkt
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - services/aureus-trader/journal.py
  - services/aureus-trader/tests/test_signal_snapshot_pipeline.py
autonomous: true
requirements:
  - QUICK-260424-QKT
---

<objective>
Mapping lại đầy đủ dữ liệu snapshot trong `_build_signal_snapshot_columns`: fix CISD text `BULLISH/BEARISH` và bổ sung mapping các trường `atr`, `vol_sma_20`, `session`, `candle_color_*` từ các nguồn snapshot/event hiện có.
</objective>

<tasks>
<task type="auto" tdd="true">
  <name>Task 1: Viết regression tests cho CISD + field bổ sung</name>
  <files>services/aureus-trader/tests/test_signal_snapshot_pipeline.py</files>
  <action>Thêm test chứng minh `BULLISH/BEARISH` map đúng về integer và snapshot có đủ atr/vol/session/candle_color thì insert args không còn null.</action>
  <verify><automated>pytest services/aureus-trader/tests/test_signal_snapshot_pipeline.py -k "cisd or snapshot_mapping" -x</automated></verify>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Sửa mapping trong journal</name>
  <files>services/aureus-trader/journal.py</files>
  <action>Mở rộng normalize polarity cho cả `BULLISH/BEARISH`; bổ sung fallback key aliases cho atr, vol_sma_20, session, candle_color_* và CISD trong `_build_signal_snapshot_columns`.</action>
  <verify><automated>pytest services/aureus-trader/tests/test_signal_snapshot_pipeline.py -k "cisd or snapshot_mapping" -x</automated></verify>
</task>

<task type="auto">
  <name>Task 3: Verify e2e DB cho signal snapshot</name>
  <files>services/aureus-trader/tests/test_signal_snapshot_pipeline.py</files>
  <action>Chạy e2e test DB thật để xác nhận persistence các cột target thành công sau chỉnh sửa.</action>
  <verify><automated>pytest services/aureus-trader/tests/test_signal_snapshot_pipeline.py -k "e2e_db_real" -x</automated></verify>
</task>
</tasks>
