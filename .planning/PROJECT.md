# PROJECT

## What This Is
A planning control document for the current Aureus milestone. It defines the active objective, expected value, and requirement sources used by the GSD workflow.

## Core Value
- Improve signal decision quality with deterministic, testable behavior.
- Prevent regression through explicit integration contracts and layered tests.
- Optimize performance only after correctness parity is preserved.

## Current Milestone: v1.1 Signal Optimization

**Goal:** Improve signal decision accuracy and deterministic behavior first, then optimize performance without changing trading intent.

**Target features:**
- Deterministic signal parity hardening across key signal modules
- Correctness-first validation for structure/OB/FVG/sweep/trend outputs
- Performance-safe optimization guarded by parity and regression checks

## Requirements
- Source of truth: `.planning/REQUIREMENTS.md`
- Roadmap and phase mapping: `.planning/ROADMAP.md`

## Active Requirements
- Source of truth: `.planning/REQUIREMENTS.md`
- Roadmap and phase mapping: `.planning/ROADMAP.md`

## Notes
- This milestone was initialized from a research-first pass over `services/aureus-signal/engine/signals/*` and current signal tests.
- Existing `.planning` directory had spec files but no prior milestone lifecycle documents.

_Last updated: 2026-03-20_
