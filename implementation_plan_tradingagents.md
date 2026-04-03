# Tích hợp TradingAgents Market Data Node vào Aureus (không phá vỡ pipeline hiện tại)

Mục tiêu là đưa năng lực `TradingAgents` (đặc biệt dataflow/vendor routing) vào `Aureus` để mở rộng nguồn market data, nhưng vẫn giữ tương thích tuyệt đối với luồng ingest hiện tại của `aureus-nautilus-node` (`Redis Stream -> AureusMarketDataClient -> Nautilus msg_bus`).

---

## SWOT Analysis

### 📊 Phân tích dựa trên Codebase hiện tại

**Codebase audit date:** 2026-04-03 | **GitNexus index:** 3147 symbols, 130 execution flows

| Component | File | Lines | Trạng thái |
|---|---|---|---|
| Data Client | [data_client.py](file:///d:/Aureus/services/aureus-nautilus-node/data_client.py) | 192 | Redis-only, no provider abstraction |
| Settings | [settings.py](file:///d:/Aureus/services/aureus-nautilus-node/settings.py) | 72 | No provider/mode config |
| Rollout Gates | [rollout_gates.py](file:///d:/Aureus/services/aureus-nautilus-node/rollout_gates.py) | 125 | Gate framework exists (2 stages) |
| Main Runtime | [main.py](file:///d:/Aureus/services/aureus-nautilus-node/main.py) | 138 | No provider routing |

---

### ✅ Strengths (Điểm mạnh)

1. **Kiến trúc rollout gate đã sẵn sàng:** `rollout_gates.py` có framework gate 2 giai đoạn (`SHADOW_TO_PAPER`, `PAPER_TO_LIVE`) với metric evidence — hoàn toàn reuse được cho TradingAgents rollout.
2. **Candle schema chặt chẽ:** `AureusMarketDataClient.REQUIRED_FIELDS = ("open", "high", "low", "close", "volume", "timestamp")` — mọi nguồn dữ liệu mới chỉ cần chuẩn hóa về 6 field này.
3. **Metric tracking có sẵn:** 4 metric (`duplicates_total`, `stream_gap_total`, `malformed_payload_total`, `read_error_total`) sẵn trong data client — tái sử dụng cho so sánh chất lượng feed.
4. **Test suite resilience mạnh:** Đã có 4 test file cho data path (chaos, dedup, replay, resilience) — đảm bảo regression khi thêm provider mới.
5. **Pipeline tách biệt rõ ràng:** `aureus-signal` engine hoạt động độc lập — không phụ thuộc directly vào cách ingest data, chỉ cần candle payload đúng schema.

### ⚠️ Weaknesses (Điểm yếu)

1. **Không có provider abstraction:** `AureusMarketDataClient` gắn chặt với Redis — `__init__` nhận `redis_client`, `_poll_market_data_once` gọi `xread` trực tiếp. Cần refactor thành provider interface trước khi plug TradingAgents.
2. **`main.py` không có provider routing:** Runtime hiện tại hardcode flow `config → node → wait`, không có logic chọn data source theo mode. Plan đề xuất thêm routing logic nhưng `main.py` hiện không khởi tạo `AureusMarketDataClient` trực tiếp — cần xác định rõ điểm inject.
3. **`settings.py` frozen dataclass:** `NautilusNodeSettings` dùng `@dataclass(frozen=True)` → thêm field mới (`provider`, `symbol_map`, `vendor`) sẽ break backward compat nếu test code khởi tạo trực tiếp (không qua `from_env()`).
4. **Symbol universe gap nghiêm trọng:** Aureus dùng `XAUUSD`, `BTCUSD` (FX/metal/crypto) — TradingAgents thiên equities (`yfinance`, `alpha_vantage`). Mapping thực tế chưa được validate.
5. **Dependency isolation chưa rõ:** Plan chưa đề cập `TradingAgents` package sẽ được install như thế nào (pip, submodule, container riêng?) — ảnh hưởng Docker image size và build time.

### 🚀 Opportunities (Cơ hội)

1. **Multi-venue data redundancy:** Shadow mode cho phép chạy song song 2 nguồn data, phát hiện anomaly/latency issues sớm — tăng reliability cho production.
2. **Vendor fallback pattern:** TradingAgents vendor routing/fallback là pattern có sẵn — nếu adapt được sẽ giảm downtime khi MT5 gateway disconnect.
3. **Mở rộng asset class:** Nếu bridge thành công cho equities (SPY, AAPL), Aureus có thể mở rộng từ FX-only sang multi-asset, tăng tính thương mại.
4. **AI-driven market insights:** TradingAgents framework hỗ trợ tích hợp AI agents cho phân tích market — có thể feed insights xuống `aureus-signal` engine trong tương lai.
5. **Provider interface tạo nền tảng:** Refactor provider abstraction không chỉ serve TradingAgents mà còn mở đường cho bất kỳ nguồn data nào (Binance WS, Polygon, v.v.).

### 🔴 Threats (Rủi ro)

1. **API rate-limit & cost:** `yfinance` / `alpha_vantage` có rate-limit thấp (5-500 req/min). Với poll interval 100ms hiện tại, sẽ bị throttle ngay lập tức nếu không có caching layer.
2. **Data latency mismatch:** MT5 gateway push real-time qua Redis stream, TradingAgents pull period-based (REST API). Latency gap có thể 5-60 giây → shadow comparison sẽ misleading nếu không normalize timing.
3. **TradingAgents maturity risk:** Nếu TradingAgents library thay đổi API hoặc ngưng maintain, adapter layer trở thành tech debt.
4. **Scope creep:** Plan hiện tại touch 6+ files trong một service. Nếu không phase rõ (adapter → config → runtime → gate → test), dễ introduce regression vào data pipeline đang chạy production.
5. **Symbol mapping false sense of security:** Config `AUREUS_TRADINGAGENTS_SYMBOL_MAP` chỉ resolve tên symbol. Chưa handle timezone differences (market hours equities vs 24h FX), volume semantics (lots vs shares), hay price precision differences.

---

## User Review Required

> [!IMPORTANT]
> **Quyết định kiến trúc cần chốt:**
> 1. Chọn hướng tích hợp ban đầu:
>    - **A. Adapter trong Aureus (khuyến nghị):** tạo lớp adapter gọi `TradingAgents` và chuẩn hóa output về payload candle hiện tại.
>    - **B. Nhúng trực tiếp module TradingAgents vào runtime node:** coupling cao hơn, khó kiểm soát version/dependency.
> 2. Chọn chiến lược vận hành ban đầu:
>    - **Shadow mode** (khuyến nghị): TradingAgents chạy song song, chỉ ghi stream shadow để so sánh chất lượng dữ liệu.
>    - **Active mode**: TradingAgents là nguồn chính ngay từ đầu.

> [!WARNING]
> `TradingAgents` thiên về equities (yfinance/alpha_vantage). Aureus đang chạy theo symbol/stream nội bộ (ví dụ `XAUUSD`). Cần chốt rõ mapping symbol universe (FX/metal/cfd) trước khi bật production.

> [!CAUTION]
> **Từ SWOT Analysis - Rủi ro cần xử lý trước khi implement:**
> 1. **Rate-limit protection** — cần caching/throttle layer trong adapter, không poll raw API mỗi 100ms.
> 2. **Dependency strategy** — chốt TradingAgents install method (pip extra, separate container, hay vendored submodule).
> 3. **Data latency contract** — define acceptable lag giữa Redis source và TradingAgents source khi chạy shadow.

---

## Proposed Changes

### Phase 0 — Prerequisites (Mới thêm từ SWOT)

Trước khi code bất kỳ thứ gì, cần hoàn thành:

1. **Validate TradingAgents API compatibility:**
   - Cài thử `TradingAgents` trong virtualenv riêng, kiểm tra:
     - Có hỗ trợ FX/metal symbols không? (`XAUUSD`, `BTCUSD`)
     - API call latency trung bình?
     - Rate-limit thực tế cho free tier?
   - Nếu không hỗ trợ FX/metal → dừng plan, chuyển hướng sang provider phù hợp hơn.

2. **Chốt dependency strategy:**
   - Thêm vào `requirements.txt` as optional dependency, hoặc
   - Container riêng expose gRPC/REST endpoint.

---

### Phase 1 — Provider Abstraction (Mới thêm từ SWOT)

Refactor `AureusMarketDataClient` thành provider pattern trước khi thêm TradingAgents.

#### [NEW] [market_data_provider.py](file:///d:/Aureus/services/aureus-nautilus-node/market_data_provider.py)
- Tạo abstract `MarketDataProvider` protocol:
  - `async poll() -> List[CandlePayload]`
  - `metrics() -> Dict[str, int]`
- Implement `RedisMarketDataProvider` extract từ logic hiện tại của `_poll_market_data_once`.
- Giữ nguyên behavior 100% — đây là pure refactor.

#### [MODIFY] [data_client.py](file:///d:/Aureus/services/aureus-nautilus-node/data_client.py)
- `AureusMarketDataClient.__init__` nhận `provider: MarketDataProvider` thay vì `redis_client` trực tiếp.
- `_poll_market_data_once` delegate sang `provider.poll()`.
- **Backward compat:** factory method `from_redis(redis_client, ...)` để code cũ không đổi.

---

### Phase 2 — TradingAgents Adapter

#### [NEW] [tradingagents_adapter.py](file:///d:/Aureus/services/aureus-nautilus-node/tradingagents_adapter.py)
- Tạo `TradingAgentsMarketDataAdapter` implement `MarketDataProvider`:
  - Gọi dataflow API theo cơ chế vendor routing/fallback của TradingAgents.
  - **Thêm caching layer:** Cache response trong N giây để tránh rate-limit (configurable via `AUREUS_TA_CACHE_TTL_SECONDS`).
  - Chuẩn hóa dữ liệu sang format bắt buộc: `open/high/low/close/volume/timestamp`.
  - Convert timestamp về epoch ms và validate tương thích với `AureusMarketDataClient.REQUIRED_FIELDS`.
- Bổ sung error taxonomy riêng (rate-limit, vendor-fallback, malformed records) để tiện metric/logging.
- **Symbol mapping logic:** Nhận `symbol_map: Dict[str, str]` để translate `XAUUSD` → vendor-specific symbol.

---

### Phase 3 — Runtime & Configuration

#### [MODIFY] [settings.py](file:///d:/Aureus/services/aureus-nautilus-node/settings.py)
- Thêm cờ cấu hình (với default backward-compatible):
  - `AUREUS_MARKET_DATA_PROVIDER=redis|tradingagents|shadow` (default: `redis`)
  - `AUREUS_TRADINGAGENTS_VENDOR` (hoặc danh sách fallback)
  - `AUREUS_TRADINGAGENTS_SYMBOL_MAP` (JSON map symbol Aureus -> symbol upstream)
  - `AUREUS_TA_CACHE_TTL_SECONDS` (default: 30)
- Validate config fail-fast khi mapping thiếu key quan trọng.
- **Lưu ý `frozen=True`:** thêm field mới vào `NautilusNodeSettings` — cần update tất cả test constructors.

#### [MODIFY] [main.py](file:///d:/Aureus/services/aureus-nautilus-node/main.py)
- Khởi tạo provider theo mode:
  - `redis`: hành vi hiện tại (default).
  - `shadow`: vừa ingest hiện tại vừa pull TradingAgents, ghi stream shadow.
  - `tradingagents`: feed chính từ adapter (sau khi shadow ổn định).

#### [MODIFY] [sync_worker.py](file:///d:/Aureus/services/aureus-nautilus-node/sync_worker.py)
- Không đổi contract sự kiện order/position.
- Chỉ bổ sung metadata `source` khi cần truy vết dữ liệu liên service.

---

### Phase 4 — Observability & Safety Gates

#### [MODIFY] [rollout_gates.py](file:///d:/Aureus/services/aureus-nautilus-node/rollout_gates.py)
- Thêm gate cho TradingAgents provider:
  - Tỉ lệ malformed tối đa (default: 1%)
  - Ngưỡng fallback liên tiếp (default: 3 lần)
  - Độ trễ data cập nhật (default: 60s max lag)
  - **Mới:** so sánh shadow drift giữa Redis source và TradingAgents (candle mismatch rate)
- Gate fail -> tự động về `redis` mode (nếu cấu hình cho phép).

---

### Phase 5 — Test Coverage

#### [NEW] [test_market_data_provider.py](file:///d:/Aureus/services/aureus-nautilus-node/tests/test_market_data_provider.py)
- Test `RedisMarketDataProvider` tương đương behavior với data_client tests hiện có.
- Test provider interface contract.

#### [NEW] [test_tradingagents_adapter.py](file:///d:/Aureus/services/aureus-nautilus-node/tests/test_tradingagents_adapter.py)
- Test mapping payload từ TradingAgents -> candle schema Aureus.
- Test fallback vendor khi lỗi rate-limit.
- Test reject payload thiếu field/time invalid.
- Test caching behavior (cache hit / cache expired).

#### [MODIFY] [test_data_client.py](file:///d:/Aureus/services/aureus-nautilus-node/tests/test_data_client.py)
- Bổ sung case nhận payload qua provider interface (không phá hành vi hiện tại).
- Update constructor calls nếu `from_redis()` factory thay đổi signature.

#### [MODIFY] [test_rollout_gates.py](file:///d:/Aureus/services/aureus-nautilus-node/tests/test_rollout_gates.py)
- Test gate trigger khi provider TradingAgents vượt ngưỡng lỗi.
- Test shadow drift detection.

---

## Verification Plan

### Automated Tests
1. Cài dependencies service:
```powershell
python -m pip install -r d:\Aureus\services\aureus-nautilus-node\requirements.txt
```
2. Chạy test hiện có (regression check):
```powershell
python -m pytest d:\Aureus\services\aureus-nautilus-node\tests\ -q --tb=short
```
3. Chạy test mới sau khi tích hợp adapter:
```powershell
python -m pytest d:\Aureus\services\aureus-nautilus-node\tests\test_market_data_provider.py -q
python -m pytest d:\Aureus\services\aureus-nautilus-node\tests\test_tradingagents_adapter.py -q
python -m pytest d:\Aureus\services\aureus-nautilus-node\tests\test_rollout_gates.py -q
```

### Manual Verification
1. **Phase 0 gate:** Confirm TradingAgents supports FX/metal symbols trước khi proceed.
2. **Phase 1 smoke test:** Chạy node ở `redis` mode sau refactor provider — confirm behavior 100% identical.
3. Chạy node ở `shadow` mode, giữ feed Redis hiện tại làm chuẩn.
4. So sánh trong 30-60 phút:
   - Tần suất candle giữa `primary` và `shadow`
   - Số bản ghi malformed
   - Latency phân phối candle
   - **Mới:** Shadow drift rate (% candle mismatch)
5. Xác nhận các metric/gate không vượt ngưỡng trước khi cân nhắc `tradingagents` mode.
6. Nếu có mismatch symbol/timezone, cập nhật `AUREUS_TRADINGAGENTS_SYMBOL_MAP` trước khi rollout tiếp.
