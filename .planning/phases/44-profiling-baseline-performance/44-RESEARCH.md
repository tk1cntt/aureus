# Phase 44: Tối ưu cách tính toán khi có nhiều signal với nhiều symbol - Research

**Researched:** 2026-04-18
**Domain:** Python signal-engine performance optimization (StructureSignal, multi-signal/multi-symbol)
**Confidence:** MEDIUM

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **Mục tiêu:** Tối ưu `StructureSignal` để giảm latency/candle nhưng **không thay đổi logic trading hiện tại** (strict parity). [VERIFIED: D:/Aureus/.planning/phases/44-profiling-baseline-performance/44-CONTEXT.md]
- **Đề xuất chính đã chốt trong context:** triển khai theo lộ trình **A + D trước**, sau đó mới cân nhắc B. [VERIFIED: D:/Aureus/.planning/phases/44-profiling-baseline-performance/44-CONTEXT.md]
- **Runtime safety bắt buộc:** có feature flag `AUREUS_STRUCTURE_OPT_MODE=off|shadow|on`, shadow log mismatch đủ context, mismatch thì auto-fallback old path. [VERIFIED: D:/Aureus/.planning/phases/44-profiling-baseline-performance/44-CONTEXT.md]
- **Performance gate:** mục tiêu giảm `structure_processor` avg_ms tối thiểu 40% trong điều kiện tương đương. [VERIFIED: D:/Aureus/.planning/phases/44-profiling-baseline-performance/44-CONTEXT.md]

### Claude's Discretion
- CONTEXT.md hiện tại không có section tiêu đề `## Claude's Discretion`; planner nên hiểu là không có quyền mở rộng ngoài các quyết định đã nêu phía trên. [VERIFIED: D:/Aureus/.planning/phases/44-profiling-baseline-performance/44-CONTEXT.md]

### Deferred Ideas (OUT OF SCOPE)
- CONTEXT.md hiện tại không có section tiêu đề `## Deferred Ideas`; mặc định chỉ làm đúng phạm vi tối ưu StructureSignal + parity/safety đã mô tả. [VERIFIED: D:/Aureus/.planning/phases/44-profiling-baseline-performance/44-CONTEXT.md]
</user_constraints>

## Project Constraints (from CLAUDE.md)

- Mọi trao đổi dùng tiếng Việt. [VERIFIED: D:/Aureus/CLAUDE.md]
- Nếu command lỗi, tham khảo `RUN_SERVICES.md`. [VERIFIED: D:/Aureus/CLAUDE.md]
- Nếu sửa `AureusProvider.mq5`, phải theo `mql5/Build_Rules.md` (phase này không nhắm file đó). [VERIFIED: D:/Aureus/CLAUDE.md]
- Ưu tiên thay đổi tối thiểu, không mở rộng scope, không refactor lan man. [VERIFIED: D:/Aureus/CLAUDE.md]
- Với task chỉnh symbol/function/class: phải chạy `gitnexus_impact` trước khi sửa; trước commit phải chạy `gitnexus_detect_changes`. [VERIFIED: D:/Aureus/CLAUDE.md]
- Với refactor/rename: phải dùng workflow GitNexus tương ứng (`gitnexus_context`, `gitnexus_impact`, `gitnexus_rename` nếu rename). [VERIFIED: D:/Aureus/CLAUDE.md]

## Summary

Phase 44 là phase tối ưu hiệu năng cho `StructureSignal` trong `services/aureus-signal`, nhưng có ràng buộc cứng là **không đổi semantic trading**. Code hiện tại của `StructureSignal` vẫn có nhiều vòng lặp Python + truy cập DataFrame theo `iloc/iterrows`, đúng với nhận định trong CONTEXT rằng hướng A (array access) là bước an toàn nhất trước. [VERIFIED: D:/Aureus/services/aureus-signal/engine/signals/structure.py] [VERIFIED: D:/Aureus/.planning/phases/44-profiling-baseline-performance/44-CONTEXT.md]

