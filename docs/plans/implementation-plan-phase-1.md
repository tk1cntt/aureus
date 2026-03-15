# Aureus Implementation Plan - Phase 1: Infrastructure & Shared Layer

This plan aligns the core infrastructure and inter-service communication with the finalized architecture.

## User Review Required

> [!IMPORTANT]
> - **Redis Upgrade**: Upgrading to Redis 8.6.1 may require data migration if persistence is enabled.
> - **Msgpack Migration**: Since Msgpack is binary, `redis-cli` debugging will require extra steps, and all services must be updated simultaneously to prevent communication failure.
> - **Database Upgrade**: Moving to TimescaleDB v2.25.2 on PostgreSQL 18.3 is a significant jump from PG 15.

## Proposed Changes

### Infrastructure (Orchestration)

#### [MODIFY] [docker-compose.dev.yml](file:///e:/Openclaw/aureus/workspace/aureus/docker-compose.dev.yml)
- Update `redis-dev` image to `redis:8.6.1-alpine` (or equivalent available version).
- Update `timescaledb-dev` image to `timescale/timescaledb:2.25.2-pg18.3`.
- Ensure all service `environment` variables reference the same Redis/DB host.

### Shared Layer (Local Packages)

#### [NEW] [shared/aureus-common/](file:///e:/Openclaw/aureus/workspace/aureus/shared/aureus-common/)
- Create a reusable library for:
    - Msgpack encoding/decoding wrappers (using `msgpack`).
    - Standard message schemas (Ticks, Candles, Signals) using Pydantic.
    - Global constant definitions (Stream names, Redis keys).

### Core Ingestion (Gateway)

#### [MODIFY] [services/aureus-gateway/main.py](file:///e:/Openclaw/aureus/workspace/aureus/services/aureus-gateway/main.py)
- Import from `shared/aureus-common`.
- Switch `REDIS_DECODE_RESPONSES` to `False` to handle binary Msgpack data.
- Update `process_message` to publish using `aureus-common` Msgpack helpers.
- Align logging format with architecture rules.

## Verification Plan

### Automated Tests
- **Unit Tests**: Verify Msgpack conversion in `aureus-common`.
- **Integration Tests**: Start updated Docker containers and verify that Gateway publishes binary data to Redis Streams that can be decoded by a test listener.

### Manual Verification
- Run `docker-compose up` and check service logs for version confirmation and standardized prefixes.
