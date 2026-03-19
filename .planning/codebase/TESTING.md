# TESTING

## Testing Toolchain

- **Python testing framework:** `pytest`.
  - declared in `services/aureus-nautilus-node/requirements.txt`
- **Linting:** `ruff`.
- **Type checking:** `mypy`.
- **CI execution target:** GitHub Actions workflow for nautilus node quality.
  - `.github/workflows/aureus-nautilus-node-quality.yml`

## Current Automated Quality Gate

Workflow: `.github/workflows/aureus-nautilus-node-quality.yml`

Runs on changes to `services/aureus-nautilus-node/**` and executes:

1. dependency install (`pip install -r requirements.txt`)
2. `python -m pytest -q`
3. `python -m ruff check .`
4. targeted `python -m mypy ...`

This indicates mature quality enforcement for at least one critical execution service.

## Test Location and Patterns

## Nautilus Node Tests

- Location: `services/aureus-nautilus-node/tests/`
- Example file: `services/aureus-nautilus-node/tests/test_execution_risk_controls.py`
- Focus observed:
  - risk-control behavior
  - strict SL/TP validation
  - duplicate trace-id suppression
  - contingent order generation expectations

## Nautilus Bridge Tests

- Location: `services/aureus-nautilus-bridge/tests/`
- Example file: `services/aureus-nautilus-bridge/tests/test_bridge_idempotency.py`
- Focus observed:
  - idempotency and duplicate suppression
  - lifecycle transition emissions
  - event payload version and fields
  - non-order event skip behavior

## Test Style Conventions

- Predominantly unit-level tests with local helper fakes/mocks.
- Heavy use of lightweight adapters and synthetic payloads to isolate behavior.
- Async behavior often tested via local event loops (`asyncio.new_event_loop()` or `asyncio.run`).

## Coverage Observations

- Execution-path quality appears strongest in nautilus-related services.
- Broader repository-wide coverage could not be confirmed from sampled files alone.
- Frontend test tooling was not observed in sampled dashboard `package.json` scripts (lint present, no explicit test script shown).

## Testing Risks / Gaps

- CI workflow currently appears scoped to nautilus node module; cross-service regression gates may be uneven.
- End-to-end verification for stream contracts across gateway → signal → bridge → dashboard is not explicit in sampled tests.
- No centralized coverage reporting surface identified in inspected files.

## Recommended Test Investigation Targets

- `services/aureus-gateway/` for ingestion contract tests
- `services/aureus-signal/` for strategy + AI decision pipeline tests
- `services/aureus-dashboard/api/` for API contract/integration tests
- frontend UI behavior tests under `services/aureus-dashboard/web/`
