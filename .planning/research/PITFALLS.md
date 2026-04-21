# Domain Pitfalls: Aureus (PITFALLS/RISKS)

**Domain:** Multi-service algorithmic trading platform (Gateway + Signal + DB Writer + Nautilus Bridge/Node + Dashboard + Monitoring)
**Researched:** 2026-04-21
**Scope:** Repo-evidence-based anti-patterns, tech debt, vùng dễ lỗi, blind spots về test/observability/security

---

## Risk catalog (severity/likelihood)

| Risk ID | Risk | Severity | Likelihood | Primary Impact |
|---|---|---|---|---|
| R1 | Silent message loss do unconditional ACK after processing failure | Critical | High | Operational + Business |
| R2 | Data integrity bug (duplicate tick insertion path) | High | High | Business + Operational |
| R3 | Error swallowing (`except Exception: pass`) in runtime paths | High | Medium-High | Operational + Dev velocity |
| R4 | Insecure default credentials (Grafana/admin, DB password fallbacks) | Critical | High | Security + Business |
| R5 | Weak perimeter controls (broad CORS + unauthenticated control/data APIs) | High | Medium | Security + Operational |
| R6 | Observability blind spot: SLO docs mention instrumentation gap while alert rules rely on that metric | Medium-High | Medium | Operational + Release confidence |
| R7 | Mixed Prometheus scrape targets (prod + dev) can pollute telemetry | Medium | Medium | Operational |
| R8 | Test strategy fragmentation (many script-like tests/prints, uneven quality gates) | Medium-High | High | Dev velocity + Regression risk |
| R9 | Startup self-healing loops without bounded degradation strategy | Medium | Medium | Operational |

---

## Evidence

### R1 — Silent message loss do unconditional ACK sau lỗi xử lý
- `services/aureus-nautilus-bridge/main.py`:
  - `handle_message()` ACK message cả ở nhánh success và nhánh `except`.
  - Ở lỗi vẫn `await client.xack(...)` ngay sau `logger.error(...)`.
- Hệ quả kiến trúc: message lỗi bị “consumed” nhưng chưa xử lý đúng, không còn retry tự nhiên từ stream group.

### R2 — Data integrity bug: duplicate insert path ở db-writer
- `services/aureus-db-writer/main.py`:
  - Trong block tick insert, `copy_records_to_table('aureus_ticks', ...)` được gọi 2 lần liên tiếp cho cùng `data_rows` trước khi ACK.
- Hệ quả: nguy cơ ghi trùng ticks, làm sai analytics/PnL/time-series downstream.

### R3 — Error swallowing / hidden failures
- `services/aureus-gateway/main.py` có nhiều `except Exception: pass` ở luồng connection close/cleanup.
- `services/aureus-signal/signal_computer.py` có các nhánh `except Exception: pass`.
- `services/aureus-bridge-metrics-exporter/main.py` có parse failure bị nuốt (`except Exception: pass`).
- Hệ quả: lỗi thật bị ẩn, MTTR tăng mạnh, khó forensic incident.

### R4 — Insecure defaults / weak secrets posture
- `docker-compose.dev.yml`: `GF_SECURITY_ADMIN_USER=admin`, `GF_SECURITY_ADMIN_PASSWORD=admin`.
- `services/aureus-db-writer/main.py`: default `POSTGRES_PASSWORD = ... "aureus_secure_pass"`.
- `docker-compose.prod.yml`: nhiều biến fallback password (`${DB_PASSWORD:-aureus_password}`).
- Hệ quả: credential guessing, lateral movement khi môi trường bị lộ network path.

### R5 — API/control surface chưa harden
- `services/aureus-dashboard/api/main.py`:
  - CORS đọc từ env nhưng `allow_methods=["*"]`, `allow_headers=["*"]`.
  - Không thấy authn/authz guard ở routes read/write chiến lược và control endpoints trong file chính.
- `services/aureus-gateway/main.py`: TCP listener exposed cho command/control flow, chưa thấy auth channel-level.
- Hệ quả: tăng attack surface, nguy cơ command abuse hoặc data exfiltration.

