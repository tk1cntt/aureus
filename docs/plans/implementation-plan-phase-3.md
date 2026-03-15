# Aureus Implementation Plan - Phase 3: Persistence Layer

This phase focuses on ensuring all market data and calculated signals are stored efficiently for long-term audit and backtesting.

## User Review Required

> [!IMPORTANT]
> - **Hypertable Policies**: Retention and compression policies in TimescaleDB will be applied. Ensure these align with your data storage requirements.
> - **Performance**: Batch inserting thousands of ticks requires careful management of connection pools.

## Proposed Changes

### Database Layer (Storage)

#### [MODIFY] [services/aureus-db-writer/schema.sql](file:///e:/Openclaw/aureus/workspace/aureus/services/aureus-db-writer/schema.sql)
- Define hypertables for `aureus_candles` and `aureus_ticks`.
- Set up indexes for fast signal retrieval (symbol, timeframe, time).
- Add support for `aureus_signals` with reasoning metadata.

### DB Writer Service (Worker)

#### [MODIFY] [services/aureus-db-writer/main.py](file:///e:/Openclaw/aureus/workspace/aureus/services/aureus-db-writer/main.py)
- Target the new schema.
- Implement **Batch Upsert** logic: Instead of writing every tick, buffer and write in chunks (e.g., every 500 records or 1 second).
- Use `asyncpg` for high-performance PostgreSQL interaction.

## Verification Plan

### Automated Tests
- **Performance Test**: Ingest 10,000 mock ticks and verify that DB Writer processes them without creating a backlog in Redis Streams.
- **Integrity Test**: Verify `ON CONFLICT DO NOTHING` or `UPDATE` behavior for duplicate candle data.

### Manual Verification
- Use `psql` to check table sizes and hypertable chunk distribution.
