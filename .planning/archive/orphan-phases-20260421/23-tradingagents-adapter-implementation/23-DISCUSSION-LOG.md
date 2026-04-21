# Phase 23: TradingAgents Adapter Implementation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions captured in CONTEXT.md — this log preserves the analysis.

**Date:** 2026-04-04
**Phase:** 23-tradingagents-adapter-implementation
**Mode:** discuss

## Discussion Log

### 1. Interface Target
**Question:** Which interface should the adapter actually implement?
**Options:**
- A. Follow D-23 (Recommended): Implement `DecisionProvider`. Fetch OHLCV via Redis.
- B. Follow ADPT-01: Implement `MarketDataProvider`.
**Selection:** User chose A (Follow D-23 - Recommended).

### 2. Symbol Mapping Approach
**Question:** Where should the adapter map Aureus symbols to TradingAgents targets?
**Options:**
- A. Static `symbols.json` file (Recommended).
- B. Hardcoded dict in code.
- C. Environment variables `.env`.
**Selection:** User chose A (Static `symbols.json` file - Recommended).

### 3. Cache & Backoff Strategy
**Question:** How should the adapter enforce the rate-limit/cache protection (ADPT-03)?
**Options:**
- A. In-memory dict with TTL (Recommended).
- B. Redis Cache.
- C. File base TTL.
**Selection:** User chose A (In-memory dict with TTL - Recommended).

### 4. Error & Fallback Handling
**Question:** How should the adapter report/handle rate-limit/fallback failures (ADPT-04)?
**Options:**
- A. Yield `None` (Recommended). Pass-through, engine logs error.
- B. Return `HOLD` signal with 0.0 confidence.
- C. Throw exception to engine.
**Selection:** User chose A (Yield `None` - Recommended).

