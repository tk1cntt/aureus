# STRUCTURE

## Repository Top Level

Key top-level locations:

- `.agent/` — local agent workflows, skills, and automation assets.
- `.github/` — CI workflows (currently includes service-specific quality gate workflows).
- `services/` — primary application services (core implementation area).
- `monitoring/` — Prometheus/Grafana config and dashboards.
- `docs/` — runbooks, plans, reports, and generated artifacts.
- `mql5/` — MQL-related integration assets.
- `scripts/` — operational/dev scripts.
- `docker-compose.dev.yml` and `docker-compose.prod.yml` — runtime orchestration.

## Services Directory Layout

`services/` contains these modules:

- `services/aureus-gateway/`
- `services/aureus-signal/`
- `services/aureus-db-writer/`
- `services/aureus-dashboard/`
- `services/aureus-nautilus-node/`
- `services/aureus-nautilus-bridge/`
- `services/aureus-bridge-metrics-exporter/`
- `services/aureus-ai-worker/`
- `services/nautilus_trader/`
- `services/brain/`

## Dashboard Substructure

- Backend API: `services/aureus-dashboard/api/`
  - FastAPI entrypoint: `services/aureus-dashboard/api/main.py`
  - deps: `services/aureus-dashboard/api/requirements.txt`
- Frontend Web: `services/aureus-dashboard/web/`
  - scripts/deps: `services/aureus-dashboard/web/package.json`

## Naming and Organization Patterns

## Service Naming

- Prefix pattern: `aureus-*` for service modules and containers.
- Environment-specific compose services use `-dev` suffix.
  - example: `aureus-nautilus-bridge-dev`

## File and Module Organization

- Python services often use `main.py` as entrypoint with adjacent helpers.
  - `services/aureus-nautilus-bridge/main.py`
  - `services/aureus-nautilus-node/main.py`
- Bridge domain logic split into semantic modules:
  - `mapper.py`
  - `reconciliation.py`

## Data Namespace Conventions

- Redis keys/streams use `aureus:` prefix and colon-separated scopes.
  - `aureus:stream:{symbol}:orders`
  - `aureus:stream:{symbol}:execution`
  - `aureus:state:{symbol}`

## Testing and Quality Location Pattern

- Service-local tests under each service.
  - `services/aureus-nautilus-node/tests/`
  - `services/aureus-nautilus-bridge/tests/`
- CI workflow currently targets nautilus node quality gate.
  - `.github/workflows/aureus-nautilus-node-quality.yml`

## Operational Config Layout

- Compose for stack wiring: `docker-compose.dev.yml`.
- Monitoring-specific files under `monitoring/prometheus/` and `monitoring/grafana/`.
- Logs mounted into shared `logs/` directory in dev compose.

## Practical Navigation Starting Points

For common tasks, start in:

- Runtime wiring: `docker-compose.dev.yml`
- Event/bridge behavior: `services/aureus-nautilus-bridge/main.py`
- Trading node lifecycle: `services/aureus-nautilus-node/main.py`
- API contract behavior: `services/aureus-dashboard/api/main.py`
- UI implementation: `services/aureus-dashboard/web/`

## Structure Risks

- `services/` has several modules with varying maturity; conventions are mostly implicit.
- No single root architecture index file surfaced in this pass; discovery depends on service-by-service inspection.
