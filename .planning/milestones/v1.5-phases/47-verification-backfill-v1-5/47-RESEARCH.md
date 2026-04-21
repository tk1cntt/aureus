# Phase 47: verification-backfill-v1-5 - Research

**Researched:** 2026-04-20
**Domain:** Verification backfill, requirement-level traceability, milestone audit evidence normalization
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
### Verification Backfill Scope
- **D-01:** Backfill verification cho đúng các phase thiếu artifact theo audit: **26, 28, 29, 31, 32, 33**.
- **D-02:** Mỗi phase backfill phải có 1 file `{phase}-VERIFICATION.md` theo format verifier hiện hành (frontmatter + Goal Achievement + Requirements Coverage + Gaps/Human Needed nếu có).
- **D-03:** Không “tuyên bố complete” bằng SUMMARY-only; requirement chỉ được coi là closed khi có evidence trong VERIFICATION.

### Requirement-level Evidence Policy
- **D-04:** Với mỗi requirement mục tiêu của phase 47 (NOTIF-01, STRAT-01..04, ORDER-04..07, TRADE-03..04), verification bắt buộc map theo bảng `Requirement | Status | Evidence` với tham chiếu file/test/command cụ thể.
- **D-05:** Evidence ưu tiên 3 lớp: (1) artifact/code-path, (2) test/command output, (3) flow/key-link wiring; thiếu lớp nào phải ghi rõ mức độ confidence.
- **D-06:** Nếu có điểm chưa thể auto-verify (môi trường live/manual), trạng thái phải là `human_needed` thay vì `passed`.

### Traceability & Audit Consistency
- **D-07:** Sau khi backfill, REQUIREMENTS traceability phải đồng bộ trạng thái từ Pending/Orphaned sang trạng thái đã có chứng cứ verification.
- **D-08:** `v1.5-MILESTONE-AUDIT.md` là baseline gap list để đối chiếu đóng gap; không tự mở rộng scope requirement ngoài danh sách audit hiện tại.
- **D-09:** Mọi kết luận phải nhất quán với Nyquist gate (không bypass VALIDATION/VERIFICATION contract).

### Scope Guardrails
- **D-10:** Không sửa runtime/business logic ở phase 47 trừ khi bắt buộc để khôi phục khả năng verify (nếu phát hiện blocker kỹ thuật thì ghi gap chuyển phase 48/49).
- **D-11:** Integration gaps đã audit (backtest API wiring, qty contract, multi-symbol hardcode) được giữ nguyên deferred sang phase đã map (48/49), chỉ link chéo trong verification nếu liên quan.

### Claude's Discretion
- Thứ tự ưu tiên backfill giữa các phase 26/28/29/31/32/33 để tối ưu tốc độ đóng orphan count.
- Mức chi tiết narrative trong phần Goal Achievement miễn vẫn đủ bằng chứng truy vết requirement-level.

### Deferred Ideas (OUT OF SCOPE)
- Sửa các integration gap kỹ thuật runtime (backtest API route mismatch, qty contract mismatch, hardcode XAUUSD consumer) — defer sang Phase 48/49 theo roadmap.
- Nyquist missing/partial closure và milestone re-audit cuối — defer sang Phase 50.

