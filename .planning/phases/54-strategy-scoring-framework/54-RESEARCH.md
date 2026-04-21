# Phase 54: Strategy Scoring Framework - Research

**Researched:** 2026-04-21
**Domain:** Strategy evaluation scoring (multi-criteria, versioned, auditable)
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Sử dụng kiến trúc **two-stage**: Stage 1 là quality gate, Stage 2 là weighted-sum scoring.
- **D-02:** Stage 2 áp dụng weighted-sum tuyến tính cho 4 trụ: profit outcome, signal quality, timing quality, volatility/session context.
- **D-03:** Quality gate là bắt buộc để loại các trade không đạt ngưỡng chất lượng tối thiểu trước khi vào tính điểm tổng hợp.
- **D-04:** Dùng **semantic score_version** làm định danh version chính.
- **D-05:** Mỗi score_version phải đi kèm **immutable weights snapshot** để đảm bảo tái lập kết quả tuyệt đối.
- **D-06:** Bất kỳ thay đổi công thức/trọng số nào đều tạo version mới, không overwrite version cũ.
- **D-07:** Tính score ở cấp **per-trade** và **aggregate**.
- **D-08:** Aggregate level khóa theo bộ chiều: **strategy / symbol / timeframe**.
- **D-09:** Persist breakdown theo định dạng **JSON breakdown** cho từng criterion, kèm normalization metadata.
- **D-10:** Bắt buộc có **missing-data policy explicit** trong payload để không mơ hồ khi criterion bị thiếu dữ liệu.
- **D-11:** Persist đầy đủ các trường phục vụ audit gồm score_total, score_breakdown, score_version và metadata liên quan normalization/weight snapshot.

### Claude's Discretion
- Thiết kế chi tiết công thức normalize cho từng criterion miễn vẫn tuân thủ contract versioning + breakdown đã khóa.
- Thiết kế mức precision (rounding/decimal) cụ thể miễn nhất quán và truy vết được.

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SCOR-01 | Định nghĩa scoring framework đa tiêu chí | Two-stage + 4-criteria contract + normalization strategy |
| SCOR-02 | Trọng số tiêu chí versioned | `score_version` + immutable `weights_snapshot` + no-overwrite policy |
| SCOR-03 | Per-trade + aggregate score | Aggregate key fixed at strategy/symbol/timeframe |
| SCOR-04 | Persist breakdown từng tiêu chí | JSON breakdown schema + missing-data policy trong payload |
| ACC-01 | Chạy end-to-end trước extension | Integration path bám `strategy_executor` + DB + dashboard patterns hiện hữu |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- Mọi trao đổi phải dùng tiếng Việt. [VERIFIED: /d/Aureus/CLAUDE.md]
- Nếu command lỗi, tham khảo `RUN_SERVICES.md`. [VERIFIED: /d/Aureus/CLAUDE.md]
- Ưu tiên giải pháp đơn giản, không over-engineer, không thêm scope ngoài yêu cầu. [VERIFIED: /d/Aureus/CLAUDE.md]
- Chỉ sửa phần liên quan trực tiếp yêu cầu (surgical changes). [VERIFIED: /d/Aureus/CLAUDE.md]
- Bắt buộc goal-driven execution với tiêu chí verify rõ ràng. [VERIFIED: /d/Aureus/CLAUDE.md]
- Với code-edit/refactor phải dùng GitNexus impact/detect_changes workflow; phase này là research nên chưa áp dụng edit workflow. [VERIFIED: /d/Aureus/CLAUDE.md]

## Summary

Phase 54 nên triển khai như một **scoring contract layer** cắm vào luồng đã có thay vì tạo subsystem mới: strategy executor hiện đã có điểm nối metadata + persistence pattern (`algo_score`, `algo_breakdown`) và hệ thống đã dùng PostgreSQL/JSONB mạnh cho payload breakdown. [VERIFIED: /d/Aureus/services/aureus-signal/engine/strategy_executor.py] [VERIFIED: /d/Aureus/services/aureus-db-writer/schema.sql]

