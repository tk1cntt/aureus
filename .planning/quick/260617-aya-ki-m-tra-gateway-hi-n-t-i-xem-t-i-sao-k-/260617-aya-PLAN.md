---
description: "Kiểm tra gateway hiện tại xem tại sao kết nối đến k gửi data qua đc. Giả lập gửi dữ liệu để phân tích và xử lý lỗi nếu có"
date: 2026-06-17
status: pending
---

## Mục tiêu
Xác định nguyên nhân gateway không nhận được data và tạo giả lập để debug.

## Phân tích sơ bộ
Gateway nằm tại `stable/FenixAI_tradingBot/api/src/server.ts`:
- Socket.IO server (lines 108-131) lắng nghe: `subscribe:market`, `subscribe:agents`, `subscribe:system`
- Server emit: `price:update`, `agent:reasoning`, `system:metrics`, etc.
- Port: 3001 (mặc định)
- CORS: `http://localhost:5173`

## Plan

### Task 1: Kiểm tra server status
**Files:** Tạo script `test-gateway-status.js`
**Action:** 
- Ping `/health` endpoint để xác nhận server đang chạy
- Log response code và latency
**Verify:** Server trả về 200 OK với JSON status
**Done:** Xác nhận server đang hoạt động

### Task 2: Tạo Socket.IO test client
**Files:** Tạo script `test-socket-client.js`
**Action:**
- Kết nối đến `ws://localhost:3001`
- Đăng ký subscribe events
- Gửi data mẫu (market data)
- Log chi tiết: connect, subscribe, emit, response
- Bắt các lỗi: connection error, timeout, disconnect
**Verify:** 
- Client kết nối thành công
- Nhận được events từ server
- Gửi data thành công
**Done:** Xác định lỗi kết nối hoặc data transfer

### Task 3: Phân tích và đề xuất fix
**Files:** Cập nhật `SUMMARY.md`
**Action:**
- Tổng hợp logs từ Task 1 & 2
- Xác định nguyên nhân: server down, CORS, firewall, logic error
- Đề xuất fix nếu cần
**Verify:** Báo cáo rõ ràng nguyên nhân và giải pháp
**Done:** Hoàn thành phân tích
