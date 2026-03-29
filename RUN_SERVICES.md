# Hướng dẫn Khởi động các Dịch vụ Aureus

Tài liệu này hướng dẫn cách khởi chạy toàn bộ hệ thống Aureus trên môi trường Windows (sử dụng WSL 2 cho backend và Docker Compose cho các core services).
Lưu ý: Tất cả các chiến lược hay giải pháp đề xuất ra phải dựa trên cơ sở định lượng được. Thực tế có thể tính toán được. Tuyệt đối không đưa ra chiến lược hay giải pháp dựa trên cảm nhận hay suy đoán.

## 1. Yêu cầu Hệ thống
- Docker Desktop (đang bật WSL 2 integration).
- WSL 2 (Ubuntu-24.04).
- Python 3.12+ (trong WSL).
- Node.js (để chạy frontend Next.js).

## 2. Core Backend Services (Docker)
Các dịch vụ nền tảng (Database, Message Queue, Signal Engine, Data Gateway) được chạy trong Docker qua `docker-compose.dev.yml` (hoặc `aureus-foundation.yml` cho môi trường production).

> **Lưu ý**: Hãy chắc chắn terminal đang ở thư mục gốc project: `d:\AIFramework\aureus` (WSL path: `/mnt/d/Aureus`).

Môi trường Development có thể khởi tạo nhanh bằng script có sẵn.
Mở PowerShell và chạy lệnh sau để bật các core services:

```powershell
wsl -d Ubuntu-24.04 -e bash -c "cd /mnt/d/Aureus && ./scripts/dev-service.sh"
```

Lệnh này sẽ build và khởi động:
- `aureus_redis_dev` (port host mặc định: `6380`)
- `aureus_timescaledb_dev` (port host mặc định: `5433`)
- `aureus-gateway-dev`
- `aureus-db-writer-dev`
- `aureus-signal-dev`
- `aureus-dashboard-api-dev`
- `aureus-nautilus-node-dev`

### 2.1 Build & chạy riêng Nautilus Stack (mới)
Sau khi đã thêm service vào `docker-compose.dev.yml`, dùng lệnh sau để build và chạy bộ service mới:

```powershell
wsl -d Ubuntu-24.04 -e bash -c "cd /mnt/d/Aureus && docker compose -f docker-compose.dev.yml up --build -d nautilus_trader-dev aureus-nautilus-node-dev aureus-nautilus-bridge-dev"
```

Service được khởi động:
- `nautilus-trader-dev` (image prebuilt `ghcr.io/nautechsystems/nautilus_trader:nightly`)
- `aureus-nautilus-node-dev` (build từ `services/aureus-nautilus-node/Dockerfile`)
- `aureus-nautilus-bridge-dev` (build từ `services/aureus-nautilus-bridge/Dockerfile`)

#### 2.1.1 Bật stream-mode cho execution report lifecycle
Mặc định bridge chạy với `NAUTILUS_ADAPTER_MODE=simulated` để tương thích flow cũ. Để bridge ingest lifecycle reports từ Redis stream, đặt biến môi trường khi chạy compose:

```powershell
wsl -d Ubuntu-24.04 -e bash -c "cd /mnt/d/Aureus && NAUTILUS_ADAPTER_MODE=stream NAUTILUS_LIFECYCLE_STREAM_PATTERN='aureus:stream:*:nautilus_execution' docker compose -f docker-compose.dev.yml up --build -d aureus-nautilus-node-dev aureus-nautilus-bridge-dev"
```

Bridge sẽ đọc thêm các stream khớp với `NAUTILUS_LIFECYCLE_STREAM_PATTERN` và publish execution events chuẩn hóa về `aureus:stream:{symbol}:execution`.

#### 2.1.2 Chạy test cho service mới (Node + Bridge + E2E flow)
Sau khi service mới đã `Up`, chạy các test sau trong WSL:

