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

> **Lưu ý**: Hãy chắc chắn terminal đang ở thư mục gốc project: `d:\AIFramework\aureus` (WSL path: `/mnt/d/AIFramework/aureus`).

Môi trường Development có thể khởi tạo nhanh bằng script có sẵn.
Mở PowerShell và chạy lệnh sau để bật các core services:

```powershell
wsl -d Ubuntu-24.04 -e bash -c "cd /mnt/d/AIFramework/aureus && ./scripts/dev-service.sh"
```

Lệnh này sẽ build và khởi động:
- `aureus_redis_dev` (port host mặc định: `6380`)
- `aureus_timescaledb_dev` (port host mặc định: `5433`)
- `aureus-gateway-dev`
- `aureus-db-writer-dev`
- `aureus-signal-dev`
- `aureus-dashboard-api-dev`

### 2.1 Build & chạy riêng Nautilus + Bridge (mới)
Sau khi đã thêm service vào `docker-compose.dev.yml`, dùng lệnh sau để build và chạy 2 service mới:

```powershell
wsl -d Ubuntu-24.04 -e bash -c "cd /mnt/d/AIFramework/aureus && docker compose -f docker-compose.dev.yml up --build -d nautilus_trader-dev aureus-nautilus-bridge-dev"
```

Service được khởi động:
- `nautilus-trader-dev` (image prebuilt `ghcr.io/nautechsystems/nautilus_trader:nightly`)
- `aureus-nautilus-bridge-dev` (build từ `services/aureus-nautilus-bridge/Dockerfile`)

*(WEB của Dashboard có thể chạy native như phần bên dưới.)*

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
wsl -d Ubuntu-24.04 -u root bash -c "cd /mnt/d/AIFramework/aureus && docker compose -f docker-compose.dev.yml up -d --build aureus-dashboard-api-dev"

# Ví dụ: Rebuild + restart Signal Engine (dev)
wsl -d Ubuntu-24.04 -u root bash -c "cd /mnt/d/AIFramework/aureus && docker compose -f docker-compose.dev.yml up -d --build aureus-signal-dev"

# Ví dụ: Rebuild + restart Nautilus Bridge (dev)
wsl -d Ubuntu-24.04 -u root bash -c "cd /mnt/d/AIFramework/aureus && docker compose -f docker-compose.dev.yml up -d --build aureus-nautilus-bridge-dev"
```

### Lệnh Rebuild/Restart riêng Nautilus + Bridge:
```powershell
wsl -d Ubuntu-24.04 -u root bash -c "cd /mnt/d/AIFramework/aureus && docker compose -f docker-compose.dev.yml up -d --build nautilus_trader-dev aureus-nautilus-bridge-dev"
```

### Lệnh Restart toàn bộ hệ thống dev:
```powershell
wsl -d Ubuntu-24.04 -u root bash -c "cd /mnt/d/AIFramework/aureus && docker compose -f docker-compose.dev.yml up -d --build"
```

### Lệnh kiểm tra sau khi chạy/build lại:
```powershell
# Xem trạng thái 2 service mới
wsl -d Ubuntu-24.04 -u root bash -c "cd /mnt/d/AIFramework/aureus && docker compose -f docker-compose.dev.yml ps nautilus_trader-dev aureus-nautilus-bridge-dev"

# Kiểm tra health cơ bản bằng restart count = 0
wsl -d Ubuntu-24.04 -u root bash -c "cd /mnt/d/AIFramework/aureus && docker inspect -f '{{.Name}}|{{.State.Status}}|restarts={{.RestartCount}}' nautilus-trader-dev aureus-nautilus-bridge-dev"

# Xem log bridge để xác nhận có publish execution event
wsl -d Ubuntu-24.04 -u root bash -c "cd /mnt/d/AIFramework/aureus && docker logs --tail 100 aureus-nautilus-bridge-dev"
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