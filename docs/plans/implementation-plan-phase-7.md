# Aureus Implementation Plan - Phase 7: Integrated Backtesting & Dashboard

The final phase provides the visual interface and the ability to test strategies against history.

## User Review Required

> [!WARNING]
> - **Next.js Deployment**: Frontend needs a stable platform; consider Vercel or local Docker hosting.
> - **Backtest Speed**: High-frequency backtesting (tick-by-tick) is slow. The initial implementation will focus on M1 candle backtesting.

## Proposed Changes

### Dashboard (UI/UX)

#### [NEW] [dashboard/src/components/Chart.tsx](file:///e:/Openclaw/aureus/workspace/aureus/dashboard/src/components/Chart.tsx)
- Integrate Lightweight Charts (TradingView) or D3.js.
- Overlay SMC zones (OB/FVG) and Swing Points dynamicly.

#### [NEW] [services/aureus-dashboard-api/main.py](file:///e:/Openclaw/aureus/workspace/aureus/services/aureus-dashboard-api/main.py)
- Create `/api/v1/backtest` endpoint.
- Create `/api/v1/live-state` endpoint (proxying Redis Cache).

### Backtesting Engine

#### [NEW] [services/aureus-signal/engine/backtester.py](file:///e:/Openclaw/aureus/workspace/aureus/services/aureus-signal/engine/backtester.py)
- Reuse the `SignalEngine` logic but feed it with data from `aureus_candles` instead of Redis Streams.
- Generate performance reports (Profit/Loss, Drawdown, AI Accuracy).

## Verification Plan

### Automated Tests
- **Backtest Consistency**: Verify that running a backtest over the same period multiple times yields identical results.
- **REST API Validation**: Ensure the Dashboard API correctly authenticates JWT requests.

### Manual Verification
- Perform a live-demo of the Dashboard connecting to the Signal Engine.