```powershell
# 1) Smoke unit cho Nautilus Node
wsl -d Ubuntu-24.04 -e bash -lc "cd /mnt/d/Aureus/services/aureus-nautilus-node && python3 -m pytest tests/test_config_validation.py tests/test_execution_risk_controls.py tests/test_sync_worker_contract.py -v"

# 2) Regression policy/rollout cho Nautilus Node (Live Trading V1)
wsl -d Ubuntu-24.04 -e bash -lc "cd /mnt/d/Aureus/services/aureus-nautilus-node && python3 -m pytest tests/test_rollout_gates.py tests/test_shadow_canary_flow.py tests/test_execution_client_policy.py tests/test_execution_client.py tests/test_execution_risk_controls.py -q"

# 3) Smoke unit cho Nautilus Bridge
wsl -d Ubuntu-24.04 -e bash -lc "cd /mnt/d/Aureus/services/aureus-nautilus-bridge && python3 -m pytest tests/test_mapper.py tests/test_bridge_idempotency.py -v"

# 4) Regression lineage cho Nautilus Bridge (Live Trading V1)
wsl -d Ubuntu-24.04 -e bash -lc "cd /mnt/d/Aureus/services/aureus-nautilus-bridge && python3 -m pytest tests/test_bridge_lineage.py tests/test_bridge_idempotency.py tests/test_mapper.py -q"

# 5) Coverage evidence cho Node + Bridge (xuất JSON để lưu proof)
wsl -d Ubuntu-24.04 -e bash -lc "cd /mnt/d/Aureus && python3 -m pytest services/aureus-nautilus-node/tests/test_rollout_gates.py services/aureus-nautilus-node/tests/test_shadow_canary_flow.py services/aureus-nautilus-node/tests/test_execution_client_policy.py services/aureus-nautilus-node/tests/test_execution_client.py services/aureus-nautilus-bridge/tests/test_bridge_lineage.py services/aureus-nautilus-bridge/tests/test_bridge_idempotency.py services/aureus-nautilus-bridge/tests/test_mapper.py --cov=services/aureus-nautilus-node --cov=services/aureus-nautilus-bridge --cov-report=json:/mnt/d/Aureus/tmp_coverage_phase14.json -q"

# 6) Test E2E Redis flow (v1)
wsl -d Ubuntu-24.04 -e bash -lc "cd /mnt/d/Aureus && python3 scripts/test_nautilus_redis_flow.py --redis-host 127.0.0.1 --redis-port 6380 --symbol XAUUSD --timeout 25"

# 7) Test E2E Redis flow (v2)
wsl -d Ubuntu-24.04 -e bash -lc "cd /mnt/d/Aureus && python3 scripts/test_nautilus_redis_flow_v2.py --redis-host 127.0.0.1 --redis-port 6380 --symbol XAUUSD --timeout 30"
```

Kết quả mong đợi:
- Unit/regression tests trả `PASSED` hoặc `X passed` và exit code `0`.
- Coverage command tạo file `d:\Aureus\tmp_coverage_phase14.json` (WSL path: `/mnt/d/Aureus/tmp_coverage_phase14.json`).
- Flow test trả log `SUCCESS`/`[PASS]` và exit code `0`.

*(WEB của Dashboard có thể chạy native như phần bên dưới.)*

### 2.2 Build & chạy Mini Monitoring Stack (Prometheus + Grafana + Exporter)
Dùng lệnh sau để build và chạy các service monitoring trong `docker-compose.dev.yml`:

```powershell
wsl -d Ubuntu-24.04 -u root bash -c "docker compose --project-directory /mnt/d/Aureus -f /mnt/d/Aureus/docker-compose.dev.yml up --build -d redis-exporter-dev aureus-bridge-metrics-dev prometheus-dev grafana-dev"
```

Service được khởi động:
- `redis-exporter-dev`
- `aureus-bridge-metrics-dev`
- `prometheus-dev` (host: `http://localhost:19590`)
- `grafana-dev` (host: `http://localhost:13555`, default login: `admin/admin`)

