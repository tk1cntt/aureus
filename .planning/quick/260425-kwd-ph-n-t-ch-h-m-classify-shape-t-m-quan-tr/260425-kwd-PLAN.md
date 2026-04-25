---
phase: quick-260425-kwd
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - .planning/quick/260425-kwd-ph-n-t-ch-h-m-classify-shape-t-m-quan-tr/260425-kwd-REPORT.md
autonomous: true
requirements:
  - QUICK-260425-KWD
must_haves:
  truths:
    - "Report xác định đúng vị trí _classify_shape và vai trò của nó trong pipeline TPO."
    - "Report nêu rõ caller/consumer và dữ liệu shape ảnh hưởng tới SIGNAL ALERT/indicator snapshot/strategy context nếu có."
    - "Report chỉ ra các điểm yếu hiện tại của thuật toán classify shape bằng chứng từ source code, không suy đoán vô căn cứ."
    - "Report đề xuất 3-4 phương pháp cải thiện khả thi, có tradeoff và hướng kiểm thử, nhưng không implement production code."
  artifacts:
    - path: ".planning/quick/260425-kwd-ph-n-t-ch-h-m-classify-shape-t-m-quan-tr/260425-kwd-REPORT.md"
      provides: "Báo cáo phân tích _classify_shape và phương án cải thiện"
      min_lines: 80
  key_links:
    - from: "source containing _classify_shape"
      to: ".planning/quick/260425-kwd-ph-n-t-ch-h-m-classify-shape-t-m-quan-tr/260425-kwd-REPORT.md"
      via: "Evidence-backed analysis with file/line references"
      pattern: "_classify_shape"
---

<objective>
Phân tích hàm `_classify_shape`, tầm quan trọng của nó trong hệ thống TPO, và viết report đề xuất 3-4 phương pháp cải thiện classify shape.

Purpose: Người dùng cần hiểu vai trò, rủi ro và hướng cải thiện shape classification trước khi quyết định implement.
Output: Một report markdown duy nhất, không thay đổi production source.
</objective>

<execution_context>
@D:/Aureus/.claude/get-shit-done/workflows/execute-plan.md
@D:/Aureus/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@D:/Aureus/CLAUDE.md
@D:/Aureus/.planning/STATE.md
@D:/Aureus/.planning/quick/260425-aln-ok-vi-t-cho-t-i-h-m-classify-v-i-t-l-nh-/260425-aln-SUMMARY.md
@D:/Aureus/.planning/quick/260425-055-t-i-mu-n-t-i-u-la-i-ca-ch-ti-nh-tpo-serv/260425-055-SUMMARY.md
@D:/Aureus/.planning/quick/260425-bs6-th-c-hi-n-c-i-thi-n-tpo-signal-theo-summ/260425-bs6-SUMMARY.md

Assumptions:
- Đây là quick analysis/report only; không sửa production code, không migration, không test database.
- Vì chỉ đọc và viết report, không cần `gitnexus_impact` trước khi edit symbol; tuy nhiên khi tracing code phải ưu tiên GitNexus theo CLAUDE.md: đọc context, dùng query/context để tìm `_classify_shape` và luồng TPO trước khi đọc source trực tiếp.
- Nếu GitNexus báo index stale, chạy `npx gitnexus analyze` trước rồi tiếp tục.
</context>

<tasks>

<task type="auto">
  <name>Task 1: Locate and trace _classify_shape in TPO flow</name>
  <files>.planning/quick/260425-kwd-ph-n-t-ch-h-m-classify-shape-t-m-quan-tr/260425-kwd-REPORT.md</files>
  <action>Use GitNexus first for code understanding: read `gitnexus://repo/Aureus/context`, run `gitnexus_query({query: "TPO classify shape _classify_shape"})`, then `gitnexus_context({name: "_classify_shape"})` if the symbol exists. After that, read the exact source file(s) containing `_classify_shape` and its direct callers/consumers. Capture file paths, line ranges, inputs/outputs, where shape/confidence are stored or emitted, and how this affects TPO indicator snapshot, Telegram SIGNAL ALERT, and TPO strategy context if present. Do not modify any production source.</action>
  <verify>
    <automated>test -f D:/Aureus/.planning/quick/260425-kwd-ph-n-t-ch-h-m-classify-shape-t-m-quan-tr/260425-kwd-REPORT.md || true</automated>
  </verify>
  <done>Working notes or first report draft identify `_classify_shape` location, signature/behavior, direct callers, downstream consumers, and at least 5 concrete evidence references with paths/line numbers.</done>
</task>

