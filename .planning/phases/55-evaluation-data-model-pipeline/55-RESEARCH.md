# Phase 55: Evaluation Data Model & Pipeline - Research

**Researched:** 2026-04-21
**Domain:** Evaluation persistence schema + compute/persist/backfill pipeline on top of Trade Execution Journal
**Confidence:** MEDIUM

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
### Data model strategy
- **D-01:** Ưu tiên tận dụng và mở rộng từ **Trade Execution Journal** hiện có thay vì tạo data model rời hoàn toàn mới.
- **D-02:** Evaluation schema phải thiết kế bám theo khóa/quan hệ hiện tại của Trade Execution Journal để giảm độ cầu kỳ migration và giữ traceability theo vòng đời lệnh.

### Versioning & recompute
- **D-03:** Chính sách versioning/recompute sẽ được khóa dựa trên cấu trúc thực tế của Trade Execution Journal (trade identity, lifecycle fields, timestamps) trước khi chốt DDL chi tiết.
- **D-04:** Recompute phải giữ được lịch sử version phục vụ truy vết, nhưng cách biểu diễn (append/version rows vs extension pattern) phải tương thích với Journal schema hiện hữu.

### Idempotency & uniqueness
- **D-05:** Guardrails idempotency/uniqueness cho evaluation pipeline phải dựa trên khóa tự nhiên và ràng buộc đã có trong Trade Execution Journal.
- **D-06:** Tránh tạo cơ chế idempotency tách rời không map được về Journal records; mọi chống duplicate phải truy hồi được về execution journal lineage.

### Pipeline trigger & boundary
- **D-07:** Điểm trigger persist evaluation bắt đầu **sau khi gửi lệnh lên MT5 thành công**.
- **D-08:** Pipeline phải ghi nhận evaluation data vào DB từ thời điểm lệnh được xác nhận thành công, rồi tiếp tục cập nhật/bổ sung theo lifecycle dữ liệu liên quan nếu cần.

### Claude's Discretion
- Cách cụ thể để map Trade Execution Journal fields sang evaluation schema trung gian/final.
- Cấu trúc migration chi tiết (naming/indexing/constraint expression) miễn tuân thủ các quyết định D-01→D-08.
- Cơ chế orchestration cho recompute jobs (batch windowing/chunking) miễn không phá vỡ traceability với Journal.

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| EVAL-01 | Thiết kế schema DB chuẩn hóa cho dữ liệu đánh giá trade/strategy (score, breakdown, context, score_version, timestamp). | Đề xuất extension-table bám `aureus_trade_journal` + versioned rows + JSONB breakdown + typed core columns. |
| EVAL-02 | Pipeline ingestion/compute/persist đảm bảo mỗi trade có evaluation record đầy đủ và truy vết được nguồn dữ liệu. | Map trigger điểm `ORDER_OPENED` hiện hữu, enrich từ `strategy_executor`, lineage qua `trace_id`/`ticket`/`strategy/symbol/timeframe`. |
| EVAL-03 | Backfill/recompute pipeline cho phép tính lại điểm khi thay đổi scoring weights/version mà không mất lịch sử phiên bản cũ. | Append-only per `score_version`, trạng thái `is_current`/`computed_at`, chunked recompute theo time window + idempotent upsert key. |
| EVAL-04 | Data quality guards cho evaluation pipeline (idempotency key, uniqueness, null/constraint checks) để tránh duplicate/sai lệch. | Unique composite key, NOT NULL/check constraints, deterministic idempotency key, và validation tests từ pattern journal hiện có. |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- Mọi trao đổi phải dùng tiếng Việt. [VERIFIED: D:/Aureus/CLAUDE.md]
- Khi command lỗi, tham khảo RUN_SERVICES.md. [VERIFIED: D:/Aureus/CLAUDE.md]
- Ưu tiên đơn giản, thay đổi tối thiểu đúng scope; không thêm tính năng ngoài yêu cầu. [VERIFIED: D:/Aureus/CLAUDE.md]
- Với task sửa code: phải chạy GitNexus impact trước khi sửa symbol và detect_changes trước commit. [VERIFIED: D:/Aureus/CLAUDE.md]
- Phase name phải tiếng Anh, ngắn gọn; tạo phase theo thứ tự đang làm. [VERIFIED: D:/Aureus/CLAUDE.md]

