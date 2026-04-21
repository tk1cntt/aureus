# STACK Research — Aureus

**Researched:** 2026-04-21  
**Scope:** Stack thực tế trong repo để làm nền requirements/roadmap

## Current stack inventory

### 1) Languages & Runtime
- **Python**: backend microservices chính (gateway, signal, db-writer, nautilus-node, nautilus-bridge, dashboard-api).
- **TypeScript/JavaScript (Node.js 20)**: dashboard web (Next.js).
- **MQL5**: adapter/client-side integration artifacts trong `mql5/`.

### 2) Frameworks / Libraries
- **Backend API:** FastAPI + Uvicorn (`services/aureus-dashboard/api/requirements.txt`).
- **Data & validation:** asyncpg, redis-py asyncio, Pydantic v2.
- **Signal/quant libs:** pandas, numpy.
- **LLM client:** openai Python SDK (service signal).
- **Frontend:** Next.js 16.1.6 + React 19.2.3 + TypeScript + TailwindCSS v4.

### 3) Data, Queue/Stream, Cache
- **Primary DB:** TimescaleDB (Postgres 15 image `timescale/timescaledb:latest-pg15`).
- **Queue/Event bus + cache/state:** Redis (streams + hashes + pub/sub patterns trong code gateway/signal).
- **Message ingress from MT5:** TCP socket (port 5556) và ZMQ PULL (port 5555) ở gateway.

### 4) Build/Test/Deploy Tooling
- **Containerization:** Docker + docker compose (`docker-compose.dev.yml`, `docker-compose.prod.yml`).
- **CI hiện có:** GitHub Actions cho `aureus-nautilus-node` (pytest + ruff + mypy, Python 3.12).
- **Testing framework:** pytest (nhiều test ở nautilus-node/signal/bridge/db-writer).
- **Static checks:** ruff, mypy (ít nhất cho nautilus-node).
- **Package managers:** pip (Python, qua requirements.txt), npm + package-lock (web).

### 5) Observability
- **Metrics/Monitoring:** Prometheus + Grafana + redis_exporter + custom bridge metrics exporter.

## Evidence from repo

- **Compose service graph + infra core**
  - Redis, TimescaleDB, signal, db-writer, gateway, nautilus stack, monitoring, dashboard-api: `docker-compose.dev.yml` (lines 3-267), `docker-compose.prod.yml` (lines 3-210).
- **Python service runtimes**
  - Docker base images `python:3.11-slim` / `python:3.12-slim`: service Dockerfiles.
  - `aureus-db-writer` dùng Python 3.12 image; service khác đa số Python 3.11.
- **Backend framework**
  - FastAPI app ở `services/aureus-dashboard/api/main.py` (line 33) + deps `fastapi`, `uvicorn` trong requirements.
- **Redis stream/state usage**
  - Gateway ghi Redis hash + xadd stream (`aureus:latest:*`, `aureus:stream:*`) tại `services/aureus-gateway/main.py` (lines 97-113, 159).
- **MT5 ingress protocols**
  - ZMQ listener port 5555, TCP listener port 5556: `services/aureus-gateway/main.py` (lines 182-190, 262-270).
- **Frontend stack**
  - Next 16.1.6, React 19.2.3, TS5, Tailwind4: `services/aureus-dashboard/web/package.json` (lines 14-30).
  - Node 20 base image + npm install/build: `services/aureus-dashboard/web/Dockerfile` (lines 1-13).
- **CI quality gate (partial scope)**
  - `.github/workflows/aureus-nautilus-node-quality.yml` chạy pytest/ruff/mypy cho duy nhất service nautilus-node.
- **Runbook vận hành**
  - `RUN_SERVICES.md` mô tả quy trình chạy bằng WSL + docker compose, test command, restart strategy.

## Strengths

1. **Kiến trúc microservice tương đối rõ ràng** quanh luồng market data/signal/execution.
2. **Data plane phù hợp domain trading/time-series:** Redis Streams + TimescaleDB.
3. **Observability đã có nền** (Prometheus/Grafana/exporters), không phải bắt đầu từ 0.
4. **Nautilus-node có quality gate CI cụ thể** (test + lint + type check).
5. **Frontend stack hiện đại** (Next 16 + React 19 + TS), có lockfile npm.