Hạ tầng baseline profiling đã được chuẩn bị ở phase 44.0 (theo các plan đã lưu): đã có luồng đo timing và summary để xác định bottleneck, nên Phase 44 nên bám chiến lược triển khai từng bước nhỏ, đo trước/sau từng thay đổi và khóa bằng parity tests + shadow mode trước khi bật `on`. [VERIFIED: D:/Aureus/.planning/phases/43.1-toi-uu-cach-tinh-toan-khi-co-nhieu-signal-voi-nhieu-symbol/44.0-01-PLAN.md] [VERIFIED: D:/Aureus/.planning/phases/43.1-toi-uu-cach-tinh-toan-khi-co-nhieu-signal-voi-nhieu-symbol/44.0-02-PLAN.md]

Về stack, repo đang pin `numpy==2.4.2` và `pandas==3.0.1` trong `services/aureus-signal/requirements.txt`, nhưng probe package index cho thấy latest công khai hiện là `numpy 2.2.6`, `pandas 2.3.3` tại thời điểm nghiên cứu; đây là rủi ro cần xử lý trong kế hoạch (xác nhận mirror nội bộ hay sửa pin). [VERIFIED: D:/Aureus/services/aureus-signal/requirements.txt] [VERIFIED: pip index command output]

**Primary recommendation:** Giữ đúng roadmap **A + D**: tối ưu data-access trong `StructureSignal` bằng array-centric reads, triển khai dual-path parity (`off|shadow|on`) và chỉ promote `on` sau khi replay + shadow mismatch = 0 trong cửa sổ quan sát đã định. [VERIFIED: D:/Aureus/.planning/phases/44-profiling-baseline-performance/44-CONTEXT.md]

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.10.11 (runtime probe) | Runtime chính của services signal | Runtime hiện có sẵn trên máy chạy lệnh nghiên cứu. [VERIFIED: python3 --version] |
| pandas | pinned `3.0.1` (repo), latest index `2.3.3` | Window DataFrame + scan theo cột OHLC/timestamp | Code hiện tại của `StructureSignal` phụ thuộc DataFrame API; hướng A vẫn giữ pandas ở boundary. [VERIFIED: requirements.txt + structure.py + pip index] |
| numpy | pinned `2.4.2` (repo), latest index `2.2.6` | Tối ưu truy cập mảng (`to_numpy`) cho hot path | Hướng A trong CONTEXT yêu cầu chuyển iloc/iterrows sang array access. [VERIFIED: CONTEXT + requirements.txt] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| redis (python) | pinned `7.2.0`, latest index `7.4.0` | Stream profiling / progress keys | Dùng cho shadow/parity telemetry và profiling summary pipeline. [VERIFIED: requirements.txt + signal_computer.py + 44.0 plans] |
| pydantic | pinned `2.12.5`, latest index `2.13.2` | Validation models/config (nếu có) | Dùng khi cần schema hóa payload parity/mismatch để tránh drift định dạng. [ASSUMED] |
| pytest | 9.0.2 (runtime probe) | Unit/replay/parity test gate | Là test runner hiện detect được trong môi trường. [VERIFIED: pytest --version] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| A (array access) | B (incremental delta scan) | B có tiềm năng nhanh hơn trên stream dài nhưng tăng rủi ro lệch state edge-case. [VERIFIED: 44-CONTEXT.md] |
| A/B Python-level | E (Numba/Cython/Rust) | Trần hiệu năng cao hơn nhưng tăng độ phức tạp build/deploy/debug. [VERIFIED: 44-CONTEXT.md] |

**Installation:**
```bash
pip install -r services/aureus-signal/requirements.txt
```

**Version verification:**
- Đã verify thực tế bằng package index: numpy/pandas/redis/pydantic. [VERIFIED: pip index command output]
- Cần user xác nhận nguồn package (PyPI public vs private mirror) trước khi planner lock dependency policy vì pins hiện tại cao hơn bản public query được. [VERIFIED: requirements.txt + pip index command output]

