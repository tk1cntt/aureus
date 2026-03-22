# CONVENTIONS

## Language and Style Conventions

## Python Service Conventions

- Predominantly async Python in service entrypoints and workers.
  - `services/aureus-nautilus-bridge/main.py`
  - `services/aureus-dashboard/api/main.py`
- `main.py` frequently acts as top-level executable module.
- Type hints are used in selected modules (stronger in nautilus node/bridge components).
  - `services/aureus-nautilus-node/main.py`

## Naming Conventions

- Service/container naming aligns with `aureus-*` prefix.
- Redis namespace uses `aureus:` prefix with semantic segments.
- Function names are snake_case for Python; classes are PascalCase.
  - `BridgeProcessor`, `AureusNautilusBridge`, `RuntimeHealth`

## Logging and Observability Practices

- Logging initialized at module start with env-driven `LOG_LEVEL` and optional file path.
  - `services/aureus-dashboard/api/main.py`
  - `services/aureus-signal/main.py`
- Many log messages include coarse tags (`[GLOBAL]`, symbol tags, function identifiers).
  - strong in `services/aureus-dashboard/api/main.py`

## Error Handling Patterns

- Pattern 1: Fail-soft loops in long-running workers, often catching broad exceptions and retrying.
  - bridge run loop in `services/aureus-nautilus-bridge/main.py`
- Pattern 2: API endpoints use HTTPException for user-facing failures.
  - `services/aureus-dashboard/api/main.py`
- Pattern 3: Defensive fallback returns (e.g., empty states when Redis key missing).
  - `get_symbol_state` in `services/aureus-dashboard/api/main.py`

## Event/Data Contract Conventions

- Events commonly carry `type` + `data` envelope when emitted to streams.
  - bridge publish format in `services/aureus-nautilus-bridge/main.py`
- Symbol-scoped and trace-scoped IDs are central to deduplication and lifecycle transitions.
  - bridge processor and tests in `services/aureus-nautilus-bridge/tests/test_bridge_idempotency.py`

## Frontend Conventions (Observed)

- Next.js scripts standardize local workflow (`dev`, `build`, `start`, `lint`).
  - `services/aureus-dashboard/web/package.json`
- TypeScript and ESLint are declared; component-level conventions were not deeply sampled in this pass.

## Quality Tooling Conventions

- Nailed-down quality gate exists for nautilus node service:
  - `pytest`
  - `ruff`
  - `mypy` with explicit targets
  - `.github/workflows/aureus-nautilus-node-quality.yml`

## Inconsistencies to Watch

- Type rigor varies by service; some modules are strongly typed while others are dynamic.
- Error handling often uses broad `except Exception`, which is pragmatic for workers but can hide root causes.
- Logging style is not fully standardized (mix of formatted f-strings and `%s` interpolation patterns).