### Reviewed Todos (not folded)
- `2026-03-28-remove-market-regime-use-htf-trend.md` — không thuộc verification backfill scope.
- `2026-03-28-investigate-sweep-triggers-after-broken-pending.md` — thuộc điều tra logic signal, không phải requirement verification backfill.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| NOTIF-01 | Signal engine publishes signal events qua Redis pub/sub | Backfill 26-VERIFICATION với artifact `signal_event_publisher.py` + wiring `strategy_executor.py/live_engine.py` + test outputs [VERIFIED: .planning/phases/26-signal-event-pipeline-strategy-contract/26-01-SUMMARY.md] |
| STRAT-01 | Strategy contract có entry_type | Backfill 26-VERIFICATION requirement table + references từ 26-PLAN/summary [VERIFIED: 26-01-PLAN.md + 26-01-SUMMARY.md] |
| STRAT-02 | Strategy output có SL/TP values | Backfill 26-VERIFICATION với evidence `_calculate_sl_tp` fallback removal + tests [VERIFIED: 26-01-PLAN.md + 26-01-SUMMARY.md] |
| STRAT-03 | Strategy output có lot size / risk percentage | Backfill 26-VERIFICATION với `size_value/size_mode` propagation evidence [VERIFIED: 26-01-PLAN.md + 26-01-SUMMARY.md] |
| STRAT-04 | Magic number per strategy | Backfill 26-VERIFICATION với migration + registry/template evidence [VERIFIED: 26-01-PLAN.md + 26-01-SUMMARY.md] |
| ORDER-04 | EA nhận command và execute OrderSend | Backfill 28-VERIFICATION với `AureusProvider.mq5` execution path [VERIFIED: 28-01-PLAN.md + 28-01-SUMMARY.md] |
| ORDER-05 | EA push order events | Backfill 28-VERIFICATION với ORDER_OPENED/CLOSED/FAILED + gateway validation [VERIFIED: 28-01-PLAN.md + 28-01-SUMMARY.md] |
| ORDER-06 | ACK/NACK protocol | Backfill 28-VERIFICATION với cmd_id + ACK/NACK event path [VERIFIED: 28-01-PLAN.md + 28-01-SUMMARY.md] |
| ORDER-07 | Idempotency key chống duplicate execution | Backfill 29-VERIFICATION với idempotency checker + tests [VERIFIED: 29-01-SUMMARY.md] |
| TRADE-03 | MT5 history push events (real-time close notification) | Backfill 31-VERIFICATION với OnTradeTransaction/push flow evidence [VERIFIED: 31-01-SUMMARY.md + 31-01-PLAN.md] |
| TRADE-04 | MT5 history poll reconciliation fallback | Backfill 31-VERIFICATION với reconciliation loop + XPENDING recovery + log table [VERIFIED: 31-01-SUMMARY.md + 31-01-PLAN.md] |
</phase_requirements>

## Summary

Phase 47 là phase **verification backfill thuần artifact/traceability** để đóng orphan requirements v1.5, không phải phase phát triển logic runtime mới. [VERIFIED: .planning/phases/47-verification-backfill-v1-5/47-CONTEXT.md] Audit hiện tại đánh dấu nhiều requirement orphan vì thiếu `*-VERIFICATION.md` dù đã có PLAN/SUMMARY triển khai trước đó. [VERIFIED: .planning/v1.5-MILESTONE-AUDIT.md]

Bằng chứng trong repo cho thấy pattern verifier chuẩn đã ổn định: frontmatter trạng thái (`passed`/`human_needed`/`gaps_found`), bảng requirement coverage, key-link verification, behavioral spot-checks, và kết luận gate. [VERIFIED: 44-VERIFICATION.md, 45-VERIFICATION.md, 40-VERIFICATION.md] Vì vậy, cách triển khai an toàn nhất là dựng lại verification cho đúng 6 phase mục tiêu (26/28/29/31/32/33), map requirement-level theo contract D-04/D-05, đồng bộ traceability trong REQUIREMENTS, và giữ nguyên integration gaps defer sang phase 48/49.

`workflow.nyquist_validation=true`, nên planner phải thiết kế plan tạo artifact verification theo chuẩn Nyquist thay vì viết summary narrative chung. [VERIFIED: .planning/config.json]

**Primary recommendation:** Ưu tiên backfill theo thứ tự **26 → 28 → 29 → 31 → 32 → 33**, hoàn tất mỗi phase bằng một `*-VERIFICATION.md` có bảng `Requirement | Status | Evidence`, rồi cập nhật traceability để đóng orphan ngay sau từng cụm requirement. [VERIFIED: 47-CONTEXT.md + REQUIREMENTS.md + v1.5-MILESTONE-AUDIT.md]