Điểm quan trọng nhất để plan đúng là phân tách rõ: (1) quality gate fail/pass có lý do cụ thể, (2) weighted-sum stage luôn chạy deterministic trên normalized criteria + weight snapshot bất biến theo `score_version`, (3) persist đủ dữ liệu audit để sau này Phase 55/56 chỉ cần consume. [VERIFIED: /d/Aureus/.planning/phases/54-strategy-scoring-framework/54-CONTEXT.md]

Hiện schema chưa có bảng/field `score_version` cho strategy scoring trade-level; chỉ thấy pattern tương tự ở AI audit (`algo_score`, `algo_breakdown`). Vì vậy kế hoạch Phase 54 phải bao gồm contract payload và điểm ghi dữ liệu tạm thời/chuẩn bị migration interface để Phase 55 chuẩn hóa schema đầy đủ. [VERIFIED: grep score_version in /d/Aureus/services => no matches] [VERIFIED: /d/Aureus/services/aureus-signal/engine/ai_validator.py] [VERIFIED: /d/Aureus/services/aureus-signal/engine/strategy_executor.py]

**Primary recommendation:** Dùng contract `ScoringResultV1` bất biến (gate result + 4 criteria normalized + weighted snapshot + breakdown JSON + missing-data policy) và gắn vào strategy evaluation pipeline hiện tại trước khi mở rộng reporting. [VERIFIED: /d/Aureus/.planning/phases/54-strategy-scoring-framework/54-CONTEXT.md]

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.10.11 (runtime), 3.12.x cũng đang dùng trong test artifacts | Runtime chính cho signal engine | Code hiện tại là Python async services end-to-end [VERIFIED: `python3 --version`] [VERIFIED: /d/Aureus/services/aureus-signal/engine/strategy_executor.py] |
| asyncpg | 0.31.0 | Async PostgreSQL access | Đã pin và dùng rộng trong services [VERIFIED: /d/Aureus/services/aureus-signal/requirements.txt] [VERIFIED: /d/Aureus/services/aureus-dashboard/api/requirements.txt] |
| pydantic | 2.12.5 | Data contract validation cho scoring payload | Stack hiện dùng Pydantic v2 [VERIFIED: /d/Aureus/services/aureus-signal/requirements.txt] |
| PostgreSQL/Timescale + JSONB | Schema persistence breakdown metadata | Lưu breakdown + metadata linh hoạt, truy vấn được | Schema hiện dùng JSONB ở nhiều bảng signal/analysis [VERIFIED: /d/Aureus/services/aureus-db-writer/schema.sql] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| redis-py | 7.2.0 | Stream transport và cache | Khi cần stream scoring event/recompute trigger [VERIFIED: /d/Aureus/services/aureus-signal/requirements.txt] |
| numpy | 2.4.2 (pinned in service) | Aggregate/stat math | Dùng cho aggregate score/statistics layer [VERIFIED: /d/Aureus/services/aureus-signal/requirements.txt] |
| pandas | 3.0.1 (pinned in service) | Trade feature normalization input | Khi normalize theo window/time context [VERIFIED: /d/Aureus/services/aureus-signal/requirements.txt] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| JSONB breakdown in Postgres | Fully normalized per-criterion tables ngay Phase 54 | Chuẩn hóa mạnh hơn nhưng tăng scope, phù hợp hơn Phase 55 [VERIFIED: /d/Aureus/.planning/ROADMAP.md] |
| Pydantic contract validation | Thuần dict + manual checks | Ít code upfront nhưng dễ drift contract và thiếu guardrails [ASSUMED] |

**Installation:**
```bash
pip install -r /d/Aureus/services/aureus-signal/requirements.txt
```

