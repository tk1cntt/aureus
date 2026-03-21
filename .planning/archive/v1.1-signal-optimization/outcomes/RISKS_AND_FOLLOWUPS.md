# Risks & Follow-ups

## Known limitations
- Python 3.10 đang được dùng với tính năng cơ bản. Với các cấu trúc cực lớn, Array của Numpy có thể phát sinh thêm delay so với Numba/Cython.
- Các Box màu xám trên UI Dashboard đang tải từ Snapshot M1 chứ không phải tick-by-tick của Live Engine. Dữ liệu chưa đủ độ sắc nét Microsecond.

## Technical debt
- Lời gọi Database Async đôi lúc chưa Handle triệt để Network Timeout nếu Postgres sập. 
- Mới chỉ Refill 1500 candles. Có thể xuất hiện độ vênh mỏng bé nếu Strategy đòi hỏi dữ liệu quá 2 ngày.

## Next actions cho Mốc tới
- Cân nhắc sử dụng Rust hoặc Cython cho `sweep_targets`.
- Tăng cường AI Analysis layer để xử lý đa luồng thay vì Batch theo Candle.