### 2.3 Kiểm tra nhanh Monitoring Stack

```powershell
# Kiểm tra trạng thái containers monitoring
wsl -d Ubuntu-24.04 -u root bash -c "docker compose --project-directory /mnt/d/Aureus -f /mnt/d/Aureus/docker-compose.dev.yml ps redis-exporter-dev aureus-bridge-metrics-dev prometheus-dev grafana-dev"

# Kiểm tra target scrape trong Prometheus
wsl -d Ubuntu-24.04 -u root bash -c "docker exec prometheus-dev wget -qO- http://localhost:9090/api/v1/targets"

# Kiểm tra endpoint metrics của exporter
wsl -d Ubuntu-24.04 -u root bash -c "docker exec aureus-bridge-metrics-dev wget -qO- http://localhost:9108/metrics | head -n 40"
```

### 2.4 Troubleshooting cho Monitoring
- Nếu dashboard chưa hiện dữ liệu: chạy flow test để tạo traffic (`scripts/test_nautilus_redis_flow.py`).
- Nếu Prometheus target DOWN: kiểm tra logs bằng `docker logs prometheus-dev` hoặc `docker logs aureus-bridge-metrics-dev`.
- Nếu quên mật khẩu Grafana: xóa volume `grafana_data_dev` rồi chạy lại stack để reset về `admin/admin`.

---

## 3. Dashboard Web UI (Native Windows/Powershell)
Giao diện frontend (Next.js) được chạy bằng script tiện ích giúp UI reload cực nhanh (HMR).

Để khởi động Web UI trong môi trường Dev, mở PowerShell và chạy lệnh:

```powershell
wsl -d Ubuntu-24.04 -e bash -c "cd /mnt/d/Aureus && ./scripts/dev-web.sh"
```

Script này sẽ tự động cài NPM packages và chạy Development Server một cách đồng bộ.
Web UI sẽ có sẵn ở: `http://localhost:17222`.

---

## 4. Quy tắc Cập nhật & Restart Service (QUAN TRỌNG)

Khi người dùng hoặc AI (Antigravity) thực hiện thay đổi mã nguồn (Python/API/Signal), do các dịch vụ backend chạy trong Docker **không sử dụng volume mount cho code** (để tối ưu performance), **BẮT BUỘC** phải rebuild và restart lại container để áp dụng thay đổi.

**Lưu ý cho AI Assistant**: Sau khi hoàn thành một Step hoặc cập nhật Feature liên quan đến service (Signal, API, DB Writer, Gateway), AI phải **tự động** thực hiện lệnh build và restart service tương ứng mà không cần người dùng nhắc nhở.

Nếu gặp lỗi **404 Not Found** sau khi thêm endpoint mới, hoặc logic mới không chạy, hãy thực hiện restart service tương ứng qua WSL.

### Lệnh Rebuild/Restart từng Service cụ thể:
Mở PowerShell và chạy lệnh (thay `[SERVICE_NAME]` bằng service cần restart trong `docker-compose.dev.yml`):

```powershell
# Ví dụ: Rebuild + restart Dashboard API (dev)
wsl -d Ubuntu-24.04 -u root bash -c "cd /mnt/d/Aureus && docker compose -f docker-compose.dev.yml up -d --build aureus-dashboard-api-dev"

# Ví dụ: Rebuild + restart Signal Engine (dev)
wsl -d Ubuntu-24.04 -u root bash -c "cd /mnt/d/Aureus && docker compose -f docker-compose.dev.yml up -d --build aureus-signal-dev"

# Ví dụ: Rebuild + restart Nautilus Bridge (dev)
wsl -d Ubuntu-24.04 -u root bash -c "cd /mnt/d/Aureus && docker compose -f docker-compose.dev.yml up -d --build aureus-nautilus-bridge-dev"
```

