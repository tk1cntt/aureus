# CONCERNS

## High-Priority Risk Areas

## 1) Cross-Service Contract Fragility

- Redis stream/key contracts are embedded in multiple services without a centralized schema contract package.
  - `services/aureus-nautilus-bridge/main.py`
  - `services/aureus-dashboard/api/main.py`
- Key naming drift (`aureus:stream:*`, `aureus:state:*`, config streams) could cause silent failures in consumers.

## 2) Broad Exception Catching in Long-Running Workers

- Worker loops catch broad exceptions and continue.
  - `services/aureus-nautilus-bridge/main.py`
  - `services/aureus-nautilus-node/main.py`
- This improves uptime but can suppress root-cause visibility unless logs/metrics are actively monitored.

## 3) Redis Centrality / Single Dependency Concentration

- Redis is transport + live-state + command bus + integration bridge.
- A Redis outage or schema inconsistency has system-wide blast radius.
  - represented across compose and service main modules

## 4) Inconsistent Quality Gate Coverage Across Services

- Strong CI quality gate exists for `aureus-nautilus-node`.
  - `.github/workflows/aureus-nautilus-node-quality.yml`
- Equivalent strict CI workflows for all services were not surfaced in this mapping pass.

## Medium-Priority Concerns

## 5) Runtime Configuration Complexity

- Many env flags influence behavior across compose services (LLM, risk, stream mode, CORS, symbols, DB URLs).
  - `docker-compose.dev.yml`
- Without centralized config validation, misconfiguration risk is non-trivial.

## 6) Data Stitching Complexity in API Layer

- Dashboard API composes response data from DB + Redis with mode-dependent logic (live vs backtest).
  - `services/aureus-dashboard/api/main.py`
- This can create edge-case inconsistency and is hard to regression test without integration suites.

## 7) Observability Fragmentation

- Monitoring stack exists (Prometheus/Grafana/exporters), but direct linkage between caught exceptions and alert rules was not validated in this pass.
  - `monitoring/prometheus/alerts.yml`
  - `docker-compose.dev.yml`

## Low-Priority / Hygiene Concerns

## 8) Monorepo Convention Drift

- Polyglot, multi-service repos can accumulate style and operational drift without shared check policies.
- Logging format and typing strictness vary by module.

## 9) Dependency Governance

- Python services show mixed pinning strategies (`==` vs ranges vs minimal declarations).
  - `services/aureus-signal/requirements.txt`
  - `services/aureus-nautilus-bridge/requirements.txt`
  - `services/aureus-nautilus-node/requirements.txt`

## Suggested Mitigations

1. Introduce explicit event schema/version docs or shared contract package.
2. Expand CI gates to key services beyond nautilus node.
3. Add integration tests for end-to-end stream lifecycle.
4. Add startup config validation and stronger environment sanity checks.
5. Standardize dependency pinning strategy per service criticality.

## Mapping Confidence

- Concerns are based on direct inspection of representative high-impact files and may not include every module-specific risk.
- Most urgent risks relate to cross-service contracts and operational resilience, not single-file syntax defects.
