---
status: complete
date: 2026-06-17
quick_id: 260617-aya
description: "Kiểm tra gateway hiện tại xem tại sao kết nối đến k gửi data qua đc. Giả lập gửi dữ liệu để phân tích và xử lý lỗi nếu có"
---

## Tóm tắt

### Nguyên nhân gốc
Docker daemon trong WSL chưa khởi động (`inactive (dead)`), khiến container `aureus-gateway-dev` không chạy → không accept TCP connections trên port 5556.

### Kết quả test
Gateway hoạt động bình thường sau khi Docker được khởi động:

| Test | Message Type | Kết quả |
|------|-------------|---------|
| 1 | TICK (EURUSD) | Processed ✓ — Redis: `aureus:latest:EURUSD:tick` |
| 2 | CANDLE (GBPUSD) | Processed ✓ — Redis: `aureus:latest:GBPUSD:candle` |
| 3 | ORDER_OPENED (XAUUSD) | Published ✓ → `aureus:mt5:events` |

### Giải pháp khi gặp lại
```bash
wsl -d Aureus -u root -e bash -lc "service docker start"
```

### Files tạo
- `services/aureus-gateway/test-gateway.js` — Script test TCP gateway, gửi TICK/CANDLE/ORDER_OPENED mẫu
