---
wave: 1
depends_on: []
files_modified:
  - services/aureus-signal/engine/strategies/template.py
  - services/aureus-signal/tests/test_template_strategy.py
autonomous: true
requirements_addressed:
  - SEQ-01
  - SEQ-02
---

# Phase 14 Plan: Sequence Engine Foundation

<objective>
Refactor `TemplateStrategy._evaluate_sequence` into an Event Pattern Matching State Machine ($O(1)$) per `14-CONTEXT.md`, supporting `reset_signals`, `max_wait` (as candle index difference), and optional steps (`required: False`), with state persisted in `state_obj.strategy_progress`.
</objective>

## Tasks

### 1. Refactor TemplateStrategy._evaluate_sequence
<read_first>
- services/aureus-signal/engine/strategies/template.py
- .planning/phases/14-sequence-engine-foundation/14-CONTEXT.md
- services/aureus-signal/engine/state.py
</read_first>
<action>
1. Replace the `while search_ptr < len(history):` loop in `TemplateStrategy._evaluate_sequence` with an O(1) state evaluator.
2. Read the current machine state from `state_obj.strategy_progress.get(self.name, {})`. Default initialize.
3. Process rules in exact priority for the latest signal at `history[-1]`.
4. Update `current_step_index`, `origin_timestamp`, `matched_timestamps`. Handle optional steps iteratively if missed.
5. Emulate legacy response dict structure ensuring `StrategyRegistry` doesn't break.
</action>
<acceptance_criteria>
- `services/aureus-signal/engine/strategies/template.py` contains no `while search_ptr < len(history)` loop in `_evaluate_sequence`.
- Evaluation only acts on the latest signal instead of full array iteration.
- Handled properly the `reset_signals`, `max_wait` (by index dif), and Optional missing.
</acceptance_criteria>

### 2. Create Unit Tests for the state machine
<read_first>
- services/aureus-signal/engine/strategies/template.py
- .planning/phases/14-sequence-engine-foundation/14-CONTEXT.md
</read_first>
<action>
1. Create `services/aureus-signal/tests/test_template_strategy.py`.
2. Mock `state_obj.strategy_progress` and test: Exact standard step match sequence, exact simultaneous reset, candle `max_wait` timeout execution, and single-tick optional step jump.
</action>
<acceptance_criteria>
- `services/aureus-signal/tests/test_template_strategy.py` explicitly tests the 4 scenarios mentioned in `14-CONTEXT.md`.
- `python -m pytest services/aureus-signal/tests/test_template_strategy.py` exits successfully with `0`.
</acceptance_criteria>
