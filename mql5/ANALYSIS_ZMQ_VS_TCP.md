# Phân tích Kỹ thuật: ZMQ vs. Native TCP Sockets

Tài liệu này phân tích sự khác biệt giữa việc sử dụng ZeroMQ (ZMQ) và Native TCP Sockets (MQL5) trong bối cảnh truyền tải dữ liệu từ MetaTrader 5 đến Aureus Gateway.

## 1. Hiệu năng (Latency < 100ms) ✅

Cả ZMQ và Native TCP đều hoàn toàn đáp ứng được yêu cầu latency < 100ms.

| Tiêu chí | ZMQ (Library) | Native TCP (MQL5) |
| :--- | :--- | :--- |
| **Protocol Overhead** | Cao hơn (ZMTP framing) | Rất thấp (Plain JSON + `\n`) |
| **I/O Model** | Background Thread (Asynchronous) | Synchronous (Blocking Send) |
| **Latency** | < 5ms (Local) | < 2ms (Local) |

**Phân tích:**
- Mặc dù ZMQ có background thread để tối ưu I/O, nhưng đối với 1 symbol (XAUUSD) trên 1 chart, tần suất tick tối đa thường là vài chục tick/giây. Ổ tốc độ này, Native TCP thực tế nhanh hơn một chút do không có bộ máy protocol phức tạp bên trên.
- Nút thắt cổ chai về latency thường nằm ở **MT5 `OnCalculate` loop** hoặc **Gateway processing**, chứ không phải ở protocol vận chuyển.

---

## 2. Rủi ro mất dữ liệu (Data Loss) ⚠️

Đây là điểm khác biệt lớn nhất về triết lý vận hành.

### ZMQ (Reliability Model)
- **Cơ chế:** ZMQ PUSH socket có bộ đệm (Queue) nội bộ. Nếu Receiver (Gateway) bị sập, PUSH socket sẽ lưu trữ message trong bộ nhớ đến khi đầy (HWM - High Water Mark).
- **Rủi ro:** Nếu MT5 bị crash hoặc Indicator bị gỡ trước khi Gateway kịp nhận dữ liệu, toàn bộ hàng đợi trong bộ nhớ sẽ **mất sạch**.

### Native TCP + Aureus Backfill (Aureus Model)
- **Cơ chế:** Nếu kết nối TCP lỗi, message hiện tại bị bỏ qua ngay lập tức nhưng Indicator chuyển sang trạng thái `Disconnected`. Ngay khi reconnect, hệ thống sử dụng **Backfill logic**.
- **Ưu điểm:** Backfill lấy dữ liệu từ **Historical Database của MT5** (vốn được MT5 tự động sync với Server sàn qua giao thức riêng). Điều này đảm bảo tính toàn vẹn dữ liệu cao hơn nhiều so với việc chỉ rely vào memory queue của ZMQ.
- **Check dây mạng (5 phút):** Trong 5 phút đó, MT5 Server vẫn ghi nhận nến M1. Khi reconnect, AureusIndicator sẽ dùng `CopyRates()` để bốc toàn bộ 5 nến đó gửi bù sang Gateway qua message `BACKFILL`.

---

## 3. Tại sao chọn Native TCP cho MT5? 🛠️

Việc chọn Native TCP thay cho ZMQ trong dự án Aureus mang tính chiến lược về mặt triển khai (Deployment):

1. **Zero Dependencies:** ZMQ yêu cầu 2 file DLL (`libzmq.dll`, `libsodium.dll`) phải được copy vào đúng thư mục `Libraries` và người dùng phải bật "Allow DLL imports". Điều này thường gây lỗi cho người dùng cuối (MT5 sandbox restrictions). Native TCP chạy trực tiếp trên file `.ex5`.
2. **Khả năng kiểm soát:** Chúng ta chủ động implement logic Reconnect và Backfill ngay trong code MQL5 thay vì lệ thuộc vào cơ chế "đen" bên trong ZMQ.
3. **Gateway Flexibility:** Gateway mới hỗ trợ cả hai. Nếu bạn muốn dùng ZMQ cho hệ thống khác, port 5555 vẫn mở. Nhưng với MT5, port 5556 (TCP) mang lại sự ổn định và dễ cài đặt nhất.

## 4. So sánh chi tiết tính năng

| Tính năng | ZeroMQ (PUSH/PULL) | Native TCP + Backfill |
| :--- | :--- | :--- |
| **Framing** | Tự động (Message-based) | Thủ công (Newline-delimited `\n`) |
| **Auto-Reconnect** | Có (trong library) | Có (trong `AureusSocketLib.mqh`) |
| **Buffering** | RAM-based (Dễ mất) | Disk-based (qua MT5 History) |
| **E2E Reliability** | Tốt cho uptime cao | Tối ưu cho môi trường mạng không ổn định |

## Kết luận
Việc thay thế ZMQ bằng Native TCP không những **không làm giảm performance** mà còn **tăng độ bền vững** của hệ thống thông qua cơ chế Backfill chủ động. 

Mọi yêu cầu về latency < 100ms và tính toàn vẹn dữ liệu sau khi reconnect (dây mạng rút 5 phút) đều được đảm bảo bằng logic xử lý nến thiếu (Gap analysis) trong file `AureusProvider.mq5`.