### Lệnh Rebuild/Restart riêng Nautilus + Node + Bridge:
```powershell
wsl -d Ubuntu-24.04 -u root bash -c "cd /mnt/d/Aureus && docker compose -f docker-compose.dev.yml up -d --build nautilus_trader-dev aureus-nautilus-node-dev aureus-nautilus-bridge-dev"
```

### Lệnh Restart toàn bộ hệ thống dev:
```powershell
wsl -d Ubuntu-24.04 -u root bash -c "cd /mnt/d/Aureus && docker compose -f docker-compose.dev.yml up -d --build"
```

### Lệnh kiểm tra sau khi chạy/build lại:
```powershell
# Xem trạng thái 3 service mới
wsl -d Ubuntu-24.04 -u root bash -c "cd /mnt/d/Aureus && docker compose -f docker-compose.dev.yml ps nautilus_trader-dev aureus-nautilus-node-dev aureus-nautilus-bridge-dev"

# Kiểm tra health cơ bản bằng restart count = 0
wsl -d Ubuntu-24.04 -u root bash -c "cd /mnt/d/Aureus && docker inspect -f '{{.Name}}|{{.State.Status}}|restarts={{.RestartCount}}' nautilus-trader-dev aureus-nautilus-node-dev aureus-nautilus-bridge-dev"

# Xem log bridge để xác nhận có publish execution event
wsl -d Ubuntu-24.04 -u root bash -c "cd /mnt/d/Aureus && docker logs --tail 100 aureus-nautilus-bridge-dev"
```


---

## 5. Khắc phục sự cố (Troubleshooting)

### Lỗi Cổng 3000 hoặc 8001 đang bị sử dụng (Address already in use)
Nếu server bị treo không giải phóng cổng, hãy diệt các process bị kẹt:

- **Diệt Web UI bị kẹt ở Windows (Port 3000)**:
  ```powershell
  Stop-Process -Name "node" -Force -ErrorAction SilentlyContinue
  ```

- **Diệt API Backend (nếu chạy native) bị kẹt ở WSL (Port 8001)**:
  ```powershell
  wsl -d Ubuntu-24.04 -e bash -c "killall python3"
  ```

### Kiểm tra Logs của Docker Service:
```powershell
wsl -d Ubuntu-24.04 -u root bash -c "cd /mnt/d/Aureus && docker compose -f aureus-foundation.yml logs -f [SERVICE_NAME]"
```

### Playbook: Điều tra & xử lý lỗi MT5 không gửi data sang Gateway (TCP 5556)

#### 1) Triệu chứng thường gặp
- MT5 EA báo không gửi được dữ liệu sang gateway.
- Dashboard không thấy tick/candle mới.
- Kiểm tra nhanh thấy MT5 connect `localhost:5556` nhưng không có listener phía gateway.

#### 2) Quy trình điều tra (theo thứ tự)

```powershell
# (A) Kiểm tra service gateway có đang chạy không
wsl -d Ubuntu-24.04 -e bash -lc "cd /mnt/d/Aureus && docker compose -f docker-compose.dev.yml ps aureus-gateway-dev"

# (B) Kiểm tra host port mapping của container gateway (phải có 5556)
wsl -d Ubuntu-24.04 -e bash -lc "cd /mnt/d/Aureus && docker compose -f docker-compose.dev.yml ps"

# (C) Kiểm tra listener trong WSL (phải LISTEN trên :5556)
wsl -d Ubuntu-24.04 -e bash -lc "ss -ltnp | grep 5556 || true"

# (D) Kiểm tra kết nối từ host Windows tới 127.0.0.1:5556
Test-NetConnection -ComputerName 127.0.0.1 -Port 5556 | Select-Object ComputerName,RemotePort,TcpTestSucceeded

# (E) Kiểm tra log gateway để xác nhận có nhận/parse message
wsl -d Ubuntu-24.04 -e bash -lc "docker logs --tail 120 aureus-gateway-dev 2>&1"
```