## Summary

Phase 55 nên được thiết kế như lớp **evaluation persistence mở rộng trực tiếp trên `aureus_trade_journal`**, không tạo mô hình tách rời, vì context đã khóa D-01/D-02 và code hiện tại đã có lifecycle/traceability tốt qua `trace_id` + `ORDER_OPENED/ORDER_CLOSED`. [VERIFIED: D:/Aureus/.planning/phases/55-evaluation-data-model-pipeline/55-CONTEXT.md] [VERIFIED: D:/Aureus/services/aureus-trader/journal.py] [VERIFIED: D:/Aureus/services/aureus-trader/dispatcher.py]

Hiện scoring payload đã có `score_total`, `score_breakdown`, `score_version`, `weights_snapshot`, `missing_data_policy` từ `strategy_executor`, nhưng mới ở contract tạm (Phase 54 D-13), chưa có schema chuẩn để persist/version/recompute. [VERIFIED: D:/Aureus/services/aureus-signal/engine/strategy_executor.py] [VERIFIED: D:/Aureus/.planning/phases/54-strategy-scoring-framework/54-CONTEXT.md]

Điểm quan trọng để plan tốt: phải tách rõ **code edit pipeline runtime** (ghi record khi order đã mở) và **data migration/recompute** (tạo record cho lịch sử hoặc version mới) theo EVAL-03, đồng thời guardrails cần ràng buộc uniqueness/idempotency dựa trên lineage của Journal thay vì key rời. [VERIFIED: D:/Aureus/.planning/REQUIREMENTS.md] [VERIFIED: D:/Aureus/.planning/phases/55-evaluation-data-model-pipeline/55-CONTEXT.md]

**Primary recommendation:** Dùng mô hình `evaluation_records` append-only theo `score_version` với khóa composite gắn chặt `aureus_trade_journal` (journal_id/trace_id/ticket + scope dimensions), trigger persist từ `ORDER_OPENED`, và recompute bằng batch idempotent. [VERIFIED: D:/Aureus/.planning/phases/55-evaluation-data-model-pipeline/55-CONTEXT.md] [ASSUMED]

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| PostgreSQL/TimescaleDB (existing) | In-use in project | Persist normalized evaluation records + constraints/indexes | Đã là DB chuẩn milestone v1.6 và journal đang nằm trên đó. [VERIFIED: D:/Aureus/.planning/STATE.md] [VERIFIED: D:/Aureus/services/aureus-db-writer/migrations/add_trade_journal.sql] |
| asyncpg | 0.31.0 | Async DB access cho pipeline write/recompute | Trader và signal stack đã dùng asyncpg; consistency với codebase hiện tại. [VERIFIED: D:/Aureus/services/aureus-signal/requirements.txt] [VERIFIED: D:/Aureus/services/aureus-trader/main.py] |
| Redis streams/pubsub | redis==7.2.0 client | Event trigger và async orchestration hiện hữu | Pipeline execution path hiện đã chạy qua Redis event streams. [VERIFIED: D:/Aureus/services/aureus-signal/requirements.txt] [VERIFIED: D:/Aureus/services/aureus-signal/engine/strategy_executor.py] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pydantic | 2.12.5 (signal), >=2.0.0 (trader) | Validate evaluation payload trước persist | Dùng khi formalize contract giữa scorer và persistence writer. [VERIFIED: D:/Aureus/services/aureus-signal/requirements.txt] [VERIFIED: D:/Aureus/services/aureus-trader/requirements.txt] |
| pytest | 9.0.2 (env) | Test data guards + pipeline behavior | Wave 0/phase gate cho EVAL-04 và recompute correctness. [VERIFIED: local env command output] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Extend existing journal-linked schema | Separate standalone evaluation datastore | Trái D-01/D-02, tăng migration + giảm traceability lineage. [VERIFIED: D:/Aureus/.planning/phases/55-evaluation-data-model-pipeline/55-CONTEXT.md] |
| asyncpg direct write | ORM layer (SQLAlchemy) | Có thể tăng abstraction nhưng không phải pattern hiện tại trong trader path. [VERIFIED: D:/Aureus/services/aureus-trader/main.py] [ASSUMED] |

**Installation:**
```bash
pip install asyncpg pydantic redis pytest
```
[VERIFIED: D:/Aureus/services/aureus-signal/requirements.txt] [VERIFIED: D:/Aureus/services/aureus-trader/requirements.txt]

