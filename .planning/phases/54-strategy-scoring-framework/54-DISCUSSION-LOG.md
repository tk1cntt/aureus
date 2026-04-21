# Phase 54: Strategy Scoring Framework - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-21T09:53:14+07:00
**Phase:** 54-strategy-scoring-framework
**Areas discussed:** Criteria formula, Score versioning, Granularity outputs, Breakdown persistence

---

## Criteria formula

| Option | Description | Selected |
|--------|-------------|----------|
| Two-stage gate + weighted sum | Gate chất lượng trước, sau đó weighted-sum đa tiêu chí; cân bằng auditability và độ chắc chắn đầu vào | ✓ |
| Weighted sum thuần | Đơn giản nhất, dễ triển khai nhưng không có lớp chặn quality trước | |
| Multiplicative/geometric | Phạt mạnh khi 1 criterion thấp, nhưng khó tuning và dễ bất ổn | |
| Rule-based hybrid | Linh hoạt domain, nhưng dễ phình complexity và khó chuẩn hóa | |

**User's choice:** 1A (Two-stage gate + weighted sum)
**Notes:** Người dùng yêu cầu quy trình tư vấn 4 bước (neutral listing, attribute mapping, contextual recommendation, adversarial mode) trước khi khóa quyết định.

---

## Score versioning

| Option | Description | Selected |
|--------|-------------|----------|
| Semantic version + immutable weights snapshot | Rõ ràng khi audit và tái lập kết quả giữa các lần compute/recompute | ✓ |
| Timestamp version | Dễ tạo nhưng khó đọc nghĩa nghiệp vụ version | |
| Hash-only version | Chặt về kỹ thuật nhưng khó giao tiếp cho vận hành/phân tích | |
| Semantic + hash | Đầy đủ nhưng tăng độ phức tạp quản lý version | |

**User's choice:** 2A (Semantic version + immutable weights snapshot)
**Notes:** Yêu cầu nhấn mạnh traceability và reproducibility.

---

## Granularity outputs

| Option | Description | Selected |
|--------|-------------|----------|
| strategy/symbol/timeframe | Aggregate đa chiều, phù hợp mục tiêu report phase sau | ✓ |
| strategy only | Đơn giản nhưng thiếu chiều phân tích theo symbol/timeframe | |
| strategy + symbol | Bỏ mất chiều timeframe | |
| strategy + timeframe | Bỏ mất chiều symbol | |

**User's choice:** 3A (strategy/symbol/timeframe)
**Notes:** Cần đầu ra có thể dùng trực tiếp cho reporting engine phase 56.

---

## Breakdown persistence

| Option | Description | Selected |
|--------|-------------|----------|
| JSON breakdown + normalization metadata + missing policy explicit | Đủ thông tin audit/giải thích và xử lý null/missing rõ ràng | ✓ |
| Flattened columns only | Truy vấn nhanh nhưng khó mở rộng tiêu chí | |
| JSON minimal | Linh hoạt nhưng thiếu metadata để tái lập đầy đủ | |
| Hybrid JSON + selected columns | Cân bằng nhưng cần thêm quy ước mapping | |

**User's choice:** 4A (JSON breakdown + normalization metadata + missing policy explicit)
**Notes:** Người dùng muốn cập nhật ngay vào tài liệu để làm baseline thực thi + kiểm thử.

---

## Claude's Discretion

- Chi tiết công thức normalize từng criterion.
- Precision/rounding policy cụ thể miễn nhất quán với contract đã khóa.

## Deferred Ideas

- Không có deferred idea ngoài scope trong phiên thảo luận này.