#### 3) Root cause đã gặp và xác nhận
- Container `aureus-gateway-dev` bị `Exited (255)` nên MT5 vẫn gửi `localhost:5556` nhưng gateway process không còn sống để nhận data.
- Bằng chứng: `docker ps -a` trả `aureus-gateway-dev|Exited (255)`; sau khi `docker start`, logs xuất hiện lại `Processed TICK ...`.

#### 4) Cách xử lý chuẩn (triệt để)

```powershell
# (1) Rebuild + restart gateway service
wsl -d Ubuntu-24.04 -u root bash -lc "docker compose --project-directory /mnt/d/Aureus -f /mnt/d/Aureus/docker-compose.dev.yml up -d --build aureus-gateway-dev"

# (2) Verify container state
wsl -d Ubuntu-24.04 -e bash -lc "docker compose --project-directory /mnt/d/Aureus -f /mnt/d/Aureus/docker-compose.dev.yml ps aureus-gateway-dev"

# (3) Verify listener + connectivity + ingestion logs
wsl -d Ubuntu-24.04 -e bash -lc "ss -ltnp | grep 5556 || true"
Test-NetConnection -ComputerName 127.0.0.1 -Port 5556 | Select-Object ComputerName,RemotePort,TcpTestSucceeded
wsl -d Ubuntu-24.04 -e bash -lc "docker logs --since 3m aureus-gateway-dev 2>&1 | tail -n 120"
```

**Durable fix đã áp dụng trong compose** (`docker-compose.dev.yml`):
- `restart: unless-stopped` cho `aureus-gateway-dev`.
- `healthcheck` kiểm tra TCP `127.0.0.1:5556` trong container.

Sau khi chạy lệnh trên, bắt buộc verify lại:
- `ss -ltnp | grep 5556` có `LISTEN`.
- `Test-NetConnection ...` trả `TcpTestSucceeded = True`.
- `docker logs aureus-gateway-dev` có dòng `process_message ... Processed TICK/CANDLE ...`.

#### 5) Checklist verify hoàn tất
- [x] `aureus-gateway-dev` trạng thái `Up`.
- [x] Port `5556` đã `LISTEN`.
- [x] MT5 gửi lại tick/candle thành công.
- [x] Dashboard hiển thị dữ liệu realtime.

---

## 6. Reset Cache CHOCH/BOS/OB (Redis)

Khi logic structure (CHOCH/BOS) trong Signal Engine bị thay đổi, dữ liệu cũ trong Redis có thể sai (OB sai vị trí, CHOCH/BOS label không đúng). Cần reset cache và để engine re-detect từ đầu.

**Script**: `services/aureus-signal/reset_structure_cache.py`

### Chạy reset:
```powershell
# 1. Copy script vào container + chạy
wsl -d Ubuntu-24.04 -u root bash -c "docker cp /mnt/d/Aureus/services/aureus-signal/reset_structure_cache.py aureus-signal:/app/reset_structure_cache.py && docker exec aureus-signal python /app/reset_structure_cache.py"

# 2. Restart signal engine để re-detect
wsl -d Ubuntu-24.04 -u root bash -c "docker restart aureus-signal"
```

### Script xóa những gì:
- **Swing points**: Xóa metadata `is_choch`, `choch_type`, `is_bos`, `bos_type`, `breakout_t`
- **OBs**: Xóa toàn bộ (sẽ được tạo lại khi engine re-detect CHOCH)
- **Sweep targets**: Xóa (sẽ tạo lại từ OB mới)
- **Candle actors**: Xóa các event `CHOCH_BREAKOUT`, `BOS_BREAKOUT`

### Debug swing points (kiểm tra kết quả):
```powershell
wsl -d Ubuntu-24.04 -u root bash -c "docker cp /mnt/d/Aureus/services/aureus-signal/debug_choch.py aureus-signal:/app/debug_choch.py && docker exec aureus-signal python /app/debug_choch.py"
```

---

## 7. Quy Tắc Chống Lỗi Hồi Quy (Anti-Regression & Core Logic Rules)