## Project Constraints (from CLAUDE.md)

- Mọi trao đổi phải dùng tiếng Việt. [VERIFIED: CLAUDE.md]
- Khi command lỗi, tham khảo `RUN_SERVICES.md`. [VERIFIED: CLAUDE.md]
- Tên phase tiếng Anh, ngắn gọn; không tạo phase 1000+. [VERIFIED: CLAUDE.md]
- Triển khai tối giản, không scope creep, không thêm tính năng ngoài yêu cầu. [VERIFIED: CLAUDE.md]
- Chỉ thay đổi đúng phạm vi cần thiết (surgical changes). [VERIFIED: CLAUDE.md]
- Goal-driven: mỗi bước cần tiêu chí verify rõ ràng. [VERIFIED: CLAUDE.md]
- Vì phase 47 là docs/verification backfill, **không cần sửa symbol runtime** trừ khi phát hiện blocker bắt buộc. [VERIFIED: 47-CONTEXT.md + CLAUDE.md]

## Standard Stack

### Core
| Library/Tool | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Markdown `*-VERIFICATION.md` contract | N/A | Artifact sự thật cuối cho phase gate | Audit hiện tại dùng VERIFICATION làm nguồn xác nhận thay vì SUMMARY [VERIFIED: v1.5-MILESTONE-AUDIT.md] |
| Nyquist verification format (frontmatter + truth/coverage/checks) | N/A | Chuẩn hóa bằng chứng requirement-level | Đang dùng nhất quán ở phase 40/44/45 [VERIFIED: 40-VERIFICATION.md, 44-VERIFICATION.md, 45-VERIFICATION.md] |
| REQUIREMENTS traceability table | N/A | Đồng bộ trạng thái orphan/pending → có chứng cứ | D-07 yêu cầu đồng bộ sau backfill [VERIFIED: 47-CONTEXT.md + REQUIREMENTS.md] |

### Supporting
| Tool | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | 9.0.2 | Chạy lại lệnh test đã có để lấy evidence command output | Dùng khi verification cần lớp evidence test/command [VERIFIED: local env `pytest --version`] |
| python3 | 3.10.11 | Chạy script/check nhẹ phục vụ kiểm chứng artifacts | Dùng khi cần parse/spot-check nhanh [VERIFIED: local env `python3 --version`] |
| node/npm | Node v22.22.0 / npm 11.12.0 | Hỗ trợ lệnh tooling hiện có nếu cần chứng cứ frontend/API | Dùng cho phase 32/33 verification command references [VERIFIED: local env `node --version`, `npm --version`] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Requirement-level VERIFICATION table | Summary narrative-only | Không đóng orphan theo audit rule, không pass milestone gate [VERIFIED: v1.5-MILESTONE-AUDIT.md + 47-CONTEXT.md] |
| Backfill đúng 6 phase bị thiếu | Backfill toàn bộ phase v1.5 | Vượt scope D-01/D-08, tăng chi phí không cần thiết [VERIFIED: 47-CONTEXT.md] |

**Installation:**
```bash
# Không yêu cầu cài package mới cho phase 47 (verification backfill docs-first).
```

## Architecture Patterns

### Recommended Project Structure
```text
.planning/
├── phases/
│   ├── 26-.../
│   │   └── 26-VERIFICATION.md   # backfill mới
│   ├── 28-.../
│   │   └── 28-VERIFICATION.md   # backfill mới
│   ├── 29-.../
│   │   └── 29-VERIFICATION.md   # backfill mới
│   ├── 31-.../
│   │   └── 31-VERIFICATION.md   # backfill mới
│   ├── 32-.../
│   │   └── 32-VERIFICATION.md   # backfill mới
│   └── 33-.../
│       └── 33-VERIFICATION.md   # backfill mới
├── REQUIREMENTS.md              # cập nhật traceability
└── v1.5-MILESTONE-AUDIT.md      # baseline đối chiếu đóng gap
```

