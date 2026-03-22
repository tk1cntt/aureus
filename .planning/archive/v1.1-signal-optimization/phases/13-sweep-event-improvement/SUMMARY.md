# Phase 13: Sweep Event Improvement - Summary

## Đã hoàn thành
1. **Status-based Sweep Contract:** Chuẩn hoá vòng đời sự kiện sweep thành các state ràng buộc logic: `PENDING`, `TOUCHED`, `SWEEP`, `BROKEN_PENDING`, `STOP_HUNT`, `DEAD` và emit chính xác qua `transient_signals`.
2. **Centralize AI Trigger Policy:** Loại bỏ toàn bộ các lệnh phát tín hiệu AI phân tán (`request_ai_update`) bên trong các file tín hiệu nhánh (`sweep.py`, `structure.py`).
3. **Event Policy Engine:** Khởi tạo `event_policy.py` hoạt động như bộ não trung tâm, map các domain events từ `transient_signals` sang mã lệnh AI Update và được orchestration trực tiếp tại hàm lõi `live_engine.py`.
4. Cơ chế đồng bộ dữ liệu tĩnh (`has_structural_event`) được làm rõ vai trò ranh giới, chỉ đóng vai trò Snapshot Gate.