## Architecture Patterns

### Recommended Project Structure
```text
services/aureus-signal/
├── engine/signals/structure.py     # Hot-path StructureSignal cần optimize A trước
├── engine/state.py                 # SymbolState: transient_signals/obs/swing_points contract
├── engine/manager.py               # Window update + profiling hooks (phase 44.0)
├── tests/                          # parity/perf regression tests
└── tools/                          # profiling summary utilities
```

### Pattern 1: Contract-preserving optimization (A-first)
**What:** Chỉ đổi cách đọc dữ liệu (DataFrame -> arrays) nhưng giữ nguyên điều kiện breakout/mitigation/OB.
**When to use:** Khi mục tiêu là giảm latency nhưng parity logic là ràng buộc cứng.
**Example:**
```python
# Source: D:/Aureus/services/aureus-signal/engine/signals/structure.py
# Current code builds t_map from df['t'].values and still scans loops.
# Phase 44 should extend this approach to replace remaining iloc/iterrows hotspots.
t_values = df['t'].values
t_map = {int(t): i for i, t in enumerate(t_values)}
```

### Pattern 2: Dual-path shadow verifier (D)
**What:** Chạy old/new path song song, so sánh full contract output, mismatch thì fallback old path.
**When to use:** Trước khi bật optimized path trong production.
**Example:**
```python
# Source: D:/Aureus/.planning/phases/44-profiling-baseline-performance/44-CONTEXT.md
# mode in {off, shadow, on}
# shadow: run both, compare, log mismatch with symbol+t+diff fields
# mismatch => fallback old path
```

### Anti-Patterns to Avoid
- **Đổi luôn thuật toán + data-access trong một bước:** khó khoanh vùng lỗi parity. [VERIFIED: 44-CONTEXT.md]
- **So sánh parity thiếu field (chỉ tag/value):** dễ lọt mismatch metadata OB. [VERIFIED: 44-CONTEXT.md]
- **Promote `on` khi chưa có cửa sổ mismatch=0 đủ lớn:** tăng rủi ro lệch production. [VERIFIED: 44-CONTEXT.md]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Percentile latency stats | Tự viết percentile thủ công dễ sai edge cases | `numpy.percentile` hoặc pipeline thống kê đã có từ phase 44.0 | Đã có baseline profiling/summary plan và test tương ứng. [VERIFIED: 44.0-02-PLAN.md] [ASSUMED: numpy.percentile choice] |
| Symbol impact tracing trước refactor | Grep/find-replace thủ công | GitNexus impact/context workflow | CLAUDE.md bắt buộc dùng để kiểm soát blast radius. [VERIFIED: CLAUDE.md] |
| Runtime flag framework phức tạp | Tự dựng config system mới | Dùng feature flag env đơn giản `AUREUS_STRUCTURE_OPT_MODE` | Đã là contract được chốt trong CONTEXT. [VERIFIED: 44-CONTEXT.md] |

**Key insight:** Trong phase này, “đúng trước nhanh sau” là bắt buộc; mọi custom optimization bỏ qua parity/shadow đều là anti-goal. [VERIFIED: 44-CONTEXT.md]

## Common Pitfalls

### Pitfall 1: Numeric/typing drift khi chuyển sang arrays
**What goes wrong:** So sánh break conditions lệch 1 candle do cast float/int khác.
**Why it happens:** DataFrame/Series và ndarray có hành vi type coercion khác nhau.
**How to avoid:** Chuẩn hóa dtype explicit và thêm parity tests theo timestamp biên.
**Warning signs:** CHOCH timestamp lệch dù tag giống nhau. [VERIFIED: 44-CONTEXT.md] [VERIFIED: structure.py]

