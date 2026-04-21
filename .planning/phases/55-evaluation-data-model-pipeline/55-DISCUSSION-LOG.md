# Phase 55: Evaluation Data Model & Pipeline - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-21
**Phase:** 55-evaluation-data-model-pipeline
**Areas discussed:** Data model shape, Versioning & recompute, Idempotency & uniqueness, Pipeline boundaries

---

## Data model shape

| Option | Description | Selected |
|--------|-------------|----------|
| Hybrid core+JSONB | Core normalized columns + JSONB breakdown/context | |
| Fully normalized tables | Split full criterion/context tables now | |
| JSONB-first minimal | Mostly JSONB with minimal core columns | |
| Extend Trade Execution Journal | Reuse and extend existing Trade Execution Journal model | ✓ |

**User's choice:** Mở rộng từ Trade Execution Journal thay vì thiết kế cầu kỳ tách rời.
**Notes:** User phản hồi trực tiếp: “Có bảng Trade Execution Journal rồi sao không mở rộng ra để thêm data mà phải cầu kỳ vậy”.

---

## Versioning & recompute

| Option | Description | Selected |
|--------|-------------|----------|
| Immutable append-only | New version rows, keep history | |
| Overwrite latest only | Keep only newest state | |
| Dual mode | Configurable append/overwrite policy | |
| Journal-anchored policy | Chốt policy dựa trên cấu trúc Trade Execution Journal | ✓ |

**User's choice:** Chốt sau khi rà lại bảng Trade Execution Journal.
**Notes:** User yêu cầu: “Xử lý cần xem lại dựa trên bảng của Trade Execution Journal”.

---

## Idempotency & uniqueness

| Option | Description | Selected |
|--------|-------------|----------|
| Composite deterministic keys | Composite unique + payload hash idempotency | |
| Idempotency key only | Producer-provided key only | |
| Natural key only | Natural unique key only | |
| Journal-anchored keys | Key strategy bám theo Trade Execution Journal | ✓ |

**User's choice:** Chốt idempotency/uniqueness dựa trên bảng Trade Execution Journal.
**Notes:** User lặp lại định hướng nhất quán với versioning/recompute.

---

## Pipeline boundaries

| Option | Description | Selected |
|--------|-------------|----------|
| Executor emits, pipeline persists | Executor emits; persistence layer handles DB flow | |
| Persist trực tiếp trong executor | Compute + persist in executor | |
| Batch-only offline pipeline | Persist later via batch jobs | |
| Trigger after MT5 success | Start DB persist after MT5 order send success | ✓ |

**User's choice:** Bắt đầu xử lý lưu DB sau khi gửi lệnh MT5 thành công.
**Notes:** User statement: “Sau khi gửi lệnh lên MT5 thành công thì sẽ bắt đầu xử lý lưu thông tin vào database”.

---

## Claude's Discretion

- Mapping chi tiết execution journal fields sang evaluation schema.
- Lựa chọn DDL/index constraints cụ thể miễn giữ đúng định hướng user đã khóa.

## Deferred Ideas

None.