### Pattern 1: Requirement-level evidence triad
**What:** Mỗi requirement cần 3 lớp evidence: artifact/code-path, test/command output, key-link wiring.
**When to use:** Cho từng requirement trong NOTIF-01, STRAT-01..04, ORDER-04..07, TRADE-03..04.
**Example:**
```markdown
| Requirement | Status | Evidence |
|-------------|--------|----------|
| ORDER-06 | passed | (1) `SendACK/SendNACK` in mql5/AureusProvider.mq5; (2) gateway tests for ACK/NACK; (3) TCP->gateway->Redis link `aureus:mt5:events` |
```
Source: 47-CONTEXT.md D-04/D-05 [VERIFIED: .planning/phases/47-verification-backfill-v1-5/47-CONTEXT.md]

### Pattern 2: Status discipline (`passed` vs `human_needed`)
**What:** Nếu chưa auto-verify được bằng môi trường hiện tại thì bắt buộc `human_needed`.
**When to use:** Các check cần MT5 live/manual hoặc integration runtime không thể chứng minh bằng artifact-only.
**Example:**
```yaml
status: human_needed
human_verification:
  - test: "..."
    why_human: "..."
```
Source: 44-VERIFICATION frontmatter pattern [VERIFIED: .planning/phases/44-profiling-baseline-performance/44-VERIFICATION.md]

### Pattern 3: Verification as gate artifact, không dùng summary thay thế
**What:** `*-VERIFICATION.md` là evidence contract cuối cùng cho audit.
**When to use:** Với mọi phase đang bị orphan do thiếu verification.
**Anti-pattern to avoid:** Dùng `*-SUMMARY.md` để kết luận complete.
[VERIFIED: v1.5-MILESTONE-AUDIT.md + 47-CONTEXT.md]

### Anti-Patterns to Avoid
- **Summary-only closure:** Audit coi là orphan nếu không có verification table. [VERIFIED: v1.5-MILESTONE-AUDIT.md]
- **Over-claim passed khi thiếu manual gate:** Vi phạm D-06 và làm sai gate quality. [VERIFIED: 47-CONTEXT.md]
- **Mở rộng sang integration fix runtime:** Lệch scope phase 47, phải defer phase 48/49. [VERIFIED: 47-CONTEXT.md]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Chuẩn format verification | Tự nghĩ format mới theo phase | Reuse format đã chứng minh ở 40/44/45 | Giữ consistency để audit tooling đọc được [VERIFIED: 40/44/45-VERIFICATION.md] |
| Requirement closure logic | Quy tắc ad-hoc “đã done trong summary” | Rule orphan/traceability hiện hành | Audit đã xác định summary-only là không đủ [VERIFIED: v1.5-MILESTONE-AUDIT.md] |
| Nyquist gate semantics | Tự định nghĩa pass criteria mới | Bám frontmatter + coverage + spot-check + human-needed contract hiện hành | Tránh bypass validation/verification contract [VERIFIED: 47-CONTEXT.md + config.json]

**Key insight:** Phase 47 cần **chuẩn hóa chứng cứ**, không cần sáng tạo cơ chế mới. [VERIFIED: 47-CONTEXT.md]

## Common Pitfalls

### Pitfall 1: Backfill sai phạm vi
**What goes wrong:** Planner thêm phase ngoài 26/28/29/31/32/33.
**Why it happens:** Trộn mục tiêu đóng orphan hiện tại với backlog toàn milestone.
**How to avoid:** Khóa scope theo D-01 và baseline audit D-08.
**Warning signs:** Task xuất hiện cho phase 27/30/35/40/46 trong plan 47.
[VERIFIED: 47-CONTEXT.md]