## Gaps/Risks

1. **Version drift Python runtime**: đang trộn 3.11 và 3.12 giữa services -> rủi ro khác biệt dependency/runtime.
2. **Dependency pinning chưa đồng nhất**: có service pin chặt (`==`), service dùng range hoặc rất ít deps khai báo (`aureus-gateway` chỉ 4 package).
3. **CI coverage chưa chuẩn hóa toàn hệ thống**: workflow chính thức mới thấy cho nautilus-node, chưa thấy gate tương đương cho signal/gateway/api/db-writer/web.
4. **Compose dùng `latest` cho nhiều image** (redis, prometheus, grafana, timescaledb tag latest-pg15) -> rủi ro reproducibility/regression.
5. **Protocol ingress kép (TCP + ZMQ)** tăng bề mặt vận hành và kiểm thử compatibility.
6. **Packaging strategy phân mảnh**: Python services chưa có pyproject/lock thống nhất; web dùng npm lock riêng.

### Maturity assessment (ngắn gọn)
- **Ổn định (tương đối):** Core runtime bằng Docker Compose; Redis+TimescaleDB; signal test suite dày; monitoring stack có mặt.
- **Chưa chuẩn hóa:** Python versioning, dependency management, CI gates cross-service, image version pinning.
- **Rủi ro cao trung hạn:** reproducibility môi trường, regression liên service, và upgrade burden khi scale team.

## Recommendations for roadmap

1. **Chuẩn hóa runtime & dependency baseline (Phase sớm, bắt buộc)**
   - Chọn **1 Python version chuẩn** (khuyến nghị 3.12) cho tất cả backend service.
   - Chuẩn hóa dependency policy: pin tối thiểu cho production-critical libs (redis/asyncpg/pydantic/fastapi).
   - Định nghĩa policy image tags: tránh `latest` ở prod path.

2. **Thiết lập quality gate toàn service (Phase sớm)**
   - Mở rộng GitHub Actions cho: gateway, signal, db-writer, dashboard-api, dashboard-web.
   - Gate tối thiểu: unit tests + lint + type checks (Python: ruff/mypy; Web: eslint + typecheck + build).

3. **Ổn định data-contract giữa services (Phase giữa)**
   - Document và version hóa Redis stream schema (`aureus:stream:*` payload fields).
   - Thêm contract tests cho producer/consumer cặp gateway → signal/db-writer/bridge.

4. **Chuẩn hóa deploy profile dev/prod (Phase giữa)**
   - Tách rõ compose overlays hoặc env profiles, giữ parity cao dev-prod.
   - Pin version các thành phần observability để tránh drift khi restart/build lại.

5. **Stack alternatives khả thi (chỉ cân nhắc khi có pain thực tế)**
   - **Python packaging:** chuyển sang `pyproject.toml` + lock (Poetry/uv) để reproducible build tốt hơn.  
     - Trade-off: chi phí migration + cập nhật CI/scripts.
   - **Message bus:** Redis Streams hiện phù hợp MVP/early scale; chỉ cân nhắc Kafka/NATS khi throughput/fanout/retention vượt giới hạn vận hành Redis hiện tại.  
     - Trade-off: hệ thống phức tạp hơn đáng kể.
   - **Workflow orchestration:** giữ docker compose cho hiện tại; chỉ chuyển K8s khi cần multi-env autoscaling/HA thực sự.  
     - Trade-off: tăng mạnh độ phức tạp ops.

## Kết luận hành động

Stack hiện tại **đủ tốt để tiếp tục phát triển roadmap gần hạn**, nhưng cần ưu tiên chuẩn hóa (runtime, dependency, CI, version pinning) trước khi mở rộng tính năng lớn. Nếu không, rủi ro chính không nằm ở thuật toán mà ở **độ tin cậy build/test/deploy liên service**.