### R6 — SLO/Alert consistency gap
- `docs/signals/nautilus-slo-v1.md` ghi rõ duplicate-trace metric có “instrumentation gap - currently not emitted by bridge exporter”.
- `monitoring/prometheus/rules/nautilus-alerts.yml` vẫn define alert `NautilusDuplicateTraceIdDetected` dựa vào `aureus_bridge_duplicate_trace_id_total`.
- `services/aureus-bridge-metrics-exporter/main.py` hiện có metric này; tài liệu và thực tế lệch nhau.
- Hệ quả: operator tin sai trạng thái readiness (doc stale), gate decision thiếu nhất quán.

### R7 — Telemetry pollution risk từ scrape target ghép prod + dev
- `monitoring/prometheus/prometheus.yml` scrape cùng lúc `prometheus` + `prometheus-dev`, `redis-exporter` + `redis-exporter-dev`, `aureus-bridge-metrics` + `aureus-bridge-metrics-dev`.
- Hệ quả: dashboard/alert có thể trộn tín hiệu môi trường, dẫn tới false positives/false negatives.

### R8 — Test blind spots & quality gate uneven
- Test inventory lớn ở `services/aureus-signal/tests` + `services/aureus-signal/unittest`, nhưng nhiều file là script-style in/out (`print`) thay vì assertion-first pytest style.
- `docs/runbooks/QUALITY_GATES.md` gate chặt cho `aureus-nautilus-node` (pytest + ruff + mypy), chưa thấy equivalent standardized gate cho gateway/db-writer/signal/bridge.
- Hệ quả: quality bar không đồng nhất giữa critical services, regression creep theo thời gian.

### R9 — Startup resilience pattern chưa có fail-fast budget
- `aureus-db-writer` / `aureus-nautilus-bridge` dùng loop connect vô hạn (`while self.running` + sleep) khi Redis/Postgres unavailable.
- Hệ quả: service “seems alive but degraded”, orchestration khó phân biệt healthy vs stuck reconnecting.

---

## Impact nếu không xử lý

### Business impact
- Lệch dữ liệu execution/tick (R1, R2) làm sai đánh giá hiệu năng strategy và risk exposure.
- Security weaknesses (R4, R5) có thể dẫn đến incident nghiêm trọng: account compromise, downtime, reputational damage.
- Telemetry sai (R6, R7) khiến quyết định rollout/promotion dựa trên tín hiệu không đáng tin.

### Dev velocity impact
- Hidden failures (R3) và test fragmentation (R8) làm debugging tốn thời gian, khó tái hiện bug.
- Doc/runtime drift (R6) tạo hiểu lầm giữa dev, SRE, và release manager.

### Operational impact
- Message loss silent (R1) gây inconsistency khó detect sớm.
- Reconnect loops (R9) kéo dài trạng thái gray failure; on-call mất thời gian triage.

---

## Mitigation options

### P0 (khẩn cấp, cần đưa vào phase sớm)

1. **Stop ACK-on-failure cho bridge ingestion (R1)**
   - Chỉ `xack` khi xử lý thành công.
   - Khi lỗi: route vào DLQ stream (`aureus:stream:dlq:*`) + metadata lỗi + retry count.
   - Bổ sung alert DLQ growth.

2. **Fix duplicate tick insert path (R2)**
   - Loại bỏ duplicate `copy_records_to_table` call.
   - Thêm idempotency key hoặc DB uniqueness strategy phù hợp với stream-id/time/symbol.
   - Viết regression test xác nhận “one input row -> one persisted row”.

3. **Secrets hardening baseline (R4)**
   - Remove insecure defaults trong compose/prod code paths.
   - Bắt buộc inject secrets qua env/secret manager; fail startup nếu secret thiếu ở prod profile.
   - Rotate mọi credential mặc định đang dùng.

4. **Control/API auth minimum (R5)**
   - Token/mTLS cho channel command và API endpoints nhạy cảm.
   - Thu hẹp CORS theo whitelist strict (origin/method/header cụ thể).

### P1 (ngắn hạn, bảo vệ release quality)

