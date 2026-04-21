# Architecture Research: Aureus

**Domain:** Real-time AI-assisted trading signal platform
**Researched:** 2026-04-21
**Confidence:** HIGH (đọc trực tiếp từ mã nguồn + compose runtime)

## 1) System context

Aureus hiện là kiến trúc microservices hướng sự kiện, với Redis Streams làm event backbone, TimescaleDB làm persistent store, và các service Python chuyên trách theo pipeline giao dịch.

### Context diagram (text)

```text
[MT4/EA | external feed]
    -> (TCP/ZMQ JSON)
[aureus-gateway]
    -> (Redis Streams: aureus:stream:{symbol}:tick|candle)
[aureus-signal] ------------------------> [LLM endpoint (vLLM/OpenAI-compatible)]
    -> (Redis: aureus:state:{symbol}, orders stream, swing_point stream)
    -> (TimescaleDB: candles/snapshots via own writes)

[aureus-nautilus-node]
    <- (orders stream)
    -> (execution/positions stream via sync worker)
[aureus-nautilus-bridge]
    <- (orders and optional nautilus lifecycle stream)
    -> (execution stream)

[aureus-db-writer]
    <- (Redis Streams: tick/candle/swing_point/execution/positions/account)
    -> (TimescaleDB)

[aureus-dashboard-api]
    <- (Redis state/latest + TimescaleDB)
    -> (REST for dashboard web)
    -> (global command stream: aureus:sys:config)

[aureus-bridge-metrics-exporter]
    <- (orders/execution/positions streams)
    -> (Prometheus metrics)
```

### External integrations

| Integration | Vai trò | Giao thức/kiểu tích hợp |
|---|---|---|
| MT4/EA | Nguồn market data + có thể nhận lệnh | TCP/ZMQ JSON qua gateway |
| LLM service (`LLM_BASE_URL`) | AI pulse/audit cho signal engine/dashboard API | HTTP API tương thích OpenAI |
| Nautilus Trader image | Runtime giao dịch (live/sim bridge) | Python integration + Redis streams |
| Prometheus/Grafana | Giám sát hệ thống | Pull metrics HTTP |

## 2) Component/module view

### Bounded contexts / modules chính

| Context | Service(s) | Trách nhiệm cốt lõi | Dữ liệu sở hữu thực tế |
|---|---|---|---|
| Ingestion | `aureus-gateway` | Validate + dedup message đầu vào, publish stream | Redis `aureus:latest:*`, stream tick/candle |
| Signal intelligence | `aureus-signal` | Tính tín hiệu, quản trị state, strategy eval, order trigger, AI queue | Redis `aureus:state:*`, `aureus:checkpoint:*`, stream orders/swing_point, DB snapshots/candles |
| Execution integration | `aureus-nautilus-node`, `aureus-nautilus-bridge` | Đọc order intents, enforce risk policy, map lifecycle về execution events | Streams orders/execution/positions, pending intents in-memory |
| Persistence | `aureus-db-writer` | Consume đa stream và flush batch vào TimescaleDB | Timescale tables (ticks/candles/swing_points/execution/positions/account) |
| Query/API | `aureus-dashboard/api` | API tổng hợp live state + historical, command/config endpoint | Đọc Redis + TimescaleDB, ghi `aureus:sys:config` |
| Observability | `aureus-bridge-metrics-exporter`, Prometheus | Đo backlog, latency, duplicate, pnl metrics | Prometheus series |

### Coupling hiện tại (điểm dính)

| Loại coupling | Mô tả | Mức độ |
|---|---|---|
| Contract-by-key giữa services | Nhiều service phụ thuộc cứng naming `aureus:stream:{symbol}:...` và payload JSON field | Cao |
| Redis schema coupling | Không có central schema registry; mapping nằm rải ở gateway/signal/bridge/db-writer | Cao |
| Symbol hardcode/assumption | `execution_client` mặc định stream `XAUUSD` khi không có cấu hình đầy đủ | Trung bình-Cao |
| Dual-write candles | Signal engine vừa xử lý logic vừa ghi `aureus_candles`, DB writer cũng ingest candle stream | Cao |
| Runtime coupling vào Redis single-node | Hầu hết service boot-loop chờ Redis, không có degrade mode rõ ràng | Cao |

### Bottleneck chính

1. **Redis là điểm cổ chai + SPOF logic**: stream bus, state cache, command bus đều tập trung Redis.
2. **DB writer single worker model**: một tiến trình xử lý nhiều stream types; khi execution/candle tăng mạnh dễ tranh tài nguyên với nhau.
3. **Signal engine nặng trách nhiệm**: compute signals + AI orchestration + snapshot persistence + command listener trong cùng loop/process.
4. **Scan-based stream discovery** (`SCAN` lặp): ở db-writer/bridge có thể gây overhead khi số stream/symbol tăng.

### Điểm mở rộng tốt

1. **Per-symbol stream partitioning**: đã dùng key theo symbol -> dễ scale ngang theo symbol affinity.
2. **Consumer groups**: nền tảng sẵn cho scale-out consumers.
3. **Execution mode abstraction**: bridge có `simulated` vs `stream`, node có risk settings -> thuận lợi thêm adapter exchange/broker mới.
4. **Feature flags trong signal engine** (`redis_sync_mode`, `snapshot_mode`) cho phép rollout hành vi lưu state/snapshot.

## 3) Data & control flow

### End-to-end flow chuẩn

