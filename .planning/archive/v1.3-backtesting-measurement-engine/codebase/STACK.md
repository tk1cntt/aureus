# STACK

## Runtime and Language Mix

- **Primary language:** Python 3.12 for core services and workers.
  - `services/aureus-gateway/main.py`
  - `services/aureus-signal/main.py`
  - `services/aureus-nautilus-node/main.py`
  - `services/aureus-nautilus-bridge/main.py`
  - `services/aureus-dashboard/api/main.py`
- **Frontend language/runtime:** TypeScript + React on Next.js.
  - `services/aureus-dashboard/web/package.json`
- **Infrastructure/config:** Docker Compose, GitHub Actions, Prometheus/Grafana provisioning.
  - `docker-compose.dev.yml`
  - `.github/workflows/aureus-nautilus-node-quality.yml`
  - `monitoring/prometheus/prometheus.yml`

## Backend Frameworks and Libraries

### API and Service Frameworks

- **FastAPI + Uvicorn** for dashboard backend API.
  - `services/aureus-dashboard/api/main.py`
  - `services/aureus-dashboard/api/requirements.txt`
- **Async Redis clients** (`redis.asyncio`) across gateway/bridge/signal/api services.
  - `services/aureus-nautilus-bridge/main.py`
  - `services/aureus-dashboard/api/main.py`
- **Async PostgreSQL access** with `asyncpg`.
  - `services/aureus-dashboard/api/main.py`
  - `services/aureus-signal/requirements.txt`
- **HTTP client integrations** with `httpx` and `requests`.
  - `services/aureus-dashboard/api/main.py`
  - `services/aureus-signal/requirements.txt`

### Signal/Trading/AI Stack

- **Nautilus Trader integration** via node container and runtime wrappers.
  - `services/aureus-nautilus-node/main.py`
  - `docker-compose.dev.yml` (`nautilus_trader-dev`, `aureus-nautilus-node-dev`)
- **Numerical/data stack** in signal engine: `pandas`, `numpy`.
  - `services/aureus-signal/requirements.txt`
- **LLM/OpenAI-compatible client** dependency in signal service.
  - `services/aureus-signal/requirements.txt` (`openai==2.21.0`)

## Frontend Stack

- **Next.js 16 + React 19** app in dashboard web module.
  - `services/aureus-dashboard/web/package.json`
- **UI/tooling libs:** `lucide-react`, `clsx`, `tailwind-merge`, `lightweight-charts`, `react-beautiful-dnd`.
  - `services/aureus-dashboard/web/package.json`
- **Tooling:** TypeScript, ESLint, Tailwind v4 packages.
  - `services/aureus-dashboard/web/package.json`

## Data and Messaging Infrastructure

- **Redis** as event bus/state cache and command channel.
  - streams like `aureus:stream:*:orders` in `services/aureus-nautilus-bridge/main.py`
  - state keys like `aureus:state:{symbol}` in `services/aureus-dashboard/api/main.py`
- **TimescaleDB/PostgreSQL** as historical store.
  - `docker-compose.dev.yml` (`timescaledb-dev`)
  - SQL access in `services/aureus-dashboard/api/main.py`

## Environment and Configuration Surfaces

- Compose-driven env injection with service-level variables for Redis/DB/LLM/risk settings.
  - `docker-compose.dev.yml`
- Root environment files available for non-committed/localized settings.
  - `.env`
  - `.env.prod`
- Service-specific config loading pattern in node module.
  - `services/aureus-nautilus-node/config.py`

## Build, Lint, and Type Tools

- Python quality tooling in node service: `pytest`, `ruff`, `mypy`.
  - `services/aureus-nautilus-node/requirements.txt`
  - `.github/workflows/aureus-nautilus-node-quality.yml`
- Frontend lint/build scripts via npm.
  - `services/aureus-dashboard/web/package.json`

## Observability Tooling

- **Prometheus + Grafana + Redis exporter** included in dev compose topology.
  - `docker-compose.dev.yml`
  - `monitoring/prometheus/alerts.yml`
  - `monitoring/grafana/provisioning/`

## Stack Notes

- Repository is **service-oriented/polyglot**, not a single root package-managed app.
- Strong async Python footprint with Redis streams and event-driven orchestration.
- Frontend is isolated inside dashboard web module and communicates with API service.