**Version verification:**
- `pydantic`: pinned 2.12.5 (upload 2025-11-26), latest 2.13.3 (2026-04-20). [VERIFIED: PyPI via `python3 -m pip index versions pydantic` + JSON API]
- `fastapi`: pinned 0.129.0 (2026-02-12), latest 0.136.0 (2026-04-16). [VERIFIED: PyPI]
- `asyncpg`: pinned 0.31.0, latest cũng 0.31.0. [VERIFIED: PyPI]
- `redis`: pinned 7.2.0 (2026-02-16), latest 7.4.0 (2026-03-24). [VERIFIED: PyPI]
- `numpy`: pinned 2.4.2 (2026-01-31), latest 2.4.4 (2026-03-29). [VERIFIED: PyPI]
- `pandas`: pinned 3.0.1 (2026-02-17), latest 3.0.2 (2026-03-31). [VERIFIED: PyPI]

## Architecture Patterns

### Recommended Project Structure
```text
services/aureus-signal/engine/
├── scoring/
│   ├── models.py          # Pydantic ScoringResultV1 + WeightSnapshot
│   ├── gate.py            # Stage-1 quality gate
│   ├── normalize.py       # criterion normalizers
│   ├── compute.py         # Stage-2 weighted-sum
│   └── aggregate.py       # aggregate by strategy/symbol/timeframe
├── strategy_executor.py   # hook scoring result into pipeline
└── strategies/            # existing strategy evaluation
```
[ASSUMED]

### Pattern 1: Two-Stage Scoring Contract
**What:** Gate trước, score sau; gate fail thì final score phải có trạng thái fail + lý do, không im lặng. [VERIFIED: /d/Aureus/.planning/phases/54-strategy-scoring-framework/54-CONTEXT.md]
**When to use:** Mọi per-trade scoring event. [VERIFIED: SCOR-01..04 in /d/Aureus/.planning/REQUIREMENTS.md]
**Example:**
```python
# Source: /d/Aureus/.planning/phases/54-strategy-scoring-framework/54-CONTEXT.md
result = {
  "score_version": "scor-v1.0.0",
  "gate": {"passed": True, "reasons": []},
  "weights_snapshot": {
    "profit_outcome": 0.35,
    "signal_quality": 0.30,
    "timing_quality": 0.20,
    "volatility_session": 0.15,
  },
  "criteria": {
    "profit_outcome": {"raw": 1.8, "normalized": 0.72, "status": "ok"},
    "signal_quality": {"raw": 0.81, "normalized": 0.81, "status": "ok"},
    "timing_quality": {"raw": 0.55, "normalized": 0.55, "status": "ok"},
    "volatility_session": {"raw": 0.62, "normalized": 0.62, "status": "ok"}
  },
  "missing_data_policy": "impute_neutral_and_flag",
  "score_total": 0.707
}
```

### Pattern 2: Reuse Existing Breakdown Persistence Style
**What:** Theo pattern `algo_breakdown` đang lưu JSON để audit/history API. [VERIFIED: /d/Aureus/services/aureus-signal/engine/strategy_executor.py] [VERIFIED: /d/Aureus/services/aureus-dashboard/api/main.py]
**When to use:** Persist score breakdown từng trade trước khi có reporting engine hoàn chỉnh. [VERIFIED: ACC-01 + Phase 56 deferred in /d/Aureus/.planning/ROADMAP.md]

### Anti-Patterns to Avoid
- **Compute score nhưng không lưu weight snapshot:** phá reproducibility theo D-05/D-06. [VERIFIED: /d/Aureus/.planning/phases/54-strategy-scoring-framework/54-CONTEXT.md]
- **Chỉ lưu final score không breakdown:** vi phạm SCOR-04. [VERIFIED: /d/Aureus/.planning/REQUIREMENTS.md]
- **Overwrite config version cũ:** vi phạm immutable versioning policy. [VERIFIED: /d/Aureus/.planning/phases/54-strategy-scoring-framework/54-CONTEXT.md]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Payload validation | Custom if/else validator dài | Pydantic models | Giảm contract drift và lỗi kiểu dữ liệu [VERIFIED: pydantic is in requirements] [ASSUMED] |
| JSON serialization rules | Manual serializer riêng | PostgreSQL JSONB + `json.dumps` pattern hiện có | Đã proven trong ai_analysis pipeline [VERIFIED: /d/Aureus/services/aureus-signal/engine/strategy_executor.py] |
| Aggregate stats primitive | Tự viết accumulator rời rạc ở nhiều điểm | Aggregate module tập trung + numpy/pandas | Dễ test deterministic hơn [ASSUMED] |

