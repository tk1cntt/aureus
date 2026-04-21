# Phase 47: verification-backfill-v1-5 - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves why these defaults were chosen.

**Date:** 2026-04-20T00:00:00Z
**Phase:** 47-verification-backfill-v1-5
**Mode:** discuss (codebase-first continuation)
**Areas discussed:** Verification scope, Evidence policy, Traceability consistency, Scope guardrails

---

## Verification scope

| Option | Description | Selected |
|--------|-------------|----------|
| Backfill only missing phases from audit (26, 28, 29, 31, 32, 33) | Đóng đúng orphan source theo audit hiện tại, tránh mở rộng scope | ✓ |
| Backfill toàn bộ phase v1.5 | Tốn effort lớn, không cần thiết cho gap đã định danh | |
| Chỉ sửa REQUIREMENTS traceability | Không đủ vì thiếu bằng chứng verifier-level | |

**Decision captured:** Backfill verification cho các phase thiếu artifact theo audit gap list.

---

## Requirement evidence policy

| Option | Description | Selected |
|--------|-------------|----------|
| Requirement-level table + file/test evidence | Rõ traceability và phù hợp gate verifier | ✓ |
| Narrative summary-only | Nhanh nhưng yếu bằng chứng, dễ tái-orphan | |
| Test-only evidence | Thiếu mapping tới requirement contract | |

**Decision captured:** Bắt buộc requirement-level mapping với evidence có thể truy vết.

---

## Verification status discipline

| Option | Description | Selected |
|--------|-------------|----------|
| `human_needed` khi thiếu runtime/manual proof | Trung thực mức tin cậy, không over-claim | ✓ |
| Vẫn mark `passed` nếu code/test nhìn ổn | Rủi ro false confidence, vi phạm gate | |
| Bỏ qua phần manual gate | Không phù hợp Nyquist/verification workflow | |

**Decision captured:** Không đủ bằng chứng tự động thì để `human_needed`, không ép `passed`.

---

## Scope guardrails

| Option | Description | Selected |
|--------|-------------|----------|
| Verification-only, defer integration/runtime fixes sang phase 48/49 | Đúng boundary phase 47 | ✓ |
| Kèm sửa integration ngay trong phase 47 | Scope creep, chồng lấn phase 48/49 | |
| Chỉ note gap, không cập nhật refs | Thiếu liên kết cho downstream planning | |

**Decision captured:** Giữ phase 47 là verification backfill; integration/runtime fixes deferred theo roadmap.

---

## Claude's Discretion

- Sắp xếp thứ tự xử lý các phase backfill để tối ưu thời gian đóng orphan requirements.
- Chọn mức chi tiết verification narrative miễn vẫn giữ đủ evidence theo requirement-level.

## Deferred Ideas

- Backtest/API wiring fix, qty contract fix, multi-symbol consumer fix chuyển phase 48/49.
- Nyquist re-audit closure tổng thể chuyển phase 50.