## Architecture Patterns

### Recommended Project Structure
```text
services/
├── aureus-db-writer/
│   ├── migrations/             # DDL cho evaluation table/index/constraints
│   └── ...
├── aureus-trader/
│   ├── journal.py              # lifecycle source-of-truth của trade
│   ├── dispatcher.py           # ORDER_OPENED / ORDER_CLOSED integration points
│   └── ...
└── aureus-signal/
    └── engine/
       └── strategy_executor.py # scoring contract producer
```
[VERIFIED: repository file structure + files read]

### Pattern 1: Journal-linked Evaluation Extension
**What:** Tạo bảng evaluation mới tham chiếu journal (`journal_id` hoặc `trace_id` FK), không đè journal hiện tại. [VERIFIED: D:/Aureus/.planning/phases/55-evaluation-data-model-pipeline/55-CONTEXT.md]
**When to use:** Khi cần persist nhiều `score_version` cho cùng trade mà vẫn giữ lifecycle execution tách biệt. [VERIFIED: D:/Aureus/.planning/REQUIREMENTS.md] [ASSUMED]
**Example:**
```sql
-- Source: project migration pattern + phase constraints
CREATE TABLE aureus_trade_evaluations (
  id BIGSERIAL PRIMARY KEY,
  trade_journal_id BIGINT NOT NULL REFERENCES aureus_trade_journal(id) ON DELETE CASCADE,
  trace_id TEXT NOT NULL,
  score_version TEXT NOT NULL,
  score_total DOUBLE PRECISION,
  score_breakdown JSONB NOT NULL,
  weights_snapshot JSONB NOT NULL,
  missing_data_policy TEXT NOT NULL,
  strategy_name TEXT NOT NULL,
  symbol TEXT NOT NULL,
  timeframe TEXT NOT NULL,
  evaluated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (trade_journal_id, score_version)
);
```
[ASSUMED]

### Pattern 2: Trigger at ORDER_OPENED, Enrich on Lifecycle Updates
**What:** Bắt đầu ghi evaluation khi `ORDER_OPENED` (khóa D-07), sau đó cập nhật bổ sung context/closure theo lifecycle nếu cần. [VERIFIED: D:/Aureus/.planning/phases/55-evaluation-data-model-pipeline/55-CONTEXT.md]
**When to use:** Khi cần đảm bảo record chỉ tạo cho order thực sự được MT5 confirm thành công. [VERIFIED: D:/Aureus/services/aureus-trader/dispatcher.py]

### Anti-Patterns to Avoid
- **Persist tại STRATEGY_MATCH trước ACK/ORDER_OPENED:** Vi phạm D-07 và có thể tạo orphan evaluation cho lệnh không mở được. [VERIFIED: D:/Aureus/.planning/phases/55-evaluation-data-model-pipeline/55-CONTEXT.md]
- **Overwrite score cũ khi đổi weights:** Vi phạm EVAL-03 (mất lịch sử). [VERIFIED: D:/Aureus/.planning/REQUIREMENTS.md]
- **Idempotency key tách khỏi lineage journal:** Vi phạm D-05/D-06. [VERIFIED: D:/Aureus/.planning/phases/55-evaluation-data-model-pipeline/55-CONTEXT.md]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Dedup order/eval events | Custom in-memory dedup map | Redis NX key pattern như `IdempotencyChecker` | Atomic + đã dùng production path. [VERIFIED: D:/Aureus/services/aureus-trader/idempotency.py] |
| Lifecycle status rules | Ad-hoc string transitions | Existing state-machine conventions + explicit status checks | Đã có pattern testable trong codebase. [VERIFIED: D:/Aureus/services/aureus-db-writer/tests/test_state_machine.py] |
| JSON payload normalization | Manual scattered parsing | Centralized normalization trước DB write (pattern journal/scoring) | Giảm drift schema/payload. [VERIFIED: D:/Aureus/services/aureus-trader/journal.py] [VERIFIED: D:/Aureus/services/aureus-signal/engine/strategy_executor.py] |

**Key insight:** Reuse lineage + idempotency primitives hiện có sẽ giảm đáng kể rủi ro duplicate/orphan khi thêm evaluation pipeline. [VERIFIED: D:/Aureus/services/aureus-trader/idempotency.py] [VERIFIED: D:/Aureus/services/aureus-trader/journal.py]

