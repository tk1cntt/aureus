# Phase 15.17: Decouple Strategy Engine - Research

**Researched:** 2026-04-01
**Domain:** Python asyncio, Redis Streams (Microservices)
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01: Khối 1 (aureus-signal-aggregator)**
  - Đọc stream giá, tính toán Indicators và Structure.
  - State Persistence (Lưu trữ): Vẫn phải giữ `aureus:state` và ghi đè file JSON trạng thái (`aureus:state:{symbol}`) lên Redis cho Dashboard đọc.
  - Snapshot & GC (TimescaleDB): Lưu Snapshot vĩnh viễn xuống TimescaleDB (có điều kiện) để khôi phục khi restart, và quản lý các tracking_vars.
  - Sau đó xuất ra một Stream mới chứa signal cho mỗi symbol riêng biệt (ví dụ: `aureus:stream:XAUUSD:signals`).

- **D-02: Khối 2 (aureus-strategy-executor)**
  - Tách đoạn mã từ dòng 692 trở xuống trong `live_engine.py`, chạy hoàn toàn bất đồng bộ và chỉ lắng nghe stream signal (không màng tới việc build dữ liệu nến).
  - **Strategy Evaluation (`evaluate_all`)**: Duyệt qua file cấu hình Strategy (`TemplateStrategy`), đối chiếu mô hình (`sequence matcher`) với mảng `log_signal_normalize` của nến hiện tại để tìm kiếm cơ hội giao dịch (Intents).
  - **Observability & Metadata Enrichment**: Đóng gói version (Spec, Engine, Strategy version), capture dữ liệu Snapshot lúc ra quyết định (tránh thay đổi sau này), và phát log Rejection ra stream `aureus:stream:{symbol}:orders` (lý do bị chặn).
  - **Trade/Order Simulation & AI Trigger**: Giả lập chạy SL/TP (`trade_manager.update_orders`), hiện thực hóa lệnh Trade mới (`process_triggers`). Nếu Strategy có cờ yêu cầu AI phê duyệt, đẩy task vào hàng đợi `ai_queue`.

### the agent's Discretion
None

### Deferred Ideas (OUT OF SCOPE)
None
</user_constraints>

## Summary

Phase này tập trung vào việc refactoring logic monolithic hiện tại của `Aureus Signal Engine` thành kiến trúc 2 microservices giao tiếp thông qua Redis Streams. Không có framework hoặc thư viện mới nào được yêu cầu ngoài `redis-py` và `asyncio` đang được sử dụng.
Trọng tâm là thiết kế contract chuẩn cho stream `aureus:stream:{symbol}:signals` đảm bảo Khối 2 có đủ dữ liệu (snapshot của signals, tracking_vars cần thiết) để chạy `evaluate_all` độc lập mà không cần phải query ngược lại DB.

**Primary recommendation:** Thiết kế payload của signal stream phải chứa JSON serialized state của nến hiện tại (hoặc những properties mấu chốt) để Khối 2 có thể reconstruct lại bối cảnh đánh giá chiến lược một cách stateless.

## Architecture Patterns

### Recommended Project Structure
Thay vì một `live_engine.py` duy nhất, chúng ta chia tách entrypoint hoặc class xử lý:
```
services/aureus-signal/engine/
├── aggregator/
│   └── live_aggregator.py    # Khối 1: Đọc nến -> tính Indicators -> emit Signals
└── executor/
    └── strategy_executor.py  # Khối 2: Đọc Signals -> evaluate_all -> Process Trades
```

### Async Redis Consumer Groups Pattern
**What:** Sử dụng `XREADGROUP` để đảm bảo tín hiệu không bị mất nếu Khối 2 restart.
**When to use:** Ngay lập tức. Khối 2 sẽ tham gia vào consumer group của `aureus:stream:{symbol}:signals`.

## Runtime State Inventory

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | Redis Streams hiện hành (`aureus:stream:XAUUSD:candle`). | Tạo thêm Stream mới `aureus:stream:{symbol}:signals`. |
| Live service config | Docker Compose configs cho worker. | Khai báo service mới hoặc cập nhật startup command cho worker 2. |
| OS-registered state | None | None |
| Secrets/env vars | Các REDIS_URL và cấu hình kết nối DB. | Dùng chung cho cả 2 khối. |
| Build artifacts | None | None |

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest |
| Config file | `pytest.ini` (nếu có) |
| Quick run command | `pytest "services/aureus-signal/tests" --lf -v` |
| Full suite command | `pytest "services/aureus-signal/tests" -v` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PARITY-01 | Khối 1 xuất Signal Stream chính xác | unit/integration | `pytest tests/test_aggregator.py` | ❌ Wave 0 |
| PARITY-02 | Khối 2 đọc Signal Stream và evaluate chính xác | unit/integration | `pytest tests/test_executor.py` | ❌ Wave 0 |
| PARITY-03 | Kết quả trade intents không bị đổi sau khi tách | integration | `pytest tests/test_signal_integration.py` | ✅ |

### Sampling Rate
- **Per task commit:** Run individual test file with `-x`.
- **Per wave merge:** Run full suite.
- **Phase gate:** Full suite green before `/gsd-verify-work`.

### Wave 0 Gaps
- [ ] `services/aureus-signal/tests/test_aggregator_stream.py` — Test Khối 1 đẩy tín hiệu đúng format.
- [ ] `services/aureus-signal/tests/test_executor_consumer.py` — Test Khối 2 consume tín hiệu và sinh intents.

## Metadata

**Confidence breakdown:**
- Architecture: HIGH - Dựa trên kiến trúc event-driven hiện tại của hệ thống.
- Pitfalls: HIGH - Xác định rõ rủi ro race condition nếu payload thiếu context.