<task type="auto">
  <name>Task 2: Assess current classification weaknesses</name>
  <files>.planning/quick/260425-kwd-ph-n-t-ch-h-m-classify-shape-t-m-quan-tr/260425-kwd-REPORT.md</files>
  <action>Analyze the current heuristic against TPO shape semantics: D balanced/rotation, B double distribution, p short-covering/late upper extension, b long-liquidation/late lower extension. Identify weaknesses that follow from the code, such as threshold brittleness, sensitivity to sparse profiles, ambiguous distributions, session/timeframe effects, confidence calibration, dependency on binning/tick size, and failure modes around outliers or incomplete current sessions. Separate confirmed facts from assumptions. Include why each weakness matters operationally for signal quality and strategy interpretation. Do not propose production code changes inside source files.</action>
  <verify>
    <automated>test -f D:/Aureus/.planning/quick/260425-kwd-ph-n-t-ch-h-m-classify-shape-t-m-quan-tr/260425-kwd-REPORT.md || true</automated>
  </verify>
  <done>Report contains a dedicated weaknesses section with evidence-backed bullets, operational impact, and explicit uncertainty where the code does not prove a claim.</done>
</task>

<task type="auto">
  <name>Task 3: Write final report with 3-4 improvement approaches</name>
  <files>.planning/quick/260425-kwd-ph-n-t-ch-h-m-classify-shape-t-m-quan-tr/260425-kwd-REPORT.md</files>
  <action>Create the final report at the target path. Required structure: `# _classify_shape Analysis Report`; `## Executive Summary`; `## Current Implementation`; `## Role in TPO System`; `## Weaknesses and Risks`; `## Improvement Approaches` with 3-4 approaches; `## Recommendation`; `## Suggested Verification Plan`; `## Sources`. For each approach include concept, data required, expected benefit, risk/tradeoff, implementation complexity, and how to validate. Candidate approaches may include: calibrated heuristic with better distribution metrics, multi-session/timeframe context, rule-based hybrid with detector outputs, and offline labeled replay/backtest calibration. The report must remain analysis-only and explicitly state no production implementation was performed.</action>
  <verify>
    <automated>test -f D:/Aureus/.planning/quick/260425-kwd-ph-n-t-ch-h-m-classify-shape-t-m-quan-tr/260425-kwd-REPORT.md && grep -q "Improvement Approaches" D:/Aureus/.planning/quick/260425-kwd-ph-n-t-ch-h-m-classify-shape-t-m-quan-tr/260425-kwd-REPORT.md && grep -q "_classify_shape" D:/Aureus/.planning/quick/260425-kwd-ph-n-t-ch-h-m-classify-shape-t-m-quan-tr/260425-kwd-REPORT.md</automated>
  </verify>
  <done>`260425-kwd-REPORT.md` exists, contains source-backed analysis of `_classify_shape`, explains TPO importance, includes 3-4 improvement methods with tradeoffs, and contains no production code edits.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Codebase source → report | Executor reads trusted local source and summarizes it into planning documentation. |
| Report → future implementation | Recommendations may influence future production changes but this plan does not implement them. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-quick-260425-kwd-01 | Tampering | Production source files | mitigate | Plan explicitly forbids production source changes; `files_modified` only includes the report. |
| T-quick-260425-kwd-02 | Information Disclosure | Report content | accept | Report references local code behavior only; do not include secrets, env vars, credentials, or private account data. |
| T-quick-260425-kwd-03 | Repudiation | Analysis claims | mitigate | Require file/line sources and separate confirmed facts from assumptions. |
</threat_model>

<verification>
- `git diff --name-only` shows only `D:/Aureus/.planning/quick/260425-kwd-ph-n-t-ch-h-m-classify-shape-t-m-quan-tr/260425-kwd-PLAN.md` and `D:/Aureus/.planning/quick/260425-kwd-ph-n-t-ch-h-m-classify-shape-t-m-quan-tr/260425-kwd-REPORT.md` after execution.
- `test -f D:/Aureus/.planning/quick/260425-kwd-ph-n-t-ch-h-m-classify-shape-t-m-quan-tr/260425-kwd-REPORT.md` succeeds.
- Report includes exactly 3-4 improvement approaches and an explicit recommendation.
</verification>

<success_criteria>
Quick task is complete when the report explains where `_classify_shape` lives, how it matters to TPO outputs/strategy interpretation, what current weaknesses exist, and which 3-4 improvement paths are worth considering next, without implementing code.
</success_criteria>

<output>
After completion, create `.planning/quick/260425-kwd-ph-n-t-ch-h-m-classify-shape-t-m-quan-tr/260425-kwd-SUMMARY.md`.
</output>