```text
(1) Feed vào
MT4/EA -> gateway(TCP/ZMQ) -> validate/dedup -> XADD candle/tick stream + update latest hash

(2) Signal pipeline
signal engine XREADGROUP candle streams -> update window/state -> evaluate signals/strategies
 -> (a) XADD orders stream
 -> (b) XADD swing_point stream
 -> (c) SET aureus:state:{symbol}
 -> (d) optional AI queue + snapshot/checkpoint

(3) Execution pipeline
nautilus bridge/node đọc orders stream -> map/enforce policy -> publish execution/positions streams

(4) Persistence pipeline
db-writer discover streams -> XREADGROUP -> batch insert/upsert TimescaleDB -> XACK

(5) Serving pipeline
dashboard API đọc Redis state/latest + query TimescaleDB -> trả dữ liệu chart/state/symbols
```

### Control flows đáng chú ý

- **Global command flow**: Dashboard API ghi `aureus:sys:config` (VD `LLM_MODEL_CHANGED`) -> signal engine listener nhận và update model runtime.
- **Recovery flow**: signal engine khởi động, hydrate từ snapshot + checkpoint + warmup candles, sau đó bắt stream realtime.
- **Risk gate flow**: execution client/node validate trace_id, symbol whitelist, SL/TP, max notional trước khi chấp nhận order.

## 4) Architectural risks

### Rủi ro kiến trúc mức cao

| Risk | What can break | Vì sao xảy ra | Mức độ |
|---|---|---|---|
| Contract drift giữa producers/consumers | Message parse fail, silent drop/reject | Không có schema versioning bắt buộc ở mọi stream | Cao |
| Redis saturation/SPOF | Toàn hệ thống dừng ingest/compute/execution | Tập trung mọi traffic và coordination | Cao |
| Duplicate/competing writes vào candles | Dữ liệu lịch sử không nhất quán, khó audit | Signal engine và DB writer cùng ghi candles | Cao |
| In-memory pending state mất khi restart (bridge) | Mất liên kết lifecycle-report với intent | `pending_intents` không persist | Trung bình |
| Scan discovery scale kém | Delay bắt stream mới, tăng CPU Redis | Phụ thuộc `SCAN` polling | Trung bình |

### Decision records ngầm định rút ra từ code

1. **Event-driven first, DB second**: mọi đường dữ liệu chính đi qua Redis stream rồi mới persist.
2. **Per-symbol isolation là trục scale chính**: key theo symbol ở hầu hết domain streams/state.
3. **At-least-once semantics + idempotency downstream**: dùng consumer group + xack, cộng với upsert/on-conflict tại DB.
4. **State in Redis, history in Timescale**: read model tách live vs historical cho dashboard.
5. **Fail-soft cho AI**: AI được tách queue/worker trong signal engine để không chặn loop ingest-calculate.
6. **Security/risk ưu tiên ở execution boundary**: enforce whitelist, SL/TP, notional trước khi tạo order thực thi.

## 5) Evolution path cho roadmap

### Đề xuất tiến hóa theo pha

#### Phase A — Stabilize contracts & ownership
- Chuẩn hóa event schema (JSON schema/pydantic shared package) cho các stream: candle/order/execution/position/account.
- Định nghĩa **single writer ownership** cho `aureus_candles` (chỉ một service ghi).
- Thêm schema version + compatibility tests giữa gateway/signal/bridge/db-writer.

#### Phase B — Decouple hot path
- Tách AI orchestration ra service riêng (hoặc worker process riêng), giữ signal loop lean.
- Tách persistence writer theo domain (market-data writer vs execution writer) để giảm contention.
- Giảm scan polling bằng stream registry hoặc explicit subscription config.

#### Phase C — Reliability & scale
- Redis HA plan (sentinel/cluster) + backpressure policy rõ ràng.
- Persist minimal correlation state cho execution bridge (trace_id intents) để survive restart.
- Bổ sung replay/reconciliation jobs đối soát Redis stream ↔ TimescaleDB.

#### Phase D — Productization architecture
- Formal API boundary giữa dashboard API và domain services (query/read model riêng).
- Thêm SLO-level observability cho end-to-end latency (gateway -> execution ack).
- Chuẩn hóa ADR chính thức cho execution mode, data retention, stream naming/versioning.

### Ưu tiên implementation cho roadmap requirements

1. **Contract governance trước** (nếu không sẽ phát sinh lỗi chéo service khi mở rộng feature).
2. **Ownership dữ liệu candles/snapshots** ngay đầu (tránh chi phí sửa dữ liệu lớn về sau).
3. **Scale theo symbol + tách writer** trước khi tăng số symbol/throughput.
4. **HA Redis và recovery semantics** trước khi mở sang live trading khối lượng lớn.

## Nguồn nội bộ đã đối chiếu

- `D:/Aureus/.claude/worktrees/agent-a42a69cd/docker-compose.dev.yml`
- `D:/Aureus/.claude/worktrees/agent-a42a69cd/docker-compose.prod.yml`
- `D:/Aureus/.claude/worktrees/agent-a42a69cd/services/aureus-gateway/main.py`
- `D:/Aureus/.claude/worktrees/agent-a42a69cd/services/aureus-signal/engine/live_engine.py`
- `D:/Aureus/.claude/worktrees/agent-a42a69cd/services/aureus-signal/engine/orders.py`
- `D:/Aureus/.claude/worktrees/agent-a42a69cd/services/aureus-db-writer/main.py`
- `D:/Aureus/.claude/worktrees/agent-a42a69cd/services/aureus-nautilus-node/{main.py,settings.py,execution_client.py,sync_worker.py}`
- `D:/Aureus/.claude/worktrees/agent-a42a69cd/services/aureus-nautilus-bridge/main.py`
- `D:/Aureus/.claude/worktrees/agent-a42a69cd/services/aureus-dashboard/api/main.py`
- `D:/Aureus/.claude/worktrees/agent-a42a69cd/services/aureus-bridge-metrics-exporter/main.py`
- `D:/Aureus/.claude/worktrees/agent-a42a69cd/docs/planning-artifacts/architecture.md`
