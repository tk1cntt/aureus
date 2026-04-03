---
phase: "15.11"
plan: "01"
title: "Deterministic Pulse Context and Prompt Stabilization"
wave: 1
depends_on: [15.10-03]
files_modified:
  - .planning/phases/15.11-optimize-llm-pulse-context/15.11-CONTEXT.md
  - .planning/phases/15.11-optimize-llm-pulse-context/15.11-RESEARCH.md
  - .planning/phases/15.11-optimize-llm-pulse-context/15.11-VALIDATION.md
  - services/aureus-signal/engine/ai_validator.py
  - services/aureus-signal/scripts/pulse_prompt_cli.py
  - services/aureus-signal/tests/fixtures/pulse_log_signal_normalize.json
  - services/aureus-signal/tests/test_ai_validator_pulse_context.py
  - services/aureus-signal/tests/test_pulse_prompt_cli.py
autonomous: true
requirements_addressed: [DETERMINISTIC-PULSE-CONTEXT]
---

<objective>
Tái thiết kế payload của `build_pulse_context` và system prompt của `generate_pulse` để narrative pulse ổn định ở tần suất cao, bám chặt anchor kỹ thuật từ 60 record `log_signal_normalize` mới nhất.
</objective>

<must_haves>
- Payload deterministic với khối thông tin cố định, thứ tự cố định, độ dài giới hạn
- Prompt quy định rõ anti-creativity drift và anchor-priority
- Giữ nguyên output JSON phẳng (`narrative`, `sentiment`, `aci`, `debate_log`)
- Có regression tests cho context shape, parser contract, fallback path
- Có script standalone để test prompt/context từ JSON `log_signal_normalize` mà không cần chạy full engine
</must_haves>

---

<task id="15.11-01-T1" title="Refactor pulse context payload into deterministic anchor blocks">
<read_first>
- services/aureus-signal/engine/ai_validator.py
- .planning/phases/15.11-optimize-llm-pulse-context/15.11-CONTEXT.md
- .planning/phases/15.11-optimize-llm-pulse-context/15.11-RESEARCH.md
</read_first>
<action>
1. Bổ sung extractor cho normalized history window 60 item với field guards.
2. Thiết kế payload text theo fixed sections (`PULSE_META`, `ANCHOR_WINDOW`, `STRUCTURE_ANCHORS`, `LIQUIDITY_ANCHORS`, `METRIC_ANCHORS`, `INSTRUCTION_GUARD`).
3. Đảm bảo output `build_pulse_context` deterministic với cùng input state.
</action>
<acceptance_criteria>
- Context luôn có đủ section cố định theo đúng thứ tự
- Không phụ thuộc vào chuỗi text tự do từ field thiếu chuẩn
</acceptance_criteria>
</task>

<task id="15.11-01-T2" title="Stabilize generate_pulse prompt while preserving flat JSON contract">
<read_first>
- services/aureus-signal/engine/ai_validator.py
- D:/Aureus/chart-analyst-skill.txt
</read_first>
<action>
1. Viết lại system prompt theo hướng institutional template, bias-first, evidence-first.
2. Giữ chặt quy tắc output JSON phẳng cho `debate_log` string fields.
3. Củng cố fallback parse guard khi LLM response thiếu key hoặc lệch type.
</action>
<acceptance_criteria>
- Không thay đổi downstream contract keys
- Prompt có rule rõ cho recency + no-new-claim-without-anchor
</acceptance_criteria>
</task>

<task id="15.11-01-T3" title="Add pulse-context tests for stability and fallback behavior">
<read_first>
- services/aureus-signal/tests/
- .planning/phases/15.11-optimize-llm-pulse-context/15.11-VALIDATION.md
</read_first>
<action>
1. Tạo `test_ai_validator_pulse_context.py` với fixtures state giả lập normalized history.
2. Thêm test cho `build_pulse_context` section order + bounded window + deterministic string anchors.
3. Thêm async tests cho `generate_pulse` parsing và `analyze_market` fallback metadata.
</action>
<acceptance_criteria>
- Test file mới bao phủ cả context builder và pulse parser flow
- Quick/full commands trong validation chạy xanh
</acceptance_criteria>
</task>

---

<verification>
1. `Get-ChildItem "D:/Aureus/.planning/phases/15.11-optimize-llm-pulse-context/*"`
2. `python -m pytest services/aureus-signal/tests/test_pulse_prompt_cli.py -q`
3. `python -m pytest services/aureus-signal/tests/test_ai_validator_pulse_context.py services/aureus-signal/tests/test_pulse_prompt_cli.py services/aureus-signal/tests/test_signal_contract_normalization.py services/aureus-signal/tests/test_state_snapshot.py -q`
</verification>
