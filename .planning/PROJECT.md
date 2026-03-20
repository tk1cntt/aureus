# PROJECT

## Current Milestone: v1.1 Signal Optimization

**Goal:** Improve signal decision accuracy and deterministic behavior first, then optimize performance without changing trading intent.

**Target features:**
- Deterministic signal parity hardening across key signal modules
- Correctness-first validation for structure/OB/FVG/sweep/trend outputs
- Performance-safe optimization guarded by parity and regression checks

## Active Requirements

- Source of truth: `.planning/REQUIREMENTS.md`
- Roadmap and phase mapping: `.planning/ROADMAP.md`

## Notes

- This milestone was initialized from a research-first pass over `services/aureus-signal/engine/signals/*` and current signal tests.
- Existing `.planning` directory had spec files but no prior milestone lifecycle documents.

_Last updated: 2026-03-20_
