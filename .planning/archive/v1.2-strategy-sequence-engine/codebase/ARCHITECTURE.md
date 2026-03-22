# ARCHITECTURE

## High-Level Style

Aureus is a **service-oriented event-driven system** built around Redis streams/state and Python async workers, with a separate Next.js dashboard frontend.

- Core runtime orchestration in `docker-compose.dev.yml`
- Service modules under `services/`

## Major Layers

## 1) Ingestion and Gateway Layer

- `services/aureus-gateway/` receives upstream feed/events and emits internal stream events.
- Feeds Redis-backed downstream processors.

## 2) Processing and Decision Layer

- `services/aureus-signal/` runs signal engine pipeline and writes outputs/state.
  - Entry: `services/aureus-signal/main.py`
- Strategy metadata and AI analysis are exposed through dashboard API endpoints.

## 3) Execution Layer

- `services/aureus-nautilus-node/` wraps Nautilus runtime startup/lifecycle.
  - Entry: `services/aureus-nautilus-node/main.py`
- `services/aureus-nautilus-bridge/` translates order events to execution events.
  - Entry: `services/aureus-nautilus-bridge/main.py`
  - Uses `mapper.py` + `reconciliation.py` abstractions.

## 4) Persistence Layer

- Redis for transient state, stream transport, and command/config signaling.
- TimescaleDB/PostgreSQL for historical candles, snapshots, strategies, and AI analysis.
  - Accessed in `services/aureus-dashboard/api/main.py`

## 5) API and Presentation Layer

- FastAPI backend serves chart, symbol state, strategy management, and AI endpoints.
  - `services/aureus-dashboard/api/main.py`
- Next.js frontend consumes API and renders dashboards.
  - `services/aureus-dashboard/web/`

## 6) Observability Layer

- Redis exporter + bridge metrics exporter + Prometheus + Grafana.
  - `docker-compose.dev.yml`
  - `monitoring/`

## Key Runtime Entry Points

- Signal engine: `services/aureus-signal/main.py`
- Nautilus node: `services/aureus-nautilus-node/main.py`
- Nautilus bridge: `services/aureus-nautilus-bridge/main.py`
- Dashboard API: `services/aureus-dashboard/api/main.py`
- Dashboard web: `services/aureus-dashboard/web/package.json` scripts

## Primary Data Flow (Simplified)

1. Market/order events enter via gateway and are pushed to Redis stream namespaces.
2. Signal/bridge consumers process symbol streams and derive intents/events.
3. Bridge publishes normalized execution events by symbol.
4. State snapshots and historical records are split between Redis (live) and TimescaleDB (historical).
5. Dashboard API stitches DB + Redis data for frontend consumption.

## Architecture Traits

## Strengths

- Clear service boundaries by responsibility (gateway, signal, bridge, node, dashboard).
- Async I/O pattern enables non-blocking stream/event handling.
- Runtime-configurable behavior via env variables in compose.

## Trade-offs

- Cross-service event contracts are implicit in code and key naming rather than centralized schema packages.
- Multiple persistence access patterns (DB + Redis live stitching) increase consistency and debugging complexity.
- Some services are mature with tests/CI, while quality gates appear focused on selected modules (not uniformly enforced repo-wide).

## Notable Architectural Abstractions

- `BridgeProcessor` in bridge service encapsulates order/lifecycle processing transitions.
  - `services/aureus-nautilus-bridge/main.py`
- `RuntimeHealth` in node service abstracts lifecycle phases and failure state.
  - `services/aureus-nautilus-node/main.py`
- API model classes (`pydantic`) enforce request shapes for strategy/model endpoints.
  - `services/aureus-dashboard/api/main.py`
