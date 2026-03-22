# PROJECT

## What This Is
A planning control document for the current Aureus milestone. It defines the active objective, expected value, and requirement sources used by the GSD workflow.

## Core Value
- Improve signal decision quality with deterministic, testable behavior.
- Prevent regression through explicit integration contracts and layered tests.
- Optimize performance only after correctness parity is preserved.

## Current Milestone: v1.2 Strategy Sequence Engine

**Goal:** Overhaul the Strategy Engine to rely purely on config-driven sequences, deprecating hardcoded logic and implementing robust state-aware sequence matching.

**Target features:**
- Production-ready sequence evaluation in TemplateStrategy.
- Support for complex time and reset constraints.
- Migration of legacy hard-coded strategies into unified `sequence` structures.

## Archived Milestones
**v1.1 Signal Optimization (Shipped 2026-03-22)**
- Toàn bộ tín hiệu lõi đã được Modular hóa.
- Cover 100% bằng Unit tests và Integration tests.
- Hệ thống phòng thủ OOM (Garbage Collection 1500 nến) hoạt động minh bạch 5h sáng hàng ngày.

<details>
<summary><b>Archived: v1.1 Signal Optimization</b></summary>

**Goal:** Improve signal decision accuracy and deterministic behavior first, then optimize performance without changing trading intent.

**Target features:**
- Deterministic signal parity hardening across key signal modules
- Correctness-first validation for structure/OB/FVG/sweep/trend outputs
- Performance-safe optimization guarded by parity and regression checks
</details>

## Requirements
- Source of truth: `.planning/REQUIREMENTS.md` (To be created)
- Roadmap and phase mapping: `.planning/ROADMAP.md`

## Notes
- This milestone was initialized from a research-first pass over `services/aureus-signal/engine/signals/*` and current signal tests.
- Existing `.planning` directory had spec files but no prior milestone lifecycle documents.

_Last updated: 2026-03-20_