### Pitfall 2: Comparator drift theo thời gian
**What goes wrong:** Comparator không update theo output contract mới, tạo false-negative parity.
**Why it happens:** Logic business đổi nhưng comparator đứng yên.
**How to avoid:** Lock comparator schema theo `state.transient_signals`, `state.obs`, `state.swing_points` và test contract.
**Warning signs:** Shadow mismatch bất thường sau refactor nhỏ không liên quan logic. [VERIFIED: 44-CONTEXT.md] [VERIFIED: structure.py + state.py]

### Pitfall 3: Dependency pin không khả dụng môi trường thực thi
**What goes wrong:** CI/CD hoặc máy mới không cài được đúng version pinned.
**Why it happens:** Pin trong repo không khớp package index public.
**How to avoid:** Planner thêm bước xác nhận nguồn package/mirror trước khi triển khai.
**Warning signs:** `pip install` fail ngay ở bước setup. [VERIFIED: requirements.txt + pip index output]

## Code Examples

Verified patterns from project sources:

### Structure signal currently mutates transient state contract
```python
# Source: D:/Aureus/services/aureus-signal/engine/signals/structure.py
if isinstance(transient, dict):
    transient["ob_state"] = {
        "active_obs": [
            {
                "top": ob.get("top"),
                "bottom": ob.get("bottom"),
                "ob_type": ob.get("ob_type"),
                "t_start": ob.get("t_start"),
                "status": ob.get("status", "PENDING"),
                "break_counter": ob.get("break_counter", 0),
                "mitigated": ob.get("mitigated", False),
                "t_mitigation": ob.get("t_mitigation", 0),
            }
            for ob in getattr(state_obj, 'obs', [])
        ]
    }
```

