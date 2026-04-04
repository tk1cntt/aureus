# RUN_SERVICES (Compact)

Tài liệu vận hành nhanh cho môi trường dev của Aureus.

> [!IMPORTANT]
> Tất cả lệnh backend phải chạy qua WSL (`wsl -d Aureus ...`). Không chạy Python/Docker/psql/redis-cli trực tiếp trên Windows host.

---

## 1) Quick Start

### 1.1 Core backend services
```powershell
wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus && ./scripts/dev-service.sh"
```

Khởi động các service chính:
- `aureus_redis_dev` (host `6380`)
- `aureus_timescaledb_dev` (host `5433`)
- `aureus-gateway-dev`
- `aureus-db-writer-dev`
- `aureus-signal-dev`
- `aureus-dashboard-api-dev`
- `aureus-nautilus-node-dev`

### 1.2 Web UI
```powershell
wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus && ./scripts/dev-web.sh"
```

Mặc định dev:
- API: `http://localhost:8002`
- Web: `http://localhost:17222`

---

## 2) Rebuild/Restart

### 2.1 Rebuild 1 service
```powershell
wsl -d Aureus -u root bash -lc "cd /mnt/d/Aureus && docker compose -f docker-compose.dev.yml up -d --build <service_name>"
```

Ví dụ:
```powershell
wsl -d Aureus -u root bash -lc "cd /mnt/d/Aureus && docker compose -f docker-compose.dev.yml up -d --build aureus-signal-dev"
```

### 2.2 Rebuild toàn bộ dev stack
```powershell
wsl -d Aureus -u root bash -lc "cd /mnt/d/Aureus && docker compose -f docker-compose.dev.yml up -d --build"
```

### 2.3 Kiểm tra trạng thái/log
```powershell
wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus && docker compose -f docker-compose.dev.yml ps"
wsl -d Aureus -e bash -lc "docker logs --tail 120 aureus-signal-dev 2>&1"
```

---

## 3) Python Runtime Chuẩn (`.venv`)

> [!IMPORTANT]
> Script/test Python chạy từ host WSL bắt buộc dùng interpreter của repo `.venv`.

### 3.1 Chạy test từ repo root
```powershell
wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus && ./.venv/bin/python -m pytest <test_paths> -q"
```

### 3.2 Chạy test trong thư mục service
```powershell
wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus/services/aureus-nautilus-node && ../../.venv/bin/python -m pytest tests -q"
```

### 3.3 Ví dụ chạy script Python chuẩn
```powershell
wsl -d Aureus -u root bash -lc "cd /mnt/d/Aureus && ./.venv/bin/python services/aureus-signal/signal_computer.py --symbol XAUUSD --start 2026-02-24 --end 2026-03-04"
```

### 3.4 Khôi phục `.venv` khi lỗi thiếu package/pip
```powershell
wsl -d Aureus -u root -e bash -lc "python3 -m pip install virtualenv && cd /mnt/d/Aureus && python3 -m virtualenv .venv"
wsl -d Aureus -u root -e bash -lc "cd /mnt/d/Aureus && ./.venv/bin/python -m pip install redis==7.2.0 asyncpg==0.30.0"
```

---

## 4) Signal Maintenance

### 4.1 Hard reset signal snapshots/swing points + restart signal service
```powershell
wsl -d Aureus -u root bash -lc "cd /mnt/d/Aureus && ./.venv/bin/python scripts/hard_reset_signals.py && docker compose -f docker-compose.dev.yml up -d --build aureus-signal-dev"
```

### 4.2 Seed strategy đúng runtime (trong container)
```powershell
wsl -d Aureus -e bash -lc "docker exec aureus-signal-dev python -m engine.strategies.seed_strategies"
```

Verify nhanh:
```powershell
wsl -d Aureus -e bash -lc "docker exec -i aureus_timescaledb_dev psql -U aureus -d aureus -c \"SELECT COUNT(*) AS templates FROM aureus_strategy_templates; SELECT COUNT(*) AS symbol_links FROM aureus_symbol_strategies;\""
```

---

## 5) Verify Checklist Sau Mỗi Lần Sửa

1. Container cần thiết ở trạng thái `Up`:
```powershell
wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus && docker compose -f docker-compose.dev.yml ps"
```

2. Log không còn lỗi runtime lặp:
```powershell
wsl -d Aureus -e bash -lc "docker logs --since 5m aureus-signal-dev 2>&1 | tail -n 200"
```

3. Endpoint/cổng đúng theo `.env`:
- `DEV_API_PORT=8002`
- `DEV_WEB_PORT=17222`

4. Nếu có đổi code backend: bắt buộc `up -d --build` service tương ứng.

---

## 6) Lỗi Thường Gặp & Cách Xử Lý Nhanh

### 6.1 `ModuleNotFoundError` khi chạy script/test
- Nguyên nhân: chạy sai interpreter (host Python thay vì `.venv` hoặc container).
- Cách xử lý: chạy lại bằng `.venv/bin/python` hoặc `docker exec ... python ...` đúng service runtime.

### 6.2 `NOGROUP` sau khi clear Redis
- Kiểm tra log `aureus-signal-dev`.
- Nếu chưa tự recover, rebuild/restart signal service.

### 6.3 MT5 không gửi data sang Gateway (`5556`)
```powershell
wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus && docker compose -f docker-compose.dev.yml ps aureus-gateway-dev"
wsl -d Aureus -e bash -lc "ss -ltnp | grep 5556 || true"
```

### 6.4 `npm i` lỗi `ERESOLVE` (React 19)
- Gỡ `react-beautiful-dnd` và `@types/react-beautiful-dnd`.
- Dùng `@hello-pangea/dnd` thay thế.

### 6.5 Lỗi parser khi chạy command dài từ PowerShell
- Gói toàn bộ logic Linux trong **1 chuỗi** `bash -lc "..."`.
- Tránh command substitution `$(...)` phức tạp.
- Nếu command quá dài, tách thành nhiều lệnh độc lập.

---

## 7) Rules Bắt Buộc (Ngắn gọn)

- Chỉ chạy backend qua WSL.
- Không chạy Python inline `python -c "..."`.
- Không cài package tạm vào system Python để chạy project.
- Với test Python: ưu tiên `.venv/bin/python -m pytest`.
- Mỗi command chạy xong phải đọc log; có lỗi thì sửa và chạy lại.

---

## 8) Tham chiếu chi tiết

Nếu cần playbook đầy đủ cho từng lỗi chuyên sâu (Gateway, NOGROUP, cleanup DB, quote-safe command), xem lịch sử commit hoặc tách riêng vào `docs/runbooks/` để giữ file này gọn.