### Pitfall 2: Mark `passed` cho chứng cứ chưa thể auto-verify
**What goes wrong:** Kết luận quá mức tin cậy cho runtime/live behavior.
**Why it happens:** Chỉ dựa code đọc tĩnh hoặc summary cũ.
**How to avoid:** Dùng `human_needed` + liệt kê manual verification rõ.
**Warning signs:** Không có command/test output nhưng vẫn `passed`.
[VERIFIED: 47-CONTEXT.md D-06 + 44-VERIFICATION.md]

### Pitfall 3: Không đồng bộ REQUIREMENTS traceability sau khi viết VERIFICATION
**What goes wrong:** Evidence có nhưng orphan count không giảm trên audit.
**Why it happens:** Bỏ sót bước cập nhật bảng traceability.
**How to avoid:** Mỗi cụm backfill phải đi kèm bước update REQUIREMENTS.
**Warning signs:** REQUIREMENTS vẫn `Pending` cho các ID phase 47.
[VERIFIED: REQUIREMENTS.md + 47-CONTEXT.md D-07]

## Code Examples

Verified pattern snippets for planner task templates:

### Verification frontmatter + status contract
```markdown
---
phase: 45-h-tr-...
verified: 2026-04-18T13:10:00Z
status: passed
score: 7/7 must-haves verified
---
```
Source: `.planning/phases/45-h-tr-x-ly-song-song-signal-strategy-cho-nhi-u-symbol-m-t-/45-VERIFICATION.md` [VERIFIED: repo file]

### Requirement coverage table
```markdown
| Requirement | Source Plan | Description | Status | Evidence |
| --- | --- | --- | --- | --- |
| PH45-01 | 45-01/45-04 | ... | ✓ SATISFIED | ... |
```
Source: `45-VERIFICATION.md` [VERIFIED: repo file]

### Human-needed pattern
```markdown
### Human Verification Required

### 1. Shadow rollout production telemetry
**Test:** ...
**Expected:** ...
**Why human:** ...
```
Source: `44-VERIFICATION.md` [VERIFIED: repo file]

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Summary-driven completion claims | Verification-driven requirement closure | Milestone audit 2026-04-20 | Buộc phải có `*-VERIFICATION.md` để đóng orphan [VERIFIED: v1.5-MILESTONE-AUDIT.md] |
| Phase-level “done” chung | Requirement-level `Status + Evidence` | Được khóa bởi D-04 phase 47 | Planner phải tách evidence theo từng REQ-ID [VERIFIED: 47-CONTEXT.md] |
| Binary pass/fail | `passed` / `human_needed` / `gaps_found` | Đang dùng ở phase gần đây | Tăng tính trung thực cho gate decisions [VERIFIED: 44/45-VERIFICATION.md] |

**Deprecated/outdated:**
- Dùng SUMMARY để đóng requirement orphan là không còn hợp lệ. [VERIFIED: v1.5-MILESTONE-AUDIT.md]

## Open Questions (RESOLVED)

1. **Phase 27/30 có cần backfill trong cùng đợt không? — RESOLVED**
   - What we know: D-01 khóa scope chỉ 26/28/29/31/32/33.
   - Resolution: **Không** đưa 27/30 vào Phase 47 để tránh scope creep; giữ đúng boundary verification-backfill đã chốt trong CONTEXT.
   - Follow-up: Nếu cần đóng thêm 27/30 thì mở phase kế tiếp độc lập, không trộn vào Phase 47. [VERIFIED: 47-CONTEXT.md + v1.5-MILESTONE-AUDIT.md]