**QUAN TRỌNG:** Việc thêm tính năng mới tuyệt đối không được làm ảnh hưởng hoặc làm hỏng (degrade) các tính năng cốt lõi hiện có.

Khi AI Assistant (Antigravity) hoặc Developer được yêu cầu sửa đổi logic cốt lõi (như CHOCH, BOS, Order Block, Sweep logic):

1. **Tuân thủ logic gốc (MQL5 Parity):** Logic hiện tại của Signal Engine được port từ codebase MQL5 đã hoạt động ổn định. Mọi thay đổi phải hiểu rõ context lịch sử của code gốc.
2. **Không phân tích chủ quan:** Các vấn đề về thị trường (Structure, CHOCH, BOS) phải được định nghĩa bằng các công thức, thuật toán rõ ràng dựa trên Price Action (High/Low/Close), không dựa trên cảm tính hoặc giả định.
3. **Mô phỏng tác động (Impact Analysis):** Trước khi đục khoét các hàm core (VD: `_process_choch`, `_handle_no_zone_base`), phải liệt kê rõ việc sửa dòng code này sẽ ảnh hưởng tới đầu ra nào, và đảm bảo mọi edge cases đã được cover.
4. **Không tạo code "vá víu" (Patching):** Nếu một tính năng (VD: BOS) cần thêm mới, hãy thêm nhánh logic riêng gọn gàng thay vì viết lại toàn bộ luồng của tính năng khác (CHOCH) khiến nó fail. 
5. **Regression Verification:** Sau khi sửa core logic, AI **BẮT BUỘC** phải:
   - Reset Cache (xem mục 6).
   - Rebuild và Restart Docker container.
   - Run debug script (VD: `debug_choch.py`) để kiểm tra lại toàn bộ dữ liệu lịch sử xem số lượng và chất lượng signals có đúng chuẩn SMC rules không, trước khi thông báo hoàn thành cho người dùng.

## 8. Một số rules khác

*Ngoài lệnh chạy web ở phía trên, các lệnh khác phải chạy trong WSL và chạy lênh trên Ubuntu. Cấm dùng các lệnh cho Windows.*

```
wsl -d Ubuntu-24.04 <command>
```

1. Cấm chạy source code python kiểu inline như bên dưới. Viết script chạy riêng.

```
wsl -d Ubuntu-24.04 -u root bash -c "python3 -c \"import urllib.request, json; req = urllib.request.Request('http://localhost:8001/api/v1/backtest/XAUUSD/sync', method='POST', headers={'Content-Type': 'application/json'}, data=json.dumps({'start': '2026-02-25', 'end': '2026-03-01'}).encode()); resp = urllib.request.urlopen(req); print('API Responses: ' + resp.read().decode())\""
```

2. Cấm chạy psql trên Windows. Phải chạy trong WSL.

```
wsl -d Ubuntu-24.04 -u root bash -c "docker exec aureus_timescaledb psql -U aureus -d aureus -c 'SELECT symbol, count(1) FROM aureus_candles GROUP BY symbol;'"
```

3. Cấm chạy python trên Windows. Phải chạy trong WSL.

```
wsl -d Ubuntu-24.04 -u root bash -c "python services/aureus-signal/signal_computer.py --symbol XAUUSD --start 2026-02-24 --end 2026-03-04"
```

4. Cấm chạy docker trên Windows. Phải chạy trong WSL.

```
wsl -d Ubuntu-24.04 -u root bash -c "docker compose -f aureus-foundation.yml up -d --build"
```

5. Cấm chạy redis-cli trên Windows. Phải chạy trong WSL.

```
wsl -d Ubuntu-24.04 -u root bash -c "docker exec aureus_redis redis-cli"
```

6. Cấm sử dụng curl ở console. Phải viết script bằng python để gọi API.

7. Cấm viết script bằng shellscript hoặc các ngôn ngữ khác. Tất cả  các script phải sử dụng python.

8. Khi chạy các lệnh ở terminal, phải đọc log và đảm bảo không có lỗi. Nếu có lỗi, phải sửa lỗi và chạy lại.

