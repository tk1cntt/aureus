# PITFALLS

## High-Risk Pitfalls

### 1) Rate-limit collapse
- **Risk:** pull provider called at Redis-like frequency triggers API throttling.
- **Prevention:** enforce adapter TTL cache and bounded polling cadence.
- **Phase owner:** TradingAgents adapter phase.

### 2) Symbol mismatch / unsupported instruments
- **Risk:** provider universe differs from Aureus symbols (`XAUUSD`, `BTCUSD`, etc.).
- **Prevention:** mandatory compatibility validation + startup mapping checks.
- **Phase owner:** prerequisites + adapter phase.

### 3) Latency drift misinterpretation
- **Risk:** comparing push stream vs pull REST without time normalization produces false negatives.
- **Prevention:** drift metric definitions with explicit lag windows and tolerances.
- **Phase owner:** rollout gate phase.

### 4) Frozen settings breakage
- **Risk:** adding fields to frozen settings model breaks direct test constructors.
- **Prevention:** update tests and defaults together; ensure backward-compatible env parsing.
- **Phase owner:** runtime/config phase.

### 5) Unsafe promotion
- **Risk:** turning TradingAgents primary without statistically meaningful shadow evidence.
- **Prevention:** enforce gate thresholds and explicit promotion criteria.
- **Phase owner:** observability + verification phases.