2. **Mức độ chạy lại test thực tế tới đâu trong backfill? — RESOLVED**
   - What we know: Có historical command/test evidence trong summary/validation cũ.
   - Resolution: Áp dụng policy **targeted re-run bắt buộc** cho từng REQ-ID backfill (quick pytest theo requirement map), dùng historical evidence như lớp bổ trợ, và đánh dấu `human_needed` khi phụ thuộc MT5/runtime live.
   - Rationale: Đáp ứng D-05 (3 lớp evidence) và D-06 (không over-claim passed). [VERIFIED: 47-CONTEXT.md + 47-VALIDATION.md]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Policy “targeted re-run bắt buộc + historical evidence bổ trợ + human_needed cho live-only checks” đủ để pass gate requirement-level | Open Questions #2 (RESOLVED) | Nếu lệnh quick-run không thực thi được trong môi trường hiện tại, phải ghi rõ blocker thay vì đánh passed |

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 [VERIFIED: local env] |
| Config file | Mixed per-service/root (ví dụ `services/aureus-gateway/tests/pytest.ini`) [VERIFIED: 28-01-SUMMARY.md] |
| Quick run command | `pytest -q -x <targeted_test_file>` [VERIFIED: patterns in 31-VALIDATION.md + 44/45-VERIFICATION.md] |
| Full suite command | `pytest tests/ -x -q` (service-scoped) [VERIFIED: 31-VALIDATION.md] |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| NOTIF-01 | Publish signal events to Redis | unit/integration | `pytest services/aureus-signal/tests/test_signal_event_publisher.py -q -x` | ✅ [VERIFIED: 26-01-SUMMARY.md] |
| STRAT-01 | entry_type contract | unit | `pytest services/aureus-signal/tests/test_strategy_contract_v2.py -q -x` | ✅ [VERIFIED: 26-01-SUMMARY.md] |
| STRAT-02 | SL/TP contract behavior | unit | `pytest services/aureus-signal/tests/test_strategy_contract_v2.py -q -x` | ✅ [VERIFIED: 26-01-SUMMARY.md] |
| STRAT-03 | size_mode/size_value propagation | unit | `pytest services/aureus-signal/tests/test_strategy_contract_v2.py -q -x` | ✅ [VERIFIED: 26-01-SUMMARY.md] |
| STRAT-04 | magic_number propagation | unit | `pytest services/aureus-signal/tests/test_strategy_contract_v2.py -q -x` | ✅ [VERIFIED: 26-01-SUMMARY.md] |
| ORDER-04 | EA executes OPEN/CLOSE order commands | manual+artifact | MetaEditor compile + gateway test command | ⚠️ manual gate [VERIFIED: 28-01-PLAN.md/28-01-SUMMARY.md] |
| ORDER-05 | EA pushes order lifecycle events | unit + manual integration | `pytest services/aureus-gateway/tests/test_order_events.py -q -x` | ✅ [VERIFIED: 35-VERIFICATION.md + 28-01-SUMMARY.md] |
| ORDER-06 | ACK/NACK protocol wired | unit + artifact | `pytest services/aureus-gateway/tests/test_order_events.py -q -x` | ✅ [VERIFIED: 28-01-SUMMARY.md] |
| ORDER-07 | Idempotency duplicate prevention | unit | `pytest services/aureus-trader/tests/test_idempotency.py -q -x` | ✅ [VERIFIED: 29-01-SUMMARY.md] |
| TRADE-03 | real-time close/history push path | artifact + integration | `pytest services/aureus-db-writer/tests/test_order_persistence.py -q -x` | ✅ [VERIFIED: 31-VALIDATION.md] |
| TRADE-04 | polling reconciliation loop fallback | unit/integration/manual | `pytest services/aureus-db-writer/tests/test_reconciliation.py -q -x` | ✅ [VERIFIED: 31-VALIDATION.md] |

### Sampling Rate
- **Per task commit:** requirement-targeted pytest command
- **Per wave merge:** service full suite (`pytest tests/ -x -q`)
- **Phase gate:** tất cả `*-VERIFICATION.md` đã có requirement coverage table + traceability sync in REQUIREMENTS

