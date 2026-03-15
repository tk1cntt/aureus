# Story 1.1: Standardized Logging Pattern Across Services

Status: ready-for-dev

## Story

As a Developer,
I want to implement a standardized, sequenced, and prefixed logging pattern across all services,
so that I can trace execution flow across the entire system with clear context about symbols and functions.

## Acceptance Criteria

1. Logger name follow the pattern: `aureus-<service>.<module>` (e.g., `aureus-signal.gap-detector`).
2. Each log entry must be prefixed with `[symbol] [function_name]` where applicable.
3. Within functions, logs must be sequenced like `1...`, `2...`, etc., to trace the execution flow.
4. The error logs in catch blocks must also follow this pattern.
5. Apply this pattern to all `.py` files in the `services/` directory.

## Tasks / Subtasks

- [ ] Task 1: Update `aureus-signal` service logs (AC: 1, 2, 3, 4, 5)
  - [ ] Update `engine/gap_detector.py`
  - [ ] Update `engine/live_engine.py`
  - [ ] Update `engine/manager.py`
  - [ ] Update `engine/signal_factory.py`
  - [ ] Update `engine/signals/*.py`
  - [ ] Update other files in `aureus-signal`
- [ ] Task 2: Update `aureus-gateway` service logs (AC: 1, 2, 3, 4, 5)
  - [ ] Update `main.py` and other modules
- [ ] Task 3: Update `aureus-db-writer` service logs (AC: 1, 2, 3, 4, 5)
  - [ ] Update `main.py` and other modules
- [ ] Task 4: Update `aureus-dashboard` service logs (AC: 1, 2, 3, 4, 5)
  - [ ] Update `api/main.py` and other modules
- [ ] Task 5: Update `aureus-ai-worker` service logs (AC: 1, 2, 3, 4, 5)
  - [ ] Update `worker.py` and other modules

## Dev Notes

- Architecture Pattern: Standardized logging as defined in `architecture.md`.
- Prefix Pattern: `[symbol] [function_name]`. If symbol is not available, use `[GLOBAL]` or omit if appropriate but prefer consistency.
- Sequence: `1...`, `2...` etc. Reset sequence per function call if possible, or maintain within a logical block.
- Service names: `aureus-signal`, `aureus-gateway`, `aureus-db-writer`, `aureus-dashboard-api`, `aureus-ai-worker`.

### Project Structure Notes

- Services are located in `services/`.
- Each service has its own logging configuration in `main.py` or equivalent.

### References

- [Source: docs/planning-artifacts/architecture.md#Section-Implementation-Patterns]

## Dev Agent Record

### Agent Model Used

Antigravity (Gemini 2.0)

### Debug Log References

### Completion Notes List

### File List