### State object contracts affected by parity requirement
```python
# Source: D:/Aureus/services/aureus-signal/engine/state.py
self.obs: List[Dict[str, Any]] = []
self.swing_points: List[Dict[str, Any]] = []
self.transient_signals: Dict[str, Any] = {}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Full DataFrame row-wise access (`iloc`, `iterrows`) for structure logic | A-first optimization direction: keep algorithm, improve data-access path | Chốt trong Phase 44 context (2026-04-17/18) | Giảm latency với rủi ro thấp hơn đổi thuật toán. [VERIFIED: 44-CONTEXT.md + structure.py] |
| Không có baseline profiling đầy đủ | Có profiling instrumentation + summary plans trong 44.0 artifacts | 44.0 plans đã tạo | Có dữ liệu để chọn bottleneck thực thay vì đoán. [VERIFIED: 44.0-01/02 plans] |

**Deprecated/outdated:**
- Cách tiếp cận “optimize by intuition” không có profiling/parity gate là không còn phù hợp cho phase này. [VERIFIED: 44-CONTEXT.md] [ASSUMED: terminology]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Có thể dùng `numpy.percentile` làm chuẩn tính p95/p99 trong toolchain phase này | Don't Hand-Roll | Nếu không dùng numpy percentile thì summary giữa các tool có thể lệch nhẹ |
| A2 | pydantic sẽ được dùng để schema hóa payload parity/mismatch nếu cần | Standard Stack (Supporting) | Nếu không dùng, planner cần chọn cách validation payload khác |
| A3 | “Optimize by intuition” được xem là outdated practice trong team này | State of the Art | Tác động thấp, chủ yếu về wording/policy |

## Open Questions (RESOLVED)

1. **Pins `pandas==3.0.1`, `numpy==2.4.2` lấy từ đâu?** — **RESOLVED**
   - Decision: Giữ nguyên pin trong `services/aureus-signal/requirements.txt` làm **source of truth** cho Phase 44; giả định môi trường chạy phase dùng internal package source tương thích với hai pin này.
   - Enforcement: Không đổi dependency policy trong Phase 44, không hạ version để khớp public index. Nếu setup env mới bị lỗi cài đặt thì ghi nhận là infra/package-source issue ngoài phạm vi plan tối ưu thuật toán.

2. **Nguồn dữ liệu benchmark chuẩn cho gate giảm 40% là gì?** — **RESOLVED**
   - Decision: Chuẩn benchmark dùng **replay dataset cố định, deterministic** trong `services/aureus-signal/tests/test_structure_replay_regression.py`, khóa rõ symbol + time-window ngay trong test fixture để old/new chạy cùng điều kiện.
   - Gate: Dùng cùng process, cùng dataset, assert cứng `optimized_avg_ms <= old_avg_ms * 0.60` (tương đương giảm >=40%).

3. **Tiêu chí promote `shadow -> on` cụ thể theo thời gian bao lâu?** — **RESOLVED**
   - Decision: Chỉ promote `on` khi shadow đạt **mismatch = 0** trên toàn bộ cửa sổ quan sát chuẩn đã chốt trong replay gate và không có parity drift ở `transient_signals`, `obs`, `swing_points`.
   - Rollback rule: Nếu phát sinh bất kỳ mismatch nào trong shadow window thì giữ/rollback về `off` (hoặc old path fallback) và không promote `on` cho đến khi replay + shadow pass lại hoàn toàn.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| python3 | aureus-signal runtime/tests | ✓ | 3.10.11 | — |
| pytest | validation quick/full tests | ✓ | 9.0.2 | — |
| pip3 | dependency install | ✓ | 26.0.1 | — |
| node/npm | gsd-tools workflow scripts | ✓ | node v22.22.0 / npm 11.12.0 | — |
| docker | containerized execution (nếu phase chạy trong container) | ✗ (không detect được) | — | Chạy local Python env |
| redis-cli | live profiling stream inspection | ✗ (không detect được) | — | Dùng integration test/mocked redis client |
| postgres CLI (`pg_isready`/`psql`) | DB connectivity checks | ✗ (không detect được) | — | dùng app-level asyncpg test/mocks |

**Missing dependencies with no fallback:**
- Không có blocker cứng cho coding/test đơn vị của phase 44 (vẫn làm local + mock được). [VERIFIED: environment probe]

**Missing dependencies with fallback:**
- docker, redis-cli, postgres CLI thiếu nhưng có fallback local/mock cho phase planning & unit/replay tests. [VERIFIED: environment probe] [ASSUMED: fallback suitability]

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 [VERIFIED: pytest --version] |
| Config file | `services/aureus-gateway/tests/pytest.ini` (không thấy pytest.ini riêng cho aureus-signal) [VERIFIED: Glob results] |
| Quick run command | `pytest services/aureus-signal/tests/test_ob_numpy.py -q -x` [VERIFIED: file exists] |
| Full suite command | `pytest services/aureus-signal/tests -q -x` [VERIFIED: tests dir exists] |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PROF-01 | Timing per-signal/per-candle additive, không đổi output | unit/regression | `pytest services/aureus-signal/tests/test_profiling_instrumentation.py -k "signal_results or profiling_records_timing or redis_failure" -q -x` | ❌ Wave 0 (theo plan 44.0-01) |
| PROF-02 | Stream profiling theo symbol với guard failure | unit/integration-lite | `pytest services/aureus-signal/tests/test_profiling_instrumentation.py -k "window_manager_times_df_build or logs_every_100_candles" -q -x` | ❌ Wave 0 (theo plan 44.0-01) |
| PROF-03 | Aggregation summary avg/p95/p99 + bottleneck ranking | unit | `pytest services/aureus-signal/tests/test_profile_summary.py -k "aggregation or bottleneck" -q -x` | ❌ Wave 0 (theo plan 44.0-02) |
| PH44-PARITY | Old/new structure output identical + side-effect parity | replay/contract | `pytest services/aureus-signal/tests -k "structure and (parity or ob_numpy or multi_symbol)" -q -x` | ⚠️ Partial (cần thêm parity-specific files) |

### Sampling Rate
- **Per task commit:** `pytest services/aureus-signal/tests -k "structure or ob_numpy or multi_symbol" -q -x`
- **Per wave merge:** `pytest services/aureus-signal/tests -q -x`
- **Phase gate:** full suite trên `services/aureus-signal/tests` xanh + shadow mismatch = 0 theo cửa sổ đã chốt.

### Wave 0 Gaps
- [ ] `services/aureus-signal/tests/test_structure_parity_shadow.py` — contract parity old/new + mismatch fallback
- [ ] `services/aureus-signal/tests/test_structure_mode_flag.py` — validate `off|shadow|on`
- [ ] `services/aureus-signal/tests/test_structure_replay_regression.py` — replay dataset chuẩn cho gate 40%

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | N/A (phase nội bộ signal compute) [ASSUMED] |
| V3 Session Management | no | N/A [ASSUMED] |
| V4 Access Control | yes | Guard feature flag + giới hạn scope fallback sang old path để tránh logic bypass vô ý. [VERIFIED: 44-CONTEXT.md] |
| V5 Input Validation | yes | Validate payload parity/profiling fields trước khi aggregate/compare. [VERIFIED: 44.0-02-PLAN.md] |
| V6 Cryptography | no | Không có crypto primitive mới trong phase này. [VERIFIED: examined relevant files] |

### Known Threat Patterns for Python signal-processor optimization

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malformed profiling payload làm sai aggregation | Tampering | Validate numeric fields, bỏ qua record lỗi có warning. [VERIFIED: 44.0-02-PLAN.md] |
| Shadow overhead gây pipeline chậm | Denial of Service | Bật mode theo flag, đo `_total` latency và rollback về old path khi vượt ngưỡng. [VERIFIED: 44-CONTEXT.md] |
| Partial parity comparator (so thiếu fields) | Repudiation/Tampering | So full contract gồm metadata OB + side effects trọng yếu. [VERIFIED: 44-CONTEXT.md] |

## Sources

### Primary (HIGH confidence)
- `D:/Aureus/.planning/phases/44-profiling-baseline-performance/44-CONTEXT.md` - locked decisions, rollout strategy A+D, risk/pitfalls, runtime safety gates.
- `D:/Aureus/services/aureus-signal/engine/signals/structure.py` - current hot-path implementation and side-effects contract.
- `D:/Aureus/services/aureus-signal/engine/state.py` - runtime state objects affected by parity.
- `D:/Aureus/services/aureus-signal/requirements.txt` - pinned dependency stack.
- `D:/Aureus/.planning/phases/43.1-toi-uu-cach-tinh-toan-khi-co-nhieu-signal-voi-nhieu-symbol/44.0-01-PLAN.md` - profiling instrumentation requirements and commands.
- `D:/Aureus/.planning/phases/43.1-toi-uu-cach-tinh-toan-khi-co-nhieu-signal-voi-nhieu-symbol/44.0-02-PLAN.md` - summary aggregation requirements and commands.
- `D:/Aureus/CLAUDE.md` and `.claude/skills/gitnexus/*/SKILL.md` - project execution constraints.

### Secondary (MEDIUM confidence)
- Runtime probes (`python3 --version`, `pytest --version`, `node --version`, `npm --version`) - environment availability at research time.
- `python3 -m pip index versions {numpy,pandas,redis,pydantic}` - current public index versions for dependency verification.

### Tertiary (LOW confidence)
- Không dùng WebSearch/WebFetch trong nghiên cứu này.

## Metadata

**Confidence breakdown:**
- Standard stack: MEDIUM - stack nội bộ đã verify từ repo + probe, nhưng có lệch pin so với public index cần xác nhận.
- Architecture: HIGH - dựa trực tiếp trên CONTEXT phase và code hiện hành của structure/state.
- Pitfalls: HIGH - đối chiếu đồng thời CONTEXT + implementation hiện tại.

**Research date:** 2026-04-18
**Valid until:** 2026-05-02 (14 ngày, vì phase tối ưu hiệu năng có biến động nhanh)