9. Về plan test và cách thức test với cách verify kết quả test.
- Nghiêm cấm thực hiện test và report test như sau:
  - Test script quá lỏng lẻo — nó chỉ kiểm tra "API có trả response không?" thay vì "API có trả đúng response không?".
  - Sync API trả về status=name 'db_pool' is not defined (lỗi 500) → test vẫn ghi PASS vì nó nhận được response
  - Sync API trả operator does not exist (lỗi SQL) → vẫn PASS
  - Command format sai, signal engine không nhận → vẫn PASS

10. Với test Python trong WSL: nếu `python3 -m pytest` báo `No module named pytest`, phải chạy bằng virtualenv của repo để đảm bảo đúng dependencies:

```
wsl -d Ubuntu-24.04 -e bash -lc "cd /mnt/d/Aureus && .venv/bin/python -m pytest <test_paths> -q"
```

10.1. Với test của `services/aureus-signal`, ưu tiên chạy từ đúng working directory của service để tránh lỗi import/collection (`engine.*`):

```
wsl -d Ubuntu-24.04 -e bash -lc "cd /mnt/d/Aureus/services/aureus-signal && ../../.venv/bin/python -m pytest tests/test_template_strategy.py tests/test_strategy_determinism.py tests/test_strategy_scenario.py -q"
```

11. Khi kiểm tra LLM endpoint trong môi trường Docker dev:
- Không chạy `docker ...` trực tiếp ở PowerShell nếu máy không expose Docker CLI. Luôn chạy qua WSL:

```
wsl -d Ubuntu-24.04 -e bash -lc "cd /mnt/d/Aureus && docker compose -f docker-compose.dev.yml ps"
```

- `host.docker.internal` là hostname dành cho container truy cập host, không dùng để probe trực tiếp từ WSL host.
- Nếu cần verify endpoint, viết script Python riêng và chạy trong container service (ví dụ `aureus-signal-dev`) để đảm bảo đúng network context.
- Tránh gộp `docker cp` và `docker exec` có heredoc/quote phức tạp trong cùng một command vì dễ lỗi escaping. Nên tách thành 2 lệnh độc lập:
  1) `docker cp ...`
  2) `docker exec ...`
  rồi kiểm tra exit code từng bước trước khi chạy bước tiếp theo.

12. Khi dùng `gsd-tools` để xem trợ giúp command phase:
- Không chạy `node ".agent/get-shit-done/bin/gsd-tools.cjs" phase remove --help` vì `--help` có thể bị parse như phase number và gây thay đổi roadmap/state.
- Cách an toàn để kiểm tra command hỗ trợ:
  1) đọc workflow trong `.agent/get-shit-done/workflows/*.md`
  2) grep usage trong `.agent/get-shit-done/bin/gsd-tools.cjs` (ví dụ `phase remove <phase>`, `phase insert <after> <description>`)
- Luôn chạy trên branch làm việc và kiểm tra `git status --short` ngay sau command thăm dò.

Không cài package tạm vào system Python để tránh lệch môi trường giữa các lần chạy.

13. Dọn sạch data DB nhưng giữ lại `aureus_candles` (WSL + Docker, quote-safe):
- Không dùng `psql` trực tiếp trên host nếu chưa cài client.
- Dùng cách ổn định sau để tránh lỗi escaping quote:

```powershell
wsl -d Ubuntu-24.04 -e bash -lc "cd /mnt/d/Aureus && cat /mnt/d/Aureus/services/aureus-db-writer/scripts/clear_all_except_aureus_candles.sql | docker exec -i aureus_timescaledb_dev psql -U aureus -d aureus"
```

- Verify nhanh:

```powershell
wsl -d Ubuntu-24.04 -e bash -lc "docker exec -i aureus_timescaledb_dev psql -U aureus -d aureus < /mnt/d/Aureus/services/aureus-db-writer/scripts/verify_cleanup_counts.sql"
```