**Key insight:** Phase 54 cần “contract-first”, không cần “new engine-first”; tận dụng luồng executor + DB pattern hiện tại để đạt ACC-01 nhanh và auditable. [VERIFIED: /d/Aureus/.planning/ROADMAP.md] [VERIFIED: /d/Aureus/services/aureus-signal/engine/strategy_executor.py]

## Common Pitfalls

### Pitfall 1: Gate/Score không deterministic theo version
**What goes wrong:** Cùng input nhưng score khác giữa lần chạy do weight/config mutable. [VERIFIED: D-05/D-06]
**Why it happens:** Dùng config hiện hành thay vì snapshot tại thời điểm tính. [ASSUMED]
**How to avoid:** Persist `score_version` + `weights_snapshot` vào từng record. [VERIFIED: D-04..D-06]
**Warning signs:** Recompute không khớp historical score. [ASSUMED]

### Pitfall 2: Thiếu explicit missing-data policy
**What goes wrong:** Criterion thiếu dữ liệu nhưng không rõ default/penalty, gây tranh cãi audit. [VERIFIED: D-10]
**Why it happens:** Breakdown schema không có `status/policy_applied`. [ASSUMED]
**How to avoid:** Bắt buộc field `missing_data_policy` + status từng criterion trong JSON. [VERIFIED: D-09/D-10]
**Warning signs:** Nhiều `null` trong breakdown mà final score vẫn có số hợp lệ. [ASSUMED]

### Pitfall 3: Trộn market_regime với htf_trend trong volatility/session criterion
**What goes wrong:** Double-count bias, score lệch ngữ nghĩa. [VERIFIED: folded todo note in CONTEXT]
**Why it happens:** Reuse feature cũ không tách vai trò trend vs regime. [VERIFIED: folded todo note]
**How to avoid:** Định nghĩa rule mapping tách biệt ngay trong criterion spec. [ASSUMED]
**Warning signs:** Volatility/session score biến động mạnh theo trend đổi chiều dù volatility không đổi. [ASSUMED]

## Code Examples

### Hook scoring vào strategy executor result enrichment
```python
# Source: /d/Aureus/services/aureus-signal/engine/strategy_executor.py
for result in strategy_results:
    decision = dict(result)
    decision["spec_version"] = SPEC_VERSION
    decision["engine_version"] = ENGINE_VERSION
    decision["strategy_version"] = str(decision.get("strategy_version") or "v0")
    decision["normalized_signal_snapshot"] = normalized_snapshot
```