## Common Pitfalls

### Pitfall 1: Mismatch trigger boundary
**What goes wrong:** Record evaluation được tạo quá sớm (strategy match) nên không map tới order thành công. [VERIFIED: D:/Aureus/.planning/phases/55-evaluation-data-model-pipeline/55-CONTEXT.md]
**Why it happens:** Reuse nhầm hook `on_strategy_match` thay vì `ORDER_OPENED`. [VERIFIED: D:/Aureus/services/aureus-trader/main.py] [VERIFIED: D:/Aureus/services/aureus-trader/dispatcher.py]
**How to avoid:** Persist initial evaluation từ `on_order_opened` path và ensure trace/ticket đã hiện diện.
**Warning signs:** Có evaluation record nhưng journal status không phải EXECUTED/CLOSED.

### Pitfall 2: Version overwrite
**What goes wrong:** Recompute ghi đè score cũ làm mất audit trail. [VERIFIED: D:/Aureus/.planning/REQUIREMENTS.md]
**Why it happens:** Dùng update-by-trace_id thay vì append-by-(trade,score_version). [ASSUMED]
**How to avoid:** Unique composite key có `score_version`; recompute tạo row mới.
**Warning signs:** Lịch sử chỉ còn 1 bản score/trade sau nhiều lần đổi weights.

### Pitfall 3: Weak constraints on JSON-rich schema
**What goes wrong:** `score_breakdown`/context bị null hoặc shape lỗi gây report sai. [ASSUMED]
**Why it happens:** Chỉ dựa vào app validation, thiếu DB NOT NULL/CHECK. [ASSUMED]
**How to avoid:** Kết hợp app validation + DB constraints + contract tests.
**Warning signs:** Query aggregate xuất hiện null score_version hoặc breakdown rỗng.

## Code Examples

Verified patterns from project sources:

### Atomic idempotency gate (Redis NX)
```python
# Source: D:/Aureus/services/aureus-trader/idempotency.py
async def check_and_mark(self, cmd_id: str) -> bool:
    key = f"aureus:trader:dedup:{cmd_id}"
    result = await self.redis.set(key, "1", ex=self.ttl, nx=True)
    return result is not None
```

### ORDER_OPENED integration point
```python
# Source: D:/Aureus/services/aureus-trader/dispatcher.py
if final.get("type") == "ORDER_OPENED":
    if self.journal:
        trace_id = order.get("trace_id", "")
        if trace_id:
            final["trace_id"] = trace_id
        await self.journal.on_order_opened(final)
```

