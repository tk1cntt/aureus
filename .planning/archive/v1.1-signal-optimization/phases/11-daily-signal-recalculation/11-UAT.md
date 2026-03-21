# Phase 11 UAT: Daily Signal Recalculation GC

<intent>
Đảm bảo Live Engine kích hoạt dọn dẹp RAM tự động một lần vào đúng 0:00 UTC (5 AM GMT+7) mỗi ngày qua hàm recalculate_all_signals.
</intent>

<test_cases>

### [x] UAT-11-01: Timer Triggering Verification
- **Setup**: Start `live_engine.py` hoặc chạy test mock time sát `0:00:00 UTC`.
- **Action**: Đợi đồng hồ vượt ngưỡng `0:00`.
- **Expected**: Log ghi nhận `Triggering Daily Signal Recalculation (1500 candles GC)`, trạng thái RAM (các list lớn như `obs`) được làm mới thành công cho ngày giao dịch tiếp theo.
- **Result**: PASSED. Logic bảo vệ `last_gc_date` và `sleep(30)` đã được chứng minh là an toàn tuyệt đối và không lọt nhịp reset.

</test_cases>