### Persist JSON breakdown pattern đã có
```python
# Source: /d/Aureus/services/aureus-signal/engine/strategy_executor.py
await db_pool.execute(
  """
  INSERT INTO aureus_ai_analysis (..., algo_score, algo_breakdown, audit_source)
  VALUES (..., $15, $16, $17)
  """,
  ...,
  audit_result.get('algo_score'),
  json.dumps(audit_result.get('algo_breakdown', {})),
  audit_result.get('audit_source', 'HYBRID')
)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Strategy score chủ yếu sequence-weight trigger nội bộ (`min_score_threshold`) | Cần scoring đa tiêu chí tách contract evaluation (SCOR-01..04) | v1.6 roadmap (2026-04-21) | Tăng auditability và khả năng aggregate insight [VERIFIED: /d/Aureus/.planning/ROADMAP.md] [VERIFIED: /d/Aureus/services/aureus-signal/engine/strategies/template.py] |

**Deprecated/outdated:**
- Coi `min_score_threshold` trong TemplateStrategy là đủ cho strategy evaluation intelligence milestone. [VERIFIED: template.py + SCOR requirements mismatch]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Tách module `engine/scoring/*` là cấu trúc phù hợp nhất | Architecture Patterns | Planner có thể over-structure hoặc lệch style repo |
| A2 | Dùng aggregate module với numpy/pandas là cách tối ưu cho deterministic aggregate score | Don't Hand-Roll | Có thể tăng dependency/complexity không cần thiết |
| A3 | Một số warning signs/pitfall root-cause là suy luận từ pattern chung | Common Pitfalls | Checklist verify có thể thiếu tình huống đặc thù hệ thống |

## Open Questions (RESOLVED)

1. **[RESOLVED] Điểm persist canonical cho strategy scoring Phase 54 là bảng nào?**
   - What we know: Chưa có `score_version` trong schema hiện tại; chỉ có pattern `aureus_ai_analysis.algo_score/algo_breakdown`. [VERIFIED: grep + schema.sql]
   - Decision: Phase 54 dùng **temporary persistence contract** bằng cách enrich decision payload trong `strategy_executor` với `score_total`, `score_breakdown`, `score_version`, `weights_snapshot`, `missing_data_policy` theo D-11; chưa tạo bảng mới ở phase này.
   - Rationale: Khớp boundary ACC-01 "chạy end-to-end trước extension", tránh mở rộng schema vượt scope và giữ đường migration schema canonical cho Phase 55.
   - Plan sync: Đã khớp với Plan 54-02 Task 2 (wiring + audit artifact assertions).

2. **[RESOLVED] Precision/rounding chuẩn cho score_total và criterion normalized?**
   - What we know: User cho Claude discretion về precision. [VERIFIED: 54-CONTEXT.md]
   - Decision: Chuẩn hóa và lưu nội bộ ở **6 decimals** cho `score_total` và `criteria[*].normalized`; display formatting (nếu cần ở phase sau) có thể rút còn 4 decimals nhưng không thay đổi persisted raw value.
   - Rationale: Cân bằng reproducibility và ổn định aggregate, đồng bộ với implementation contract đã khóa ở Plan 54-01 Task 2.
   - Plan sync: Đã khớp với Plan 54-01 Task 2 (`round internal 6 decimals`).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| python3 | scoring implementation/tests | ✓ | 3.10.11 | — |
| pytest | validation architecture | ✓ | 9.0.2 | — |
| npm | frontend/api aux tooling | ✓ | 11.12.0 | — |
| docker | local infra orchestration | ✗ | — | chạy service trực tiếp theo RUN_SERVICES.md |
| redis-cli | kiểm tra Redis runtime nhanh | ✗ | — | dùng app logs + redis client trong code |
| psql/pg_isready | DB readiness checks | ✗ | — | dùng asyncpg connectivity checks trong app |

**Missing dependencies with no fallback:**
- None for planning/implementation scope Phase 54 (core code path vẫn chạy bằng Python libs). [VERIFIED: availability probes]

**Missing dependencies with fallback:**
- docker, redis-cli, psql/pg_isready. [VERIFIED: availability probes]

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 [VERIFIED: `pytest --version`] |
| Config file | `services/aureus-gateway/tests/pytest.ini` (global cho signal chưa thấy dedicated pytest.ini) [VERIFIED: glob pytest.ini] |
| Quick run command | `python3 -m pytest /d/Aureus/services/aureus-signal/tests/test_template_strategy.py -q` [VERIFIED: test file exists] |
| Full suite command | `python3 -m pytest /d/Aureus/services/aureus-signal/tests -q` [VERIFIED: tests directory exists] |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SCOR-01 | 4-criteria formula + gate flow | unit | `python3 -m pytest /d/Aureus/services/aureus-signal/tests/test_scoring_formula.py -q` | ❌ Wave 0 |
| SCOR-02 | versioned weights snapshot immutable | unit | `python3 -m pytest /d/Aureus/services/aureus-signal/tests/test_score_versioning.py -q` | ❌ Wave 0 |
| SCOR-03 | per-trade + aggregate output | integration | `python3 -m pytest /d/Aureus/services/aureus-signal/tests/test_scoring_aggregate.py -q` | ❌ Wave 0 |
| SCOR-04 | breakdown persistence + missing-data policy | integration | `python3 -m pytest /d/Aureus/services/aureus-signal/tests/test_scoring_breakdown_persistence.py -q` | ❌ Wave 0 |
| ACC-01 | end-to-end scoring through executor path | smoke | `python3 -m pytest /d/Aureus/services/aureus-signal/tests/test_scoring_e2e_executor.py -q` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `python3 -m pytest /d/Aureus/services/aureus-signal/tests/test_template_strategy.py -q`
- **Per wave merge:** `python3 -m pytest /d/Aureus/services/aureus-signal/tests -q`
- **Phase gate:** Full suite signal service + scoring-specific tests green trước `/gsd-verify-work`.

### Wave 0 Gaps
- [ ] `services/aureus-signal/tests/test_scoring_formula.py` — covers SCOR-01
- [ ] `services/aureus-signal/tests/test_score_versioning.py` — covers SCOR-02
- [ ] `services/aureus-signal/tests/test_scoring_aggregate.py` — covers SCOR-03
- [ ] `services/aureus-signal/tests/test_scoring_breakdown_persistence.py` — covers SCOR-04
- [ ] `services/aureus-signal/tests/test_scoring_e2e_executor.py` — covers ACC-01

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Internal service path only in this phase scope [ASSUMED] |
| V3 Session Management | no | N/A for scoring compute path [ASSUMED] |
| V4 Access Control | yes | API/service boundary enforcement existing FastAPI layer [VERIFIED: /d/Aureus/services/aureus-dashboard/api/main.py] |
| V5 Input Validation | yes | Pydantic contract validation for scoring payloads [VERIFIED: pydantic in requirements] |
| V6 Cryptography | no | Không có crypto logic mới trong phase này [VERIFIED: scope in 54-CONTEXT]

### Known Threat Patterns for Python async + JSONB scoring stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| JSON payload tampering/inconsistent schema | Tampering | Schema validation + strict required fields (`score_version`, weights snapshot, breakdown) [ASSUMED] |
| Replay/recompute mismatch | Repudiation | Immutable version snapshots + audit fields persisted per trade [VERIFIED: D-04..D-06, D-11] |
| Missing-data silent coercion | Integrity | Explicit missing-data policy + criterion status flags [VERIFIED: D-10] |

## Sources

### Primary (HIGH confidence)
- `/d/Aureus/.planning/phases/54-strategy-scoring-framework/54-CONTEXT.md` - locked decisions, scoring architecture constraints.
- `/d/Aureus/.planning/REQUIREMENTS.md` - SCOR-01..04, ACC-01 requirements.
- `/d/Aureus/.planning/ROADMAP.md` - phase boundary and success criteria.
- `/d/Aureus/CLAUDE.md` - project constraints and execution guardrails.
- `/d/Aureus/services/aureus-signal/engine/strategies/template.py` - existing sequence scoring and threshold behavior.
- `/d/Aureus/services/aureus-signal/engine/strategy_executor.py` - current enrich/persist integration path.
- `/d/Aureus/services/aureus-signal/engine/ai_validator.py` - existing breakdown pattern usage.
- `/d/Aureus/services/aureus-db-writer/schema.sql` - current DB capabilities and missing score_version fields.
- `/d/Aureus/services/aureus-dashboard/api/main.py` - downstream retrieval of breakdown fields.
- PyPI index + JSON API via commands run in session - verified package latest/pinned versions and publish timestamps.

### Secondary (MEDIUM confidence)
- None.

### Tertiary (LOW confidence)
- Architectural structuring and some mitigation recommendations marked `[ASSUMED]`.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - verified from requirements files + PyPI live checks.
- Architecture: HIGH - constrained strongly by locked decisions and existing code paths.
- Pitfalls: MEDIUM - partly inferred from patterns, explicitly marked assumptions where needed.

**Research date:** 2026-04-21
**Valid until:** 2026-05-21
