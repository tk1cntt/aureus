---
phase: "15.9"
plan: "01"
title: "Enrich Signal History with Semantic Metadata While Preserving Legacy Contract"
wave: 1
depends_on: []
files_modified:
  - .planning/phases/15.9-enrich-signal-history-with-semantic-metadata/15.9-CONTEXT.md
  - .planning/phases/15.9-enrich-signal-history-with-semantic-metadata/15.9-RESEARCH.md
  - .planning/phases/15.9-enrich-signal-history-with-semantic-metadata/15.9-VALIDATION.md
  - services/aureus-signal/engine/state.py
  - services/aureus-signal/engine/live_engine.py
  - services/aureus-signal/engine/backtest_engine.py
  - services/aureus-signal/signal_computer.py
  - services/aureus-signal/engine/ai_validator.py
  - services/aureus-signal/engine/state_snapshot.py
autonomous: true
requirements_addressed: [INTERNAL-SEMANTIC-OBSERVABILITY]
---

<objective>
Bổ sung metadata ngữ nghĩa cho `signal_history` để tăng khả năng diễn giải AI/debug, đồng thời bảo toàn compatibility (`tag`, `t`) cho mọi consumer legacy.
</objective>

<must_haves>
- Metadata chuẩn gồm `category`, `value`, `explain`, `inputs` cho record mới
- Không phá contract cũ (`tag`, `t` vẫn luôn có)
- Đồng bộ producer + consumer theo cùng contract
- Có verification map rõ ràng cho execution
</must_haves>

---

<task id="15.9-01-T1" title="Stabilize state logging contract for semantic metadata">
<read_first>
- services/aureus-signal/engine/state.py
- .planning/phases/15.9-enrich-signal-history-with-semantic-metadata/15.9-CONTEXT.md
</read_first>
<action>
1. Chuẩn hóa `log_signal` để nhận metadata kwargs.
2. Đảm bảo record append luôn có `tag` và `t`.
3. Bổ sung fallback khi metadata không đầy đủ.
</action>
<acceptance_criteria>
- Contract logger chấp nhận metadata mới + không phá caller cũ
- `signal_history` record có shape nhất quán
</acceptance_criteria>
</task>

<task id="15.9-01-T2" title="Align producer call-sites across live/backtest/precompute">
<read_first>
- services/aureus-signal/engine/live_engine.py
- services/aureus-signal/engine/backtest_engine.py
- services/aureus-signal/signal_computer.py
</read_first>
<action>
1. Map output calculators vào `category/value/explain/inputs`.
2. Đồng bộ strategy signal logging theo contract mới.
3. Giảm drift field names giữa các loop xử lý.
</action>
<acceptance_criteria>
- 3 call-sites chính dùng cùng signature ghi signal
- Không còn nhánh ghi metadata lệch chuẩn
</acceptance_criteria>
</task>

<task id="15.9-01-T3" title="Update semantic consumers and snapshot path">
<read_first>
- services/aureus-signal/engine/ai_validator.py
- services/aureus-signal/engine/state_snapshot.py
</read_first>
<action>
1. Ưu tiên narrative từ `explain/category` khi có.
2. Giữ fallback parse từ dữ liệu legacy.
3. Xác nhận serialize/restore không làm mất metadata.
</action>
<acceptance_criteria>
- Consumer đọc metadata an toàn
- Snapshot path giữ đủ trường mở rộng
</acceptance_criteria>
</task>

---

<verification>
1. `Get-ChildItem ".planning/phases/15.9-enrich-signal-history-with-semantic-metadata/*"`
2. `node ".agent/get-shit-done/bin/gsd-tools.cjs" phase-plan-index "15.9"`
3. `pytest tests/test_decision_trace_schema.py tests/test_signal_contract_normalization.py -q`
</verification>