### Scoring payload contract fields to persist
```python
# Source: D:/Aureus/services/aureus-signal/engine/strategy_executor.py
decision["score_total"] = round(float(scoring_result["score_total"]), 6)
decision["score_breakdown"] = {"criteria": criteria}
decision["score_version"] = scoring_result.get("score_version", DEFAULT_SCORE_VERSION)
decision["weights_snapshot"] = scoring_result.get("weights_snapshot", dict(DEFAULT_WEIGHTS_SNAPSHOT))
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Temporary scoring contract in executor only | Formalized DB-normalized evaluation persistence in Phase 55 scope | v1.6 planning (2026-04-21) | Enables stable querying, recompute history, and downstream reporting integrity. [VERIFIED: D:/Aureus/.planning/phases/54-strategy-scoring-framework/54-CONTEXT.md] [VERIFIED: D:/Aureus/.planning/ROADMAP.md] |

**Deprecated/outdated:**
- Temporary contract-only persistence for long-term analytics: không đủ EVAL-01→04. [VERIFIED: D:/Aureus/.planning/phases/54-strategy-scoring-framework/54-CONTEXT.md] [VERIFIED: D:/Aureus/.planning/REQUIREMENTS.md]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Composite unique `(trade_journal_id, score_version)` là key tối ưu nhất | Architecture Patterns | Có thể cần thêm dimensions/time bucket nếu business key khác. |
| A2 | Recompute nên append-only thay vì update current row | Summary / Pitfalls | Nếu product cần mutable “current only”, sẽ đổi semantics query/report. |
| A3 | Cần thêm DB-level CHECK/NOT NULL cho breakdown shape | Pitfalls | Nếu schema intentionally loose, constraints quá chặt có thể block ingest. |

## Open Questions (RESOLVED)

1. **Nguồn `timeframe` canonical để persist ở evaluation record là gì?**
   - **Resolved:** Dùng `timeframe` từ strategy decision/scoring payload do `strategy_executor` phát ra làm canonical field cho evaluation record; journal linkage chỉ dùng để trace lifecycle, không override dimension này.
   - **Implementation rule:** Persist trực tiếp `strategy_name/symbol/timeframe` vào core columns của evaluation record và giữ nguyên giá trị đó khi recompute để đảm bảo aggregate comparability theo version.

2. **Recompute orchestration đặt ở service nào?**
   - **Resolved:** Giao ownership recompute cho **aureus-db-writer** (single owner), chạy batch append-only theo score_version.
   - **Implementation rule:** `aureus-signal` chỉ emit scoring contract; `aureus-db-writer` chịu trách nhiệm persist/recompute/idempotency để tránh split-brain giữa services.

3. **Signal snapshot strategy cho mở rộng lâu dài?**
   - **Resolved:** Áp dụng hybrid contract: lưu full raw signal snapshot trong JSONB và trích các field analytics nóng thành typed columns + index.
   - **Implementation rule:** Signal mới được thêm trước vào JSONB theo schema version; chỉ promote thành typed column khi có nhu cầu thống kê truy vấn thường xuyên. Không lưu vật lý các field dẫn xuất như `ema21_above_ema55`; tính downstream bằng pandas/SQL expression từ `ema21` và `ema55` để tránh phình schema.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| python | trader/signal pipeline + scripts | ✓ | 3.12.9 | — |
| pytest | validation architecture | ✓ | 9.0.2 | `python -m pytest` |
| node/npm | gsd tooling/orchestration | ✓ | node v22.22.0 / npm 11.12.0 | — |
| psql CLI | manual migration verification | ✗ | — | Dùng app-level asyncpg migration path hoặc Docker container exec nếu có |
| redis-cli | manual redis probe | ✗ | — | Validate qua integration tests dùng redis client/fakeredis |
| docker CLI | local container service checks | ✗ | — | Dựa vào service runtime hiện có; nếu cần ops phải cài docker CLI |

**Missing dependencies with no fallback:**
- Không có blocking tuyệt đối cho coding phase; nhưng thiếu docker/psql CLI sẽ hạn chế manual ops verification.

**Missing dependencies with fallback:**
- psql, redis-cli, docker có fallback qua app tests / existing runtime integration.

## Large-Volume Data Organization & Index Strategy

- Partition ưu tiên theo thời gian (`created_at`/`evaluated_at`) cho bảng snapshot/evaluation khi volume tăng lớn; giữ query nóng trong partition gần nhất.
- Bộ index tối thiểu cho signal snapshot:
  - BTREE `(symbol, timeframe, created_at DESC)` cho truy vấn chuỗi thời gian theo cặp symbol-timeframe.
  - BTREE `(symbol, timeframe, cisd_direction, created_at DESC)` cho filter thống kê CISD nhanh.
  - BRIN `(created_at)` để giảm cost scan range rộng theo thời gian.
- Bộ index tối thiểu cho evaluation:
  - BTREE `(symbol, timeframe, evaluated_at DESC)`.
  - Partial index `WHERE is_current=true` cho truy vấn state hiện tại.
- Nguyên tắc mở rộng: chỉ thêm index mới khi có query profile chứng minh bottleneck; tránh over-index gây write amplification.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 [VERIFIED: local env command output] |
| Config file | `services/aureus-gateway/tests/pytest.ini` (repo-level rời rạc, chưa có config thống nhất) [VERIFIED: glob results] |
| Quick run command | `pytest services/aureus-trader/tests/test_journal.py -q` |
| Full suite command | `pytest services/aureus-trader/tests services/aureus-signal/tests -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| EVAL-01 | Schema normalized + constraints for evaluation records | migration/unit | `pytest services/aureus-trader/tests/test_journal.py -q` | ✅ (journal tests exist; eval schema tests need add) |
| EVAL-02 | Persist đầy đủ per-trade evaluation với lineage | integration | `pytest services/aureus-trader/tests/test_journal.py -q` | ✅ |
| EVAL-03 | Recompute/backfill theo score_version không mất lịch sử | integration | `pytest services/aureus-signal/tests/test_strategy_scoring_e2e.py -q` | ✅ (recompute-specific tests chưa có) |
| EVAL-04 | Idempotency + uniqueness + null checks | unit/integration | `pytest services/aureus-trader/tests/test_idempotency.py -q` | ✅ |

