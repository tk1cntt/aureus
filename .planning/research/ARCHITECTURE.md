# ARCHITECTURE

## Existing Integration Path
`Redis Stream -> AureusMarketDataClient -> Nautilus msg_bus`

## Target Milestone Architecture

### New Components
1. `MarketDataProvider` protocol/module
2. `RedisMarketDataProvider` (behavior-preserving extraction)
3. `TradingAgentsMarketDataAdapter` (pull, normalize, cache, map symbols)

### Modified Components
- `data_client.py`: delegate polling to provider abstraction.
- `settings.py`: add provider and TradingAgents config fields.
- `main.py`: provider selection + shadow mode orchestration.
- `rollout_gates.py`: add TradingAgents drift/error/lag gate metrics.

## Data Contract
All providers must emit:
- `open`, `high`, `low`, `close`, `volume`, `timestamp` (epoch ms)

## Shadow Topology
- Primary: Redis path remains source of truth.
- Secondary: TradingAgents adapter feed compared in shadow metrics.
- Gate logic determines readiness for promotion; fallback remains Redis.

## Build Order (dependency-safe)
1. Provider abstraction extraction.
2. TradingAgents adapter implementation.
3. Runtime/config routing.
4. Observability & rollout gates.
5. Test coverage and shadow verification.