5. **Error-handling policy: no silent pass in runtime paths (R3)**
   - Cấm `except Exception: pass` trừ cleanup vô hại có comment lý do.
   - Structured logging + error classification (parse_error, redis_error, downstream_error).

6. **Unify observability contract (R6, R7)**
   - Đồng bộ tài liệu SLO với metric hiện hành.
   - Tách scrape config theo environment hoặc dùng labels bắt buộc (`env=dev|prod`) và alert filter theo env.

7. **Health model cải tiến (R9)**
   - Expose readiness/liveness phản ánh dependency connectivity thật.
   - Đặt retry budget + escalating state (DEGRADED -> FAIL) thay vì loop vô hạn im lặng.

### P2 (chiến lược, giảm debt dài hạn)

8. **Cross-service quality gates (R8)**
   - Mở rộng gate chuẩn (pytest + lint + type check + contract tests) cho gateway/db-writer/signal/bridge.
   - Thêm smoke test cho luồng end-to-end critical: order intent -> execution -> persistence -> dashboard.

9. **Reliability architecture baseline**
   - Dead-letter + replay tools.
   - Idempotency contracts documented per stream.
   - SLO error budget workflow gắn với rollout gates.

---

## Quick wins vs strategic fixes

### Quick wins (1-3 ngày)
- Sửa duplicate insert ở `aureus-db-writer` (R2).
- Bỏ/giảm `except ...: pass` ở runtime hotspots (R3).
- Cập nhật tài liệu SLO để hết mâu thuẫn metric gap (R6).
- Đổi ngay default Grafana/admin và DB fallback password ở compose profiles (R4).
- Tách/label env trong Prometheus scrape để tránh trộn dev/prod (R7).

### Strategic fixes (1-3 sprint)
- Thiết kế DLQ + retry semantics + replay tooling cho Redis stream pipeline (R1).
- Chuẩn hóa authn/authz + network segmentation cho API/gateway control plane (R5).
- Thiết lập quality gate đồng nhất toàn bộ services + contract tests xuyên service (R8).
- Xây readiness/degradation model với retry budget và operator runbook chi tiết (R9).

---

## Confidence

| Area | Confidence | Basis |
|---|---|---|
| Runtime reliability pitfalls | HIGH | Direct code evidence from gateway/db-writer/bridge files |
| Security posture pitfalls | HIGH | Compose/env defaults + API config evidence |
| Observability blind spots | HIGH | Prometheus rules/config + SLO docs cross-check |
| Test blind spots | MEDIUM-HIGH | Test corpus pattern + quality gate docs for one service only |

---

## Sources (repo evidence)

- `/d/Aureus/.claude/worktrees/agent-aee71ecf/services/aureus-nautilus-bridge/main.py`
- `/d/Aureus/.claude/worktrees/agent-aee71ecf/services/aureus-db-writer/main.py`
- `/d/Aureus/.claude/worktrees/agent-aee71ecf/services/aureus-gateway/main.py`
- `/d/Aureus/.claude/worktrees/agent-aee71ecf/services/aureus-dashboard/api/main.py`
- `/d/Aureus/.claude/worktrees/agent-aee71ecf/services/aureus-bridge-metrics-exporter/main.py`
- `/d/Aureus/.claude/worktrees/agent-aee71ecf/docker-compose.dev.yml`
- `/d/Aureus/.claude/worktrees/agent-aee71ecf/docker-compose.prod.yml`
- `/d/Aureus/.claude/worktrees/agent-aee71ecf/monitoring/prometheus/prometheus.yml`
- `/d/Aureus/.claude/worktrees/agent-aee71ecf/monitoring/prometheus/alerts.yml`
- `/d/Aureus/.claude/worktrees/agent-aee71ecf/monitoring/prometheus/rules/nautilus-alerts.yml`
- `/d/Aureus/.claude/worktrees/agent-aee71ecf/docs/signals/nautilus-slo-v1.md`
- `/d/Aureus/.claude/worktrees/agent-aee71ecf/docs/runbooks/QUALITY_GATES.md`
