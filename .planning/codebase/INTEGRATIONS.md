# External Integrations

**Analysis Date:** 2026-05-27

## APIs & External Services

**Market Data Ingestion:**
- MetaTrader/MQL5 client feed - sends tick, candle, and backfill messages to gateway ports exposed in `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/docker-compose.dev.yml` and `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/docker-compose.prod.yml`.
  - SDK/Client: `pyzmq==27.1.0` for ZMQ PULL on `tcp://0.0.0.0:5555` in `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-gateway/main.py`; asyncio TCP newline JSON listener uses `TCP_PORT` default `5556` in same file.
  - Auth: Not detected; network access controlled by exposed ports `${BACKTEST_WS_PORT:-5555}` and `${BACKTEST_EVENTS_PORT:-5556}`.
- Gateway Redis stream publishing - gateway writes normalized messages to Redis keys `aureus:latest:{symbol}:{type}` and streams `aureus:stream:{symbol}:{type}` in `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-gateway/main.py`.
  - SDK/Client: `redis.asyncio` from `redis==7.2.0`.
  - Auth: `REDIS_HOST`, `REDIS_PORT`.

**AI/LLM:**
- OpenAI-compatible LLM endpoint - signal engine creates `AsyncOpenAI(api_key="none", base_url=LLM_BASE_URL)` in `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-signal/engine/ai_validator.py`.
  - SDK/Client: `openai==2.21.0`.
  - Auth: hardcoded placeholder API key `none`; base URL from `LLM_BASE_URL`; model from `LLM_MODEL` with fallback `meta-llama/Llama-3.2-3B-Instruct`.
- Dashboard API LLM base configuration - `LLM_BASE_URL` read in `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-dashboard/api/main.py` and passed by Compose in `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/docker-compose.dev.yml`.
  - SDK/Client: `httpx==0.28.1` in `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-dashboard/api/requirements.txt`.
  - Auth: Not detected.

**News Calendar:**
- FairEconomy/ForexFactory calendar - fetches `https://nfs.faireconomy.media/ff_calendar_thisweek.json` in `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-signal/engine/signals/news_provider.py`.
  - SDK/Client: `requests==2.32.5`.
  - Auth: None; uses browser-like `User-Agent`, `Accept`, and `Referer` headers.
  - Cache: local JSON cache at `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-signal/brain/news_calendar.json` via relative `CACHE_PATH`.

**Trading Execution:**
- Nautilus Trader runtime - Compose starts `ghcr.io/nautechsystems/nautilus_trader:nightly` and bridge services in `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/docker-compose.prod.yml`.
  - SDK/Client: Nautilus container image plus Python bridge code in `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-nautilus-bridge/main.py` and node clients in `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-nautilus-node`.
  - Auth: Not detected; controlled by Redis stream access and env vars `NAUTILUS_ADAPTER_MODE`, `NAUTILUS_SYMBOL_WHITELIST`, `NAUTILUS_RISK_MODE`, `NAUTILUS_REQUIRE_SL_TP`, `NAUTILUS_MAX_ORDER_NOTIONAL`, `NAUTILUS_MAX_POSITION_NOTIONAL`.

## Data Storage

**Databases:**
- TimescaleDB on PostgreSQL 15 - defined as `timescaledb-dev` and `timescaledb` in `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/docker-compose.dev.yml` and `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/docker-compose.prod.yml`.
  - Connection: service-specific `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`; combined `DATABASE_URL` for signal engine and dashboard API.
  - Client: `asyncpg==0.31.0` in `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-db-writer/main.py`, `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-signal/engine/live_engine.py`, and `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-dashboard/api/main.py`.
  - Schema: DB writer applies `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-db-writer/schema.sql` at startup from `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-db-writer/main.py`.

**File Storage:**
- Local filesystem only - logs mounted to `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/logs` by `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/docker-compose.dev.yml`.
- Signal brain cache - `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-signal/brain` mounted into signal service by `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/docker-compose.dev.yml` and `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/docker-compose.prod.yml`.
- Grafana volume - `grafana_data_dev` for dev dashboard persistence in `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/docker-compose.dev.yml`.
- TimescaleDB volume - `timescaledb_data_dev` and `timescaledb_data` in `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/docker-compose.dev.yml` and `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/docker-compose.prod.yml`.

**Caching:**
- Redis - primary stream/state/cache layer for all services, configured in `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/docker-compose.dev.yml` and `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/docker-compose.prod.yml`.
- Redis keys include `aureus:latest:*`, `aureus:stream:*`, `aureus:state:*`, `aureus:checkpoint:*`, and `aureus:config:*` in `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-gateway/main.py`, `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-signal/engine/live_engine.py`, and `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-dashboard/api/main.py`.
- News calendar local cache - file cache with 6-hour freshness check in `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-signal/engine/signals/news_provider.py`.

## Authentication & Identity

**Auth Provider:**
- Not detected for dashboard API - `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-dashboard/api/main.py` exposes FastAPI endpoints with CORS control only.
  - Implementation: `CORSMiddleware` allowlist from `CORS_ORIGINS` in `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-dashboard/api/main.py`.