### Sampling Rate
- **Per task commit:** `pytest services/aureus-trader/tests/test_journal.py -q`
- **Per wave merge:** `pytest services/aureus-trader/tests/test_journal.py services/aureus-trader/tests/test_idempotency.py services/aureus-signal/tests/test_strategy_scoring_e2e.py -q`
- **Phase gate:** Full required subset green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `services/aureus-trader/tests/test_evaluation_pipeline.py` — covers EVAL-02/EVAL-04 for new evaluation table writes
- [ ] `services/aureus-db-writer/tests/test_evaluation_migration.py` — covers EVAL-01 constraints/indexes
- [ ] `services/aureus-trader/tests/test_evaluation_recompute.py` — covers EVAL-03 append-version behavior

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | N/A (internal service pipeline) [ASSUMED] |
| V3 Session Management | no | N/A (non-user session flow) [ASSUMED] |
| V4 Access Control | yes | DB role/connection scoping per service config [ASSUMED] |
| V5 Input Validation | yes | Pydantic + explicit validation in journal/pipeline code [VERIFIED: D:/Aureus/services/aureus-trader/journal.py] [VERIFIED: D:/Aureus/services/aureus-signal/requirements.txt] |
| V6 Cryptography | no | No crypto primitive introduced in this phase [ASSUMED] |

### Known Threat Patterns for Python async + Postgres pipeline

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Duplicate event replay | Tampering | Redis NX idempotency + DB unique constraints [VERIFIED: D:/Aureus/services/aureus-trader/idempotency.py] [ASSUMED] |
| Incomplete/invalid payload persisted | Tampering | Input validation + NOT NULL/CHECK + contract tests [VERIFIED: D:/Aureus/services/aureus-trader/journal.py] [ASSUMED] |
| Lost audit history on recompute | Repudiation | Append-only by score_version + immutable weights snapshot [VERIFIED: D:/Aureus/.planning/phases/54-strategy-scoring-framework/54-CONTEXT.md] [ASSUMED] |

## Sources

### Primary (HIGH confidence)
- `D:/Aureus/.planning/phases/55-evaluation-data-model-pipeline/55-CONTEXT.md` - locked decisions D-01..D-08 and phase scope
- `D:/Aureus/.planning/REQUIREMENTS.md` - EVAL-01..EVAL-04 requirements
- `D:/Aureus/.planning/ROADMAP.md` - phase goals/success criteria
- `D:/Aureus/services/aureus-trader/journal.py` - journal lifecycle persistence behavior
- `D:/Aureus/services/aureus-trader/dispatcher.py` - ORDER_OPENED/ORDER_CLOSED integration hooks
- `D:/Aureus/services/aureus-trader/idempotency.py` - Redis NX idempotency pattern
- `D:/Aureus/services/aureus-signal/engine/strategy_executor.py` - scoring payload contract fields
- `D:/Aureus/services/aureus-signal/engine/scoring/compute.py` - deterministic scoring structure
- `D:/Aureus/services/aureus-signal/engine/scoring/aggregate.py` - aggregate key semantics
- `D:/Aureus/services/aureus-db-writer/migrations/add_trade_journal.sql` - existing journal schema baseline
- `D:/Aureus/services/aureus-trader/tests/test_journal.py` - current data-quality expectations
- `D:/Aureus/CLAUDE.md` - project constraints
- Environment probe commands executed in this session - tool/runtime availability

### Secondary (MEDIUM confidence)
- None.

### Tertiary (LOW confidence)
- Các đề xuất DDL cụ thể cho bảng evaluation mới (phần example) — cần xác nhận khi chốt plan.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - dựa trên dependency + code đang chạy trong repo.
- Architecture: MEDIUM - boundary rõ, nhưng chi tiết DDL/recompute strategy vẫn cần chốt.
- Pitfalls: MEDIUM - phần lớn verified từ context/code, một phần là best-practice assumptions.

**Research date:** 2026-04-21
**Valid until:** 2026-05-21