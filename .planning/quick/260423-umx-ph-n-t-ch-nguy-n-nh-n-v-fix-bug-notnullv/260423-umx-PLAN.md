---
plan_id: 260423-umx
type: quick
objective: "Phân tích và fix lỗi NotNullViolation timeframe khi on_order_opened insert vào aureus_trade_signal_snapshots"
scope: "services/aureus-trader/journal.py và tests pipeline liên quan snapshot/evaluation"
autonomous: true
---

<objective>
Tái hiện chính xác lỗi `asyncpg.exceptions.NotNullViolationError: null value in column "timeframe" of relation "aureus_trade_signal_snapshots"`, sau đó fix tối thiểu ngay tại luồng `on_order_opened` để không còn insert `timeframe=NULL`.

Purpose: Chặn lỗi ghi snapshot làm fail journal pipeline khi ORDER_OPENED thiếu/khuyết timeframe.
Output: Test đỏ tái hiện lỗi -> code fix nhỏ gọn -> test xanh + verify e2e với database thật.
</objective>

<context>
@D:/Aureus/CLAUDE.md
@D:/Aureus/.planning/STATE.md
@D:/Aureus/services/aureus-trader/journal.py
@D:/Aureus/services/aureus-trader/tests/test_signal_snapshot_pipeline.py
@D:/Aureus/services/aureus-trader/tests/test_evaluation_pipeline.py
@D:/Aureus/RUN_SERVICES.md
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Impact analysis bắt buộc + viết test tái hiện timeframe NULL</name>
  <files>D:/Aureus/services/aureus-trader/tests/test_signal_snapshot_pipeline.py</files>
  <behavior>
    - Test 1 (RED): Khi event ORDER_OPENED không có timeframe (và journal fallback cũng không cung cấp), insert snapshot phải từng gây lỗi NotNullViolation ở cột timeframe.
    - Test 2 (RED/contract): Sau fix mong muốn, timeframe phải được gán giá trị mặc định hợp lệ (ví dụ M1) trước khi insert snapshot.
  </behavior>
  <action>Trước khi sửa bất kỳ symbol nào trong `TradeJournalManager.on_order_opened` hoặc helper liên quan timeframe, bắt buộc chạy GitNexus impact analysis cho symbol đó (`gitnexus_impact({target: "on_order_opened", direction: "upstream"})` và helper nếu có chỉnh sửa), ghi rõ blast radius d=1/d=2. Sau đó bổ sung/chỉnh test để tái hiện đúng bug `timeframe=NULL` ở snapshot insert, tránh mở rộng phạm vi ngoài bug này.</action>
  <verify>
    <automated>pytest D:/Aureus/services/aureus-trader/tests/test_signal_snapshot_pipeline.py -k timeframe -x</automated>
  </verify>
  <done>Test thể hiện rõ lỗi gốc timeframe null ở snapshot path và định nghĩa được expected behavior sau fix.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Sửa tối thiểu trong on_order_opened để snapshot insert luôn có timeframe hợp lệ</name>
  <files>D:/Aureus/services/aureus-trader/journal.py, D:/Aureus/services/aureus-trader/tests/test_signal_snapshot_pipeline.py, D:/Aureus/services/aureus-trader/tests/test_evaluation_pipeline.py</files>
  <behavior>
    - Test 1 (GREEN): Event thiếu timeframe vẫn insert snapshot thành công với timeframe mặc định, không raise NotNullViolation.
    - Test 2 (GREEN): Luồng evaluation/snapshot hiện có không regress (bao gồm case đã default timeframe trước đó).
  </behavior>
  <action>Áp dụng fix tại đúng điểm build payload insert `aureus_trade_signal_snapshots` trong `on_order_opened`: chuẩn hóa fallback timeframe nhất quán (event -> journal -> default) và đảm bảo giá trị non-empty trước execute. Không refactor lan man, không đổi kiến trúc, chỉ chạm tối thiểu các dòng liên quan bug.</action>
  <verify>
    <automated>pytest D:/Aureus/services/aureus-trader/tests/test_signal_snapshot_pipeline.py D:/Aureus/services/aureus-trader/tests/test_evaluation_pipeline.py -x</automated>
  </verify>
  <done>Không còn đường insert snapshot với timeframe NULL; test pipeline liên quan pass.</done>
</task>

<task type="auto">
  <name>Task 3: Verify e2e với database thật theo yêu cầu CLAUDE.md</name>
  <files>D:/Aureus/RUN_SERVICES.md</files>
  <action>Dùng hướng dẫn trong RUN_SERVICES.md để khởi chạy môi trường DB/test service, chạy test e2e có ghi DB cho journal/snapshot path để xác nhận fix tạo data thành công và không phát sinh NotNullViolation với ORDER_OPENED thiếu timeframe.</action>
  <verify>
    <automated>pytest D:/Aureus/services/aureus-trader/tests/test_e2e_mt5_orders.py D:/Aureus/services/aureus-trader/tests/test_e2e_trader.py -x</automated>
  </verify>
  <done>Có bằng chứng e2e DB rằng snapshot insert thành công sau fix, không còn lỗi timeframe null.</done>
</task>

</tasks>

<verification>
- Đã có bước impact analysis bắt buộc trước edit symbol chính.
- TDD rõ ràng theo chu kỳ: tái hiện lỗi timeframe null (RED) -> sửa tối thiểu (GREEN).
- Có verify e2e với database thật theo CLAUDE.md.
</verification>

<success_criteria>
1. Không còn `NotNullViolationError` do `timeframe` null khi `on_order_opened` insert vào `aureus_trade_signal_snapshots`.
2. Bộ test snapshot/evaluation pipeline pass sau fix.
3. E2E test với database xác nhận dữ liệu snapshot được tạo thành công.
4. Phạm vi thay đổi tối thiểu, không refactor lan man ngoài bug timeframe.
</success_criteria>
