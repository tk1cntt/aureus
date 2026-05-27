# Technology Stack

**Analysis Date:** 2026-05-27

## Languages

**Primary:**
- Python 3 - backend services under `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-gateway/main.py`, `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-db-writer/main.py`, `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-signal/main.py`, `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-dashboard/api/main.py`.
- TypeScript 5 - Next.js dashboard web app under `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-dashboard/web/src` with config in `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-dashboard/web/tsconfig.json`.

**Secondary:**
- MQL5/MetaTrader artifacts - trading terminal provider code/binaries under `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/mql5`.
- SQL - TimescaleDB/PostgreSQL schema and utility scripts such as `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-db-writer/schema.sql`.
- YAML - Docker Compose and monitoring config in `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/docker-compose.dev.yml`, `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/docker-compose.prod.yml`, and `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/monitoring/prometheus/prometheus.yml`.

## Runtime

**Environment:**
- Python container runtime - each Python service has its own `Dockerfile` and `requirements.txt`, e.g. `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-signal/Dockerfile` and `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-signal/requirements.txt`.
- Node.js runtime - dashboard web app uses Next.js scripts in `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-dashboard/web/package.json`.
- Docker Compose - local and production orchestration in `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/docker-compose.dev.yml` and `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/docker-compose.prod.yml`.
- Nautilus Trader container image - `ghcr.io/nautechsystems/nautilus_trader:nightly` in `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/docker-compose.prod.yml`.

**Package Manager:**
- pip - Python dependencies pinned in service-level `requirements.txt` files.
- npm - dashboard web app scripts in `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-dashboard/web/package.json`.
- Lockfile: present for web at `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-dashboard/web/package-lock.json`; Python lockfiles not detected.

## Frameworks

**Core:**
- FastAPI 0.129.0 - dashboard API server in `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-dashboard/api/main.py`.
- Uvicorn 0.41.0 - ASGI runtime for dashboard API from `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-dashboard/api/requirements.txt`.
- Next.js 16.1.6 - dashboard web app in `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-dashboard/web/package.json`.
- React 19.2.3 / React DOM 19.2.3 - dashboard UI dependencies in `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-dashboard/web/package.json`.
- Tailwind CSS 4 - dashboard styling via `tailwindcss` and `@tailwindcss/postcss` in `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-dashboard/web/package.json`.

**Testing:**
- pytest - configured for `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-nautilus-node/requirements.txt`; Python tests exist under service `tests` and `unittest` directories.
- Service-level Python unit tests - examples in `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-signal/tests` and `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-db-writer/tests`.
- Next.js ESLint - `eslint` script in `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-dashboard/web/package.json` with config `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-dashboard/web/eslint.config.mjs`.

**Build/Dev:**
- Docker Compose v3.8 - service orchestration in `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/docker-compose.dev.yml` and `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/docker-compose.prod.yml`.
- TypeScript strict mode - enabled in `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-dashboard/web/tsconfig.json`.
- Ruff and mypy - listed for Nautilus node development in `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-nautilus-node/requirements.txt`.
- Prometheus and Grafana - monitoring stack in `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/docker-compose.dev.yml`.

## Key Dependencies

**Critical:**
- `redis==7.2.0` - async Redis streams/state in gateway, signal engine, DB writer, dashboard API via `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-gateway/requirements.txt`, `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-signal/requirements.txt`, and `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-db-writer/requirements.txt`.
- `asyncpg==0.31.0` - TimescaleDB/PostgreSQL access in `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-signal/engine/live_engine.py`, `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-db-writer/main.py`, and `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-dashboard/api/main.py`.
- `pydantic==2.12.5` - message and request validation in `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-gateway/main.py` and dashboard API models in `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-dashboard/api/main.py`.
- `openai==2.21.0` - OpenAI-compatible LLM client in `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-signal/engine/ai_validator.py`.
- `pyzmq==27.1.0` - ZMQ PULL ingestion in `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-gateway/main.py`.
- `pandas==3.0.1` and `numpy==2.4.2` - signal computation dataframes/indicators in `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-signal/requirements.txt`.
- `fastapi==0.129.0` and `uvicorn==0.41.0` - HTTP dashboard API in `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-dashboard/api/requirements.txt`.

**Infrastructure:**
- Redis Alpine image - message bus and state store in `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/docker-compose.dev.yml` and `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/docker-compose.prod.yml`.
- TimescaleDB PostgreSQL 15 image - time-series storage in `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/docker-compose.dev.yml` and `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/docker-compose.prod.yml`.
- `prometheus-client==0.21.1` - bridge metrics exporter in `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-bridge-metrics-exporter/requirements.txt`.
- `oliver006/redis_exporter:latest` - Redis metrics exporter in `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/docker-compose.prod.yml`.
- `prom/prometheus:latest` and `grafana/grafana:latest` - monitoring in `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/docker-compose.dev.yml`.
- `httpx==0.28.1` and `requests==2.32.5` - HTTP clients for dashboard API and news/LLM integration in `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-dashboard/api/requirements.txt` and `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-signal/requirements.txt`.

## Configuration

**Environment:**
- `.env` file present at `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/.env` - contains environment configuration; contents not read.
- Docker Compose passes `REDIS_HOST`, `REDIS_PORT`, `DATABASE_URL`, `POSTGRES_*`, `DB_PASSWORD`, `SYMBOLS`, `LLM_BASE_URL`, `LOG_LEVEL`, `LOG_FILE`, and Nautilus risk variables in `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/docker-compose.dev.yml` and `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/docker-compose.prod.yml`.
- Python services load environment via `os.getenv` and `python-dotenv`; signal engine calls `load_dotenv()` in `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-signal/engine/live_engine.py`.
- Symbols and precision config live in `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-signal/symbols.json` and are mounted into dashboard API in `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/docker-compose.dev.yml`.

**Build:**
- Compose files: `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/docker-compose.dev.yml`, `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/docker-compose.prod.yml`.
- Web config: `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-dashboard/web/next.config.ts`, `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-dashboard/web/tsconfig.json`, `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-dashboard/web/postcss.config.mjs`, `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-dashboard/web/eslint.config.mjs`.
- Monitoring config: `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/monitoring/prometheus/prometheus.yml`, `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/monitoring/prometheus/alerts.yml`, `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/monitoring/prometheus/rules/nautilus-alerts.yml`.

## Platform Requirements

**Development:**
- Docker and Docker Compose required to run Redis, TimescaleDB, Python services, Nautilus, Prometheus, and Grafana from `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/docker-compose.dev.yml`.
- Node.js/npm required for dashboard web commands from `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-dashboard/web/package.json`.
- Python/pip required for service development using service-level `requirements.txt` files.
- Optional local OpenAI-compatible LLM endpoint expected at `LLM_BASE_URL`, defaulting to `http://host.docker.internal:8005/v1` in Compose.

**Production:**
- Docker Compose production target defined by `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/docker-compose.prod.yml`.
- Production service ports include Redis `${REDIS_PORT:-6379}`, TimescaleDB `${DB_PORT:-5432}`, gateway `${BACKTEST_WS_PORT:-5555}` and `${BACKTEST_EVENTS_PORT:-5556}`, bridge metrics `${BRIDGE_METRICS_PORT:-19158}`, and Prometheus `${PROMETHEUS_PORT:-19590}`.
- Production persistence uses Docker volume `timescaledb_data` in `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/docker-compose.prod.yml`.

---

*Stack analysis: 2026-05-27*