### Wave 0 Gaps
- [ ] `26-VERIFICATION.md` missing — tạo mới theo format chuẩn
- [ ] `28-VERIFICATION.md` missing — tạo mới theo format chuẩn
- [ ] `29-VERIFICATION.md` missing — tạo mới theo format chuẩn
- [ ] `31-VERIFICATION.md` missing — tạo mới theo format chuẩn
- [ ] `32-VERIFICATION.md` missing — tạo mới theo format chuẩn
- [ ] `33-VERIFICATION.md` missing — tạo mới theo format chuẩn
- [ ] REQUIREMENTS traceability update after each verification batch
[VERIFIED: glob check no *VERIFICATION.md in phase 26/28/29/31/32/33]

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | N/A (phase 47 docs backfill) [VERIFIED: phase goal] |
| V3 Session Management | no | N/A (phase 47 docs backfill) [VERIFIED: phase goal] |
| V4 Access Control | no | Scope guardrail: không thêm runtime behavior mới [VERIFIED: 47-CONTEXT D-10] |
| V5 Input Validation | yes | Verification evidence phải trỏ test/validation đã tồn tại, không claim mơ hồ [VERIFIED: D-04/D-05] |
| V6 Cryptography | no | N/A trong verification-only phase [VERIFIED: phase goal] |

### Known Threat Patterns for this phase

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| False-positive completion claims | Repudiation | Requirement-level evidence table + source file/test/command references [VERIFIED: D-04] |
| Scope creep into runtime fixes | Tampering | Guardrail D-10/D-11; defer sang phase 48/49 | [VERIFIED: 47-CONTEXT.md] |
| Missing manual gate disclosure | Repudiation | Bắt buộc `human_needed` cho non-auto-verifiable checks [VERIFIED: D-06 + 44-VERIFICATION.md] |

## Sources

### Primary (HIGH confidence)
- `.planning/phases/47-verification-backfill-v1-5/47-CONTEXT.md` - locked decisions D-01..D-11, scope, requirement policy.
- `.planning/v1.5-MILESTONE-AUDIT.md` - orphan requirements list, missing verification evidence rules, gap baseline.
- `.planning/REQUIREMENTS.md` - requirement definitions + current traceability status (Pending/Done).
- `.planning/config.json` - `workflow.nyquist_validation=true`.
- `.planning/phases/40-.../40-VERIFICATION.md`, `.planning/phases/44-.../44-VERIFICATION.md`, `.planning/phases/45-.../45-VERIFICATION.md` - canonical verification format patterns.
- `.planning/phases/26.../26-01-PLAN.md`, `26-01-SUMMARY.md`, `26-VALIDATION.md` - NOTIF/STRAT evidence source.
- `.planning/phases/28.../28-01-PLAN.md`, `28-01-SUMMARY.md` - ORDER-04/05/06 evidence source.
- `.planning/phases/29.../29-01-SUMMARY.md` - ORDER-07 evidence source.
- `.planning/phases/31.../31-01-PLAN.md`, `31-01-SUMMARY.md`, `31-VALIDATION.md` - TRADE-03/04 evidence source.
- `.planning/phases/32.../32-PLAN.md`, `32-01-SUMMARY.md`; `.planning/phases/33.../33-01-PLAN.md`, `33-01-SUMMARY.md` - context for missing verification artifacts.
- `CLAUDE.md` - project constraints and process requirements.

### Secondary (MEDIUM confidence)
- Local environment checks: `python3 --version`, `pytest --version`, `node --version`, `npm --version`.

### Tertiary (LOW confidence)
- None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - toàn bộ dựa trên artifact/contract đang tồn tại trong repo.
- Architecture: HIGH - pattern verification đã được dùng thực tế ở nhiều phase gần đây.
- Pitfalls: HIGH - trực tiếp suy ra từ audit gaps + locked guardrails.

**Research date:** 2026-04-20
**Valid until:** 2026-05-20 (30 ngày, domain ổn định dạng process/docs)
