# Story 3.1: Persistent Time-Map Storage in SymbolState

Status: review

## Story

As a system developer,
I want the `SymbolState` to maintain a persistent mapping of timestamps to indices,
So that I don't have to rebuild this map on every market update.

## Acceptance Criteria

1. **Initial State**: A new instance of `SymbolState` includes an empty `t_map` dictionary.
2. **Reset Logic**: Calling `reset()` on `SymbolState` clears the `t_map`.
3. **Accessibility**: `t_map` is accessible to signal engines via the `state_obj`.
4. **Persistence**: `t_map` is included in `to_dict` and restored in `from_dict` (optional but recommended for state snapshots).

## Tasks / Subtasks

- [ ] Task 1: Add `t_map` to `SymbolState` initialization (AC: 1, 2)
  - Files
    - Modify: `services/aureus-signal/engine/state.py`
    - Test: `services/aureus-signal/tests/test_state_management.py` (New)
  - [ ] Step 1: Create a test ensuring `SymbolState` has `t_map` after init and reset.
  - [ ] Step 2: Run test to verify it fails (missing attribute).
    - Command: `python3 -m pytest services/aureus-signal/tests/test_state_management.py`
  - [ ] Step 3: Add `self.t_map: Dict[int, int] = {}` to `SymbolState.reset()`.
  - [ ] Step 4: Run test to verify it passes.

- [ ] Task 2: Implement Serialization for `t_map` (AC: 4)
  - Files
    - Modify: `services/aureus-signal/engine/state.py`
  - [ ] Step 1: Update `from_dict` to load `t_map` (using `.get('t_map', {})`).
  - [ ] Step 2: Update `to_dict` to include `t_map` in the returned dictionary.
  - [ ] Step 3: Add a test case in `test_state_management.py` for serialization parity.

## Dev Notes

- **Naming**: Use `t_map` (snake_case) as per project conventions.
- **Type Hinting**: Ensure `Dict[int, int]` is used.
- **Micro-caching Phase**: This story only provides the *storage*. The logic to *use* and *efficiently update* it belongs to Story 3.2.

### Project Structure Notes
- `services/aureus-signal/engine/state.py` is the target for `SymbolState` modifications.

### References
- [Architecture: State Management Patterns](file:///d:/Aureus/docs/planning-artifacts/architecture.md#L250)
- [Signal Design Analysis: Performance Bottlenecks](file:///d:/Aureus/docs/signals/signal_design_analysis.md#L45)

## Dev Agent Record

### Agent Model Used
{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
