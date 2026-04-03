---
plan_id: "22-01"
status: complete
key-files.created: 
  - services/aureus-signal/engine/providers/__init__.py
  - services/aureus-signal/engine/providers/base.py
key-files.modified: []
key-links: []
---

# Plan 22-01 Summary

Defined two abstract base classes (`MarketDataProvider`, `DecisionProvider`) and one data model (`DecisionSignal`) in a new `providers/` package. These interfaces establish the contract for future plug-and-play modules without breaking the core execution loop.

## What Was Done
- Created `services/aureus-signal/engine/providers/__init__.py` to re-export standard interfaces.
- Created `services/aureus-signal/engine/providers/base.py` containing:
  - `DecisionSignal` dataclass containing canonical fields.
  - `MarketDataProvider` abstract class with streaming `subscribe` and `get_historical` mechanisms.
  - `DecisionProvider` abstract class with asynchronous `get_decision` capability.

## Self-Check: PASSED
- `__init__.py` exposes correct types.
- Both ABCs created using Python's `abc.ABC`.
- `DecisionSignal` covers all requested fields.
- `python -c` verification tests imported successfully.