- Not detected for gateway ingestion - `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-gateway/main.py` accepts ZMQ and TCP messages without token validation.
  - Implementation: Pydantic validation only for message shape.
- LLM auth not used - `AsyncOpenAI(api_key="none")` in `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-signal/engine/ai_validator.py`.

## Monitoring & Observability

**Error Tracking:**
- External error tracking not detected.
- Python logging to stdout and optional file via `LOG_FILE` in `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-gateway/main.py`, `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-db-writer/main.py`, `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-signal/engine/live_engine.py`, and `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-dashboard/api/main.py`.

**Logs:**
- Dev Compose mounts `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/logs` into Python services and sets per-service `LOG_FILE` paths in `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/docker-compose.dev.yml`.
- Production Compose does not mount logs for all services; logging defaults to stdout from service code and Docker logs in `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/docker-compose.prod.yml`.

**Metrics:**
- Redis exporter - `oliver006/redis_exporter:latest` configured with `REDIS_ADDR=redis://redis:6379` in `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/docker-compose.prod.yml`.
- Bridge metrics exporter - Python service `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-bridge-metrics-exporter/main.py` uses `prometheus-client==0.21.1` and Redis.
- Prometheus - config mounted from `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/monitoring/prometheus/prometheus.yml` in Compose files.
- Grafana - dev dashboard provisioning mounted from `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/monitoring/grafana` in `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/docker-compose.dev.yml`.

## CI/CD & Deployment

**Hosting:**
- Docker Compose self-hosted deployment - production service graph in `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/docker-compose.prod.yml`.
- Dev Compose includes dashboard API, dashboard web dependencies, Grafana, and local volume mounts in `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/docker-compose.dev.yml`.

**CI Pipeline:**
- Not detected in analyzed files.

## Environment Configuration

**Required env vars:**
- `DB_PASSWORD` - TimescaleDB password in `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/docker-compose.dev.yml` and `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/docker-compose.prod.yml`.
- `REDIS_HOST`, `REDIS_PORT` - Redis connection for gateway, signal, DB writer, dashboard API, Nautilus bridge/node, metrics exporter.
- `DATABASE_URL` - asyncpg DSN for signal engine and dashboard API in `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-signal/engine/live_engine.py` and `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-dashboard/api/main.py`.
- `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` - DB writer connection in `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-db-writer/main.py`.
- `SYMBOLS` - multi-symbol processing list in `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-signal/engine/live_engine.py` and metrics exporter config in Compose.
- `LLM_BASE_URL` - OpenAI-compatible endpoint for signal AI validator and dashboard API config.
- `LLM_MODEL` - optional active model fallback in `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-signal/engine/ai_validator.py`.
- `CORS_ORIGINS` - dashboard API CORS allowlist in `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-dashboard/api/main.py`.
- `TCP_PORT` - gateway TCP listener port from Compose and `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-gateway/main.py`.
- `LOG_LEVEL`, `LOG_FILE` - Python logging in service entrypoints.
- `NAUTILUS_ADAPTER_MODE`, `NAUTILUS_LIFECYCLE_STREAM_PATTERN`, `NAUTILUS_SYMBOL_WHITELIST`, `NAUTILUS_RISK_MODE`, `NAUTILUS_REQUIRE_SL_TP`, `NAUTILUS_MAX_ORDER_NOTIONAL`, `NAUTILUS_MAX_POSITION_NOTIONAL` - Nautilus integration config in `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/docker-compose.prod.yml`.

**Secrets location:**
- `.env` file present at `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/.env`; contents not read.
- Docker Compose references secrets through environment substitutions in `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/docker-compose.dev.yml` and `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/docker-compose.prod.yml`.

## Webhooks & Callbacks

**Incoming:**
- ZMQ PULL listener - binds `tcp://0.0.0.0:5555` in `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-gateway/main.py` for message ingestion.
- TCP newline JSON listener - configured by `TCP_PORT` in `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-gateway/main.py` and exposed as `${BACKTEST_EVENTS_PORT:-5556}` in Compose.
- Dashboard REST API - FastAPI endpoints under `/api/v1/*` in `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-dashboard/api/main.py`, exposed as `${DEV_API_PORT:-8002}:8001` in dev Compose.
- Prometheus metrics endpoint - bridge metrics exporter exposes `EXPORTER_PORT=9108` mapped to `${BRIDGE_METRICS_PORT:-19158}` in `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/docker-compose.prod.yml`.

**Outgoing:**
- OpenAI-compatible chat completions - signal AI validator calls `client.chat.completions.create(...)` in `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-signal/engine/ai_validator.py`.
- FairEconomy calendar GET - news provider calls `requests.get(URL, headers=headers, timeout=25)` in `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-signal/engine/signals/news_provider.py`.
- Redis stream reads/writes - services use Redis streams for internal callbacks and lifecycle events in `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-gateway/main.py`, `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-db-writer/main.py`, `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-signal/engine/live_engine.py`, and Nautilus services under `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-nautilus-bridge` and `D:/Aureus/.claude/worktrees/agent-a4f04ac96376ec7fa/services/aureus-nautilus-node`.

---

*Integration audit: 2026-05-27*
