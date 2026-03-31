---
phase: "15.15"
plan: "01"
title: "Align strategy behavior with updated tag taxonomy"
wave: 1
depends_on: []
files_modified:
  - .planning/phases/15.15-align-strategy-with-new-tags/15.15-CONTEXT.md
  - .planning/phases/15.15-align-strategy-with-new-tags/15.15-RESEARCH.md
  - services/aureus-signal/engine/event_policy.py
  - services/aureus-signal/engine/strategies/seed_strategies.py
  - services/aureus-signal/engine/strategies/smc_trend_scalping.py
  - services/aureus-signal/tests/test_event_policy.py
autonomous: true
requirements_addressed: [PHASE-15.15-TAG-ALIGNMENT]
---

<objective>
Đồng bộ strategy tags với canonical event-policy taxonomy để bảo toàn hành vi strategy + AI pulse khi tags đã thay đổi.
</objective>

<must_haves>
- Có canonical tag inventory rõ ràng cho strategy-facing usage.
- Không làm mất deterministic ordering của AI trigger events.
- Có backward compatibility có kiểm soát cho legacy tags (nếu còn runtime usage).
- Có regression tests cho mapping + priority + legacy alias handling.
</must_haves>

---

<task id="15.15-01-T1" title="Create canonical tag inventory and identify mismatches">
<read_first>
- services/aureus-signal/engine/event_policy.py
- services/aureus-signal/engine/strategies/seed_strategies.py
- services/aureus-signal/engine/strategies/smc_trend_scalping.py
- .planning/phases/15.15-align-strategy-with-new-tags/15.15-RESEARCH.md
</read_first>
<action>
1. Lập danh sách đầy đủ tags canonical hiện dùng trong `event_policy`.
2. Đối chiếu toàn bộ strategy template tags để đánh dấu mismatches.
3. Chốt quyết định từng mismatch: rename sang canonical hoặc giữ alias compatibility.
</action>
<acceptance_criteria>
- Có bảng mapping canonical/legacy rõ ràng trước khi sửa code.
- Không còn tag strategy “mồ côi” ngoài inventory đã định nghĩa.
</acceptance_criteria>
</task>

<task id="15.15-01-T2" title="Implement strategy-tag alignment with safe compatibility">
<read_first>
- services/aureus-signal/engine/event_policy.py
- services/aureus-signal/engine/strategies/seed_strategies.py
- services/aureus-signal/engine/strategies/smc_trend_scalping.py
</read_first>
<action>
1. Cập nhật strategy tags theo canonical naming đã chốt.
2. Bổ sung alias handling trong `event_policy` nếu cần để tránh breaking behavior.
3. Giữ nguyên semantic behavior của existing strategies (chỉ alignment naming).
</action>
<acceptance_criteria>
- `evaluate_ai_trigger_events` trả về expected events cho cả canonical và alias tags (nếu còn hỗ trợ).
- Không đổi ngưỡng điểm/min_score/trade_execution của strategy templates.
</acceptance_criteria>
</task>

<task id="15.15-01-T3" title="Add regression coverage and verify deterministic ordering">
<read_first>
- services/aureus-signal/tests/test_event_policy.py
- services/aureus-signal/engine/live_engine.py
</read_first>
<action>
1. Bổ sung test cases cho canonical sweep/structure tags và alias compatibility.
2. Bổ sung test bảo vệ ordering theo `_TRIGGER_PRIORITY` khi mixed tags cùng candle.
3. Chạy targeted tests để xác nhận không regression mapping.
</action>
<acceptance_criteria>
- Test mapping/priority pass ổn định.
- Có ít nhất 1 test chứng minh behavior khi gặp tag legacy (nếu hỗ trợ alias).
</acceptance_criteria>
</task>

---

<verification>
1. `node ".agent/get-shit-done/bin/gsd-tools.cjs" phase-plan-index "15.15"`
2. `pytest services/aureus-signal/tests/test_event_policy.py -q`
3. `pytest services/aureus-signal/tests/test_sweep_o1.py -q`
</verification>
