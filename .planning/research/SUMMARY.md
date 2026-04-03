# SUMMARY

## Stack additions
- Add provider abstraction module and keep Redis provider as baseline.
- Add TradingAgents adapter as optional dependency path.
- Add cache/throttle controls and symbol mapping config.

## Feature table stakes
- Provider-neutral ingestion interface.
- TradingAgents adapter normalization to canonical candle schema.
- Runtime routing modes: `redis`, `shadow`, `tradingagents`.
- Shadow drift and rollout-gate safety controls.
- Regression-focused tests for provider/adapter/gates.

## Watch Out For
- Pull-based API rate limits vs current high-frequency expectations.
- Symbol universe and timezone/latency mismatches.
- Frozen settings constructor compatibility in tests.
- Promotion to primary before gate evidence is stable.
