# Phase 45: h-tr-x-ly-song-song-signal-strategy-cho-nhi-u-symbol-m-t- - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-18
**Phase:** 45-h-tr-x-ly-song-song-signal-strategy-cho-nhi-u-symbol-m-t-
**Areas discussed:** Mô hình song song, Thứ tự & nhất quán, Cô lập lỗi & nghẽn, Rollout an toàn

---

## Folded Todos

| Option | Description | Selected |
|--------|-------------|----------|
| Investigate missing OB events | Liên quan pipeline signal khi chạy nhiều symbol song song | |
| Remove market_regime use htf_trend | Cleanup logic tín hiệu | |

**User's choice:** Không fold todo nào; chỉ tập trung song song signal/strategy đa symbol.
**Notes:** User muốn giữ scope phase 45 thật gọn, không trộn cleanup logic khác.

---

## Mô hình song song

| Option | Description | Selected |
|--------|-------------|----------|
| Per-symbol worker | Mỗi symbol một worker/task riêng | ✓ |
| Worker pool chung | Pool xử lý job từ nhiều symbol | |
| Hybrid | Queue per-symbol + pool phụ | |

**User's choice:** Per-symbol worker.
**Notes:** Chọn hướng đơn giản, dễ cô lập, giảm rủi ro khi rollout.

### Mức độ áp dụng trong phase

| Option | Description | Selected |
|--------|-------------|----------|
| Signal + Strategy cùng lúc | Song song hóa cả signal và strategy ngay phase này | ✓ |
| Chỉ Signal trước | Strategy giữ gần hiện tại | |
| Chỉ Strategy trước | Signal giữ hiện tại | |

**User's choice:** Signal + Strategy cùng lúc.

### Concurrency mặc định

| Option | Description | Selected |
|--------|-------------|----------|
| Theo số symbol active | 1 worker/symbol | ✓ |
| Giới hạn cứng N worker | Trần cố định | |
| Auto theo CPU core | Scale theo core | |

**User's choice:** Theo số symbol active.

### Chính sách quá tải

| Option | Description | Selected |
|--------|-------------|----------|
| Ưu tiên độ đúng, xếp hàng | Không drop event/candle | ✓ |
| Ưu tiên độ trễ, drop cũ | Giữ realtime | |
| Theo symbol priority | Symbol quan trọng ưu tiên | |

**User's choice:** Ưu tiên độ đúng, chậm thì xếp hàng.

---

## Thứ tự & nhất quán

### Ordering trong mỗi symbol

| Option | Description | Selected |
|--------|-------------|----------|
| FIFO strict theo candle t | Không vượt mặt trong cùng symbol | ✓ |
| Cho phép reorder nhẹ | Tăng throughput | |
| Theo watermark thời gian | Chốt theo cửa sổ | |

**User's choice:** FIFO strict theo candle t.

### Out-of-order candle

| Option | Description | Selected |
|--------|-------------|----------|
| Reorder ngắn rồi fallback recalc | Chờ reorder trong cửa sổ ngắn | |
| Bỏ candle trễ | Không reorder | ✓ |
| Xử lý theo arrival order | Không kiểm soát thứ tự thời gian | |

**User's choice:** Bỏ candle trễ.

### Ràng buộc strategy với snapshot

| Option | Description | Selected |
|--------|-------------|----------|
| Bắt buộc cùng candle snapshot | Strict consistency | ✓ |
| Dùng snapshot gần nhất | Nới lỏng để giảm chờ | |
| Config per strategy | Linh hoạt theo strategy | |

**User's choice:** Bắt buộc cùng candle snapshot.

### Idempotency guard

| Option | Description | Selected |
|--------|-------------|----------|
| trace_id strict per symbol+candle | Chống duplicate trigger/order chặt | ✓ |
| Guard ở tầng order | Trigger có thể trùng | |
| Guard mềm timeout | Chống trùng tạm thời | |

**User's choice:** trace_id strict per symbol+candle.

---

## Cô lập lỗi & nghẽn

### Runtime failure theo symbol

| Option | Description | Selected |
|--------|-------------|----------|
| Circuit-breaker riêng symbol | Symbol lỗi tự tách ra | ✓ |
| Dừng toàn engine | 1 lỗi dừng tất cả | |
| Bỏ qua lỗi chạy tiếp | Chỉ log lỗi | |

**User's choice:** Circuit-breaker riêng symbol.

### Backlog threshold

| Option | Description | Selected |
|--------|-------------|----------|
| Ngưỡng backlog per-symbol + cảnh báo | Theo dõi và xử lý riêng từng symbol | ✓ |
| Ngưỡng backlog toàn cục | Một ngưỡng chung | |
| Không đặt ngưỡng cứng | Chỉ giám sát | |

**User's choice:** Ngưỡng backlog per-symbol + cảnh báo.

---

## Rollout an toàn

### Chiến lược rollout

| Option | Description | Selected |
|--------|-------------|----------|
| Shadow -> Canary -> Full | Triển khai theo nhiều lớp an toàn | ✓ |
| Canary trực tiếp | Bỏ shadow | |
| Full một lần | Triển khai toàn bộ ngay | |

**User's choice:** Shadow -> Canary -> Full.

### Điều kiện rollback

| Option | Description | Selected |
|--------|-------------|----------|
| Rollback tự động theo SLO per-symbol | Vi phạm SLO liên tiếp thì hạ cấp symbol đó | ✓ |
| Rollback thủ công | Vận hành quyết định | |
| Chỉ cảnh báo | Không tự rollback | |

**User's choice:** Rollback tự động theo SLO per-symbol.

---

## Claude's Discretion

- Giá trị ngưỡng SLO chi tiết và hysteresis cụ thể.
- Thiết kế chi tiết metric/log cho quan sát vận hành.

## Deferred Ideas

- Todo điều tra missing OB events (defer khỏi phase 45).
- Todo remove market_regime use htf_trend (defer khỏi phase 45).