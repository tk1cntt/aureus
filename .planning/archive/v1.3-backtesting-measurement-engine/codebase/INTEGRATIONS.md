# INTEGRATIONS

## Core Integration Surfaces

## 1) Redis (Streams, Keys, Pub/Sub-like command channels)

Redis is the dominant integration point across services.

- **Order intake streams:** bridge discovers and consumes `aureus:stream:*:orders`.
  - `services/aureus-nautilus-bridge/main.py`
- **Lifecycle stream mode:** optional consumption of `aureus:stream:*:nautilus_execution`.
  - `services/aureus-nautilus-bridge/main.py`
- **Execution event publishing:** emits to `aureus:stream:{symbol}:execution`.
  - `services/aureus-nautilus-bridge/main.py`
- **Dashboard API reads state/cache keys:**
  - `aureus:state:{symbol}`
  - `aureus:latest:*:candle`
  - `aureus:ai:latest:*`
  - Implemented in `services/aureus-dashboard/api/main.py`
- **Config/command channels:**
  - stream `aureus:sys:config`
  - publish channel `aureus:cmd:refresh_strategies`
  - defined in `services/aureus-dashboard/api/main.py`

## 2) PostgreSQL / TimescaleDB

Historical and analytical storage is handled via TimescaleDB.

- Compose service: `timescaledb-dev`.
  - `docker-compose.dev.yml`
- Dashboard API reads/writes strategy/backtest/AI-analysis data with `asyncpg`.
  - tables queried in `services/aureus-dashboard/api/main.py` include:
    - `aureus_candles`
    - `aureus_swing_points`
    - `aureus_backtest_snapshots`
    - `aureus_backtest_runs`
    - `aureus_strategy_templates`
    - `aureus_symbol_strategies`
    - `aureus_ai_analysis`

## 3) Nautilus Trader Runtime

Trading engine interaction is isolated by dedicated services.

- Nautilus image container: `ghcr.io/nautechsystems/nautilus_trader:nightly`.
  - `docker-compose.dev.yml`
- Node wrapper lifecycle and health tracking.
  - `services/aureus-nautilus-node/main.py`
- Bridge adapter converts internal order intent to execution reports.
  - `services/aureus-nautilus-bridge/main.py`

## 4) LLM Endpoint (OpenAI-compatible)

AI features are endpoint-driven and configurable.

- API service health-checks `${LLM_BASE_URL}/models`.
  - `services/aureus-dashboard/api/main.py`
- Signal service includes `openai`, `httpx`, and external URL env.
  - `services/aureus-signal/requirements.txt`
  - `docker-compose.dev.yml` (`LLM_BASE_URL`)

## 5) Monitoring/Observability

- Redis metrics exporter and custom bridge metrics exporter.
  - `docker-compose.dev.yml`
  - `services/aureus-bridge-metrics-exporter/`
- Prometheus scrapes and alerts.
  - `monitoring/prometheus/prometheus.yml`
  - `monitoring/prometheus/alerts.yml`
- Grafana dashboard provisioning.
  - `monitoring/grafana/provisioning/`

## Integration Contracts and Patterns

## Event/Contract Normalization

- Bridge normalizes adapter reports through dedicated reconciliation layer.
  - `services/aureus-nautilus-bridge/reconciliation.py`
  - called from `services/aureus-nautilus-bridge/main.py`
- Mapper translates order payload into adapter intent.
  - `services/aureus-nautilus-bridge/mapper.py`

## Symbol-Scoped Routing

Many integrations follow symbol-scoped key patterns:

- `aureus:stream:{symbol}:...`
- `aureus:state:{symbol}`
- `aureus:ai:latest:{symbol}`

This improves partitioning but requires strict consistency in producers/consumers.

## Security/Secret Handling Observations

- Credentials and connection details are supplied via env/compose variables.
  - `docker-compose.dev.yml`
  - `.env`, `.env.prod`
- No embedded long-form API key literals observed in mapper-scanned service entrypoints.

## Integration Risk Hotspots

- Heavy Redis reliance means stream/key schema drift can break multiple services.
- Multiple transport styles (streams + publish + direct key reads) increase contract complexity.
- LLM endpoint availability directly affects AI health endpoints and potentially signal enrichment paths.
