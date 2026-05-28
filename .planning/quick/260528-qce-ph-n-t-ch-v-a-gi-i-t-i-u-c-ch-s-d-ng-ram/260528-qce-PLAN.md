---
phase: quick-260528-qce-redis-ram-optimization
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - .planning/quick/260528-qce-ph-n-t-ch-v-a-gi-i-t-i-u-c-ch-s-d-ng-ram/260528-qce-REDIS-RAM-REPORT.md
  - .planning/quick/260528-qce-ph-n-t-ch-v-a-gi-i-t-i-u-c-ch-s-d-ng-ram/260528-qce-SUMMARY.md
autonomous: true
requirements:
  - QCE-REDIS-RAM-01
must_haves:
  truths:
    - "Người dùng thấy mức RAM thật của container aureus_redis_dev, Redis process, dataset, overhead, fragmentation, và keyspace."
    - "Người dùng biết nhóm key/stream/list/hash nào đang chiếm RAM nhiều nhất dựa trên bằng chứng runtime an toàn."
    - "Người dùng nhận được phương án tối ưu Redis RAM có thứ tự ưu tiên, tradeoff rõ, và command áp dụng/verify nếu cần."
  artifacts:
    - path: ".planning/quick/260528-qce-ph-n-t-ch-v-a-gi-i-t-i-u-c-ch-s-d-ng-ram/260528-qce-REDIS-RAM-REPORT.md"
      provides: "Báo cáo phân tích Redis RAM và đề xuất tối ưu vận hành"
      contains: "docker stats"
    - path: "docker-compose.dev.yml"
      provides: "Nguồn cấu hình Redis dev hiện tại để đối chiếu memory policy/limit"
      contains: "aureus_redis_dev"
    - path: "RUN_SERVICES.md"
      provides: "Quy tắc chạy command backend qua WSL"
      contains: "wsl -d Aureus"
  key_links:
    - from: "aureus_redis_dev runtime"
      to: ".planning/quick/260528-qce-ph-n-t-ch-v-a-gi-i-t-i-u-c-ch-s-d-ng-ram/260528-qce-REDIS-RAM-REPORT.md"
      via: "docker stats/inspect + redis-cli INFO/MEMORY evidence copied into report"
      pattern: "docker stats.*aureus_redis_dev"
    - from: "Redis keyspace samples"
      to: "Optimization recommendations"
      via: "bigkeys/memory samples drive retention, trimming, maxmemory, persistence, or producer-specific proposal"
      pattern: "redis-cli.*(--bigkeys|MEMORY USAGE|SCAN)"
---

# Quick Plan: Phân tích và tối ưu RAM Redis dev

## Objective

Phân tích RAM Redis trong môi trường Docker/WSL dev hiện tại của Aureus, xác định nguồn dùng RAM bằng bằng chứng runtime, rồi tạo đề xuất tối ưu an toàn.

Purpose: tránh đoán mò Redis RAM; ưu tiên tối ưu dựa trên container metrics, Redis memory internals, keyspace, và key samples.

Output: `.planning/quick/260528-qce-ph-n-t-ch-v-a-gi-i-t-i-u-c-ch-s-d-ng-ram/260528-qce-REDIS-RAM-REPORT.md`

## Execution Context

- Làm việc từ repo `D:/Aureus`.
- Theo `RUN_SERVICES.md`, mọi command backend/Docker/redis-cli phải chạy qua WSL: `wsl -d Aureus -e bash -lc "..."`.
- Không sửa code. Chỉ đề xuất thay đổi. Nếu thấy `docker-compose.dev.yml` có config Redis an toàn nên đổi, báo trong report kèm diff đề xuất, không tự sửa trong plan này.
- Không dùng command destructive: không `FLUSH*`, không `DEL`, không `XTRIM`, không đổi `CONFIG SET`, không restart container trong bước phân tích.

## Context

- `@D:/Aureus/CLAUDE.md`
- `@D:/Aureus/RUN_SERVICES.md`
- `@D:/Aureus/docker-compose.dev.yml`
- `@D:/Aureus/.planning/STATE.md`

## Tasks

### Task 1: Thu thập runtime evidence Redis/container an toàn

files: `.planning/quick/260528-qce-ph-n-t-ch-v-a-gi-i-t-i-u-c-ch-s-d-ng-ram/260528-qce-REDIS-RAM-REPORT.md`

Action:
1. Tạo report với section `Runtime Evidence` và ghi timestamp.
2. Chạy các command read-only qua WSL, từ `/mnt/d/Aureus`, lưu output quan trọng vào report:
   - `docker ps --filter name=aureus_redis_dev --format '{{.Names}} {{.Status}} {{.Image}}'`
   - `docker stats --no-stream --format 'table {{.Name}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.CPUPerc}}\t{{.NetIO}}\t{{.BlockIO}}' aureus_redis_dev`
   - `docker inspect aureus_redis_dev --format '{{json .HostConfig.Memory}} {{json .HostConfig.MemorySwap}} {{json .HostConfig.RestartPolicy}} {{json .Config.Image}}'`
   - `docker exec aureus_redis_dev redis-cli INFO memory`
   - `docker exec aureus_redis_dev redis-cli INFO keyspace`
   - `docker exec aureus_redis_dev redis-cli INFO stats`
   - `docker exec aureus_redis_dev redis-cli MEMORY STATS`
   - `docker exec aureus_redis_dev redis-cli CONFIG GET maxmemory maxmemory-policy save appendonly client-output-buffer-limit`
3. Nếu container chưa chạy, report rõ `aureus_redis_dev not running`, dẫn lại command start từ `RUN_SERVICES.md`, và dừng sau khi tạo report skeleton. Không tự start container.

verify:
`wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus && test -s .planning/quick/260528-qce-ph-n-t-ch-v-a-gi-i-t-i-u-c-ch-s-d-ng-ram/260528-qce-REDIS-RAM-REPORT.md && grep -E 'Runtime Evidence|docker stats|INFO memory|MEMORY STATS|INFO keyspace|CONFIG GET' .planning/quick/260528-qce-ph-n-t-ch-v-a-gi-i-t-i-u-c-ch-s-d-ng-ram/260528-qce-REDIS-RAM-REPORT.md"`

Done:
Report có bằng chứng container RAM, Redis memory breakdown, keyspace, stats, memory config. Không có command destructive được chạy.

### Task 2: Lấy mẫu key lớn và phân loại nguồn RAM

files: `.planning/quick/260528-qce-ph-n-t-ch-v-a-gi-i-t-i-u-c-ch-s-d-ng-ram/260528-qce-REDIS-RAM-REPORT.md`

Action:
1. Thêm section `Keyspace Sampling` vào report.
2. Chạy command read-only an toàn qua WSL:
   - `docker exec aureus_redis_dev redis-cli --bigkeys`
   - `docker exec aureus_redis_dev redis-cli --memkeys --memkeys-samples 1000` nếu Redis image hỗ trợ; nếu không hỗ trợ, ghi lỗi ngắn và dùng fallback bên dưới.
   - Fallback safe sample: dùng `SCAN` với count giới hạn, lấy tối đa 1000 key, chạy `TYPE`, `MEMORY USAGE`, `XLEN` cho stream, `LLEN` cho list, `HLEN` cho hash, `ZCARD` cho zset, `SCARD` cho set, `STRLEN` cho string. Không dùng `KEYS *`.
3. Tổng hợp top nhóm theo prefix/key pattern nếu đủ dữ liệu: stream `aureus:stream:*`, cache/snapshot/TPO/reasoning, consumer group metadata, các key không có TTL.
4. Ghi rõ giới hạn phương pháp: `--bigkeys` sampling, `SCAN` không snapshot tuyệt đối, runtime biến động khi services đang chạy.

verify:
`wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus && grep -E 'Keyspace Sampling|--bigkeys|MEMORY USAGE|TTL|stream|hash|list|string' .planning/quick/260528-qce-ph-n-t-ch-v-a-gi-i-t-i-u-c-ch-s-d-ng-ram/260528-qce-REDIS-RAM-REPORT.md"`

Done:
Report chỉ ra top key/type/prefix nghi ngờ chiếm RAM, có số đo hoặc sample cụ thể, có TTL/retention nhận xét, không scan kiểu blocking toàn bộ bằng `KEYS *`.

### Task 3: Đề xuất tối ưu RAM Redis theo bằng chứng

files: `.planning/quick/260528-qce-ph-n-t-ch-v-a-gi-i-t-i-u-c-ch-s-d-ng-ram/260528-qce-REDIS-RAM-REPORT.md`, `.planning/quick/260528-qce-ph-n-t-ch-v-a-gi-i-t-i-u-c-ch-s-d-ng-ram/260528-qce-SUMMARY.md`

Action:
1. Thêm section `Diagnosis`, `Optimization Options`, `Recommended Plan`, `Verification Commands` vào report.
2. Chẩn đoán dựa trên Task 1-2:
   - Tách container RSS vs Redis `used_memory`, `used_memory_dataset`, `used_memory_overhead`, `mem_fragmentation_ratio`, `allocator_frag_ratio`.
   - Xác định RAM do dataset/key, stream backlog, hash/list lớn, no-TTL cache, fragmentation, client buffers, hoặc Docker/WSL overhead.
   - Đối chiếu `docker-compose.dev.yml`: Redis hiện dùng `redis:alpine`, container `aureus_redis_dev`, host port `${DEV_REDIS_PORT:-6380}`, chưa thấy memory limit/maxmemory trong compose hiện tại.
3. Đề xuất thứ tự ưu tiên, chỉ gồm phương án an toàn cho dev:
   - Nếu stream backlog lớn: đề xuất retention/trim theo producer/consumer cụ thể sau khi xác định key, kèm command verify `XLEN` trước/sau; không tự trim.
   - Nếu cache/snapshot không TTL: đề xuất TTL tại producer hoặc namespace-specific retention; không dùng global delete.
   - Nếu cần guard dev RAM: đề xuất `maxmemory` + policy phù hợp, nêu tradeoff `noeviction` vs `allkeys-lru`/`volatile-lru` cho hệ thống stream/trading.
   - Nếu fragmentation cao nhưng dataset nhỏ: đề xuất restart Redis dev theo maintenance window, hoặc image/config allocator nếu có bằng chứng; không restart tự động.
   - Nếu Docker/WSL memory cao: đề xuất WSL/Docker Desktop limit và verify bằng `docker stats` sau chỉnh.
4. Nếu khuyến nghị sửa `docker-compose.dev.yml`, đưa diff đề xuất trong report, không sửa file. Vì đây là operational proposal.
5. Tạo `.planning/quick/260528-qce-ph-n-t-ch-v-a-gi-i-t-i-u-c-ch-s-d-ng-ram/260528-qce-SUMMARY.md` tóm tắt evidence chính, nguyên nhân RAM, khuyến nghị ưu tiên, và file report chi tiết.

verify:
`wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus && grep -E 'Diagnosis|Optimization Options|Recommended Plan|Verification Commands|maxmemory|mem_fragmentation|XLEN|TTL' .planning/quick/260528-qce-ph-n-t-ch-v-a-gi-i-t-i-u-c-ch-s-d-ng-ram/260528-qce-REDIS-RAM-REPORT.md && test -s .planning/quick/260528-qce-ph-n-t-ch-v-a-gi-i-t-i-u-c-ch-s-d-ng-ram/260528-qce-SUMMARY.md && grep -E 'Evidence|Nguyên nhân|Khuyến nghị|report' .planning/quick/260528-qce-ph-n-t-ch-v-a-gi-i-t-i-u-c-ch-s-d-ng-ram/260528-qce-SUMMARY.md"`

Done:
Report có kết luận nguyên nhân chính, 2-4 phương án tối ưu theo thứ tự ưu tiên, tradeoff rõ, command verify sau tối ưu; summary tồn tại và trỏ tới report chi tiết; không thay đổi runtime/config ngoài việc ghi report.

## Threat Model

Trust Boundaries:

| Boundary | Description |
|---|---|
| WSL shell -> Docker daemon | Command phân tích có quyền xem container runtime; phải giữ read-only. |
| Docker exec -> Redis | redis-cli có thể thao tác dữ liệu production-like dev; chỉ dùng lệnh quan sát. |
| Report -> vận hành sau này | Đề xuất sai có thể làm mất stream/cache nếu người dùng copy command destructive. |

STRIDE Threat Register:

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|---|---|---|---|---|
| T-QCE-01 | Tampering | Redis keyspace | mitigate | Plan cấm `FLUSH*`, `DEL`, `XTRIM`, `CONFIG SET`, restart; chỉ read-only evidence. |
| T-QCE-02 | Denial of Service | Redis runtime | mitigate | Dùng `--bigkeys`, `--memkeys`, `SCAN` count giới hạn; không dùng `KEYS *`. |
| T-QCE-03 | Information Disclosure | Report artifact | accept | Report nằm trong repo local; không ghi secret/env password; chỉ ghi metrics/key names cần thiết. |
| T-QCE-04 | Repudiation | Runtime evidence | mitigate | Report phải có timestamp và command đã chạy để audit lại. |

## Verification

Chạy verify từng task. Cuối cùng kiểm tra report đầy đủ:

`wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus && test -s .planning/quick/260528-qce-ph-n-t-ch-v-a-gi-i-t-i-u-c-ch-s-d-ng-ram/260528-qce-REDIS-RAM-REPORT.md && grep -E 'Runtime Evidence|Keyspace Sampling|Diagnosis|Recommended Plan|Verification Commands' .planning/quick/260528-qce-ph-n-t-ch-v-a-gi-i-t-i-u-c-ch-s-d-ng-ram/260528-qce-REDIS-RAM-REPORT.md"`

## Success Criteria

- Report dùng bằng chứng runtime bắt buộc: docker stats/inspect, Redis INFO memory, INFO keyspace, MEMORY STATS, big key samples.
- Report phân biệt container RAM, Redis dataset, overhead, fragmentation, keyspace/prefix drivers.
- Đề xuất tối ưu có thứ tự ưu tiên, an toàn cho dev, không xóa dữ liệu, không restart tự động.
- Nếu có config change đề xuất, report có diff và verify command, chưa sửa file.

## Output

Sau completion, tạo `.planning/quick/260528-qce-ph-n-t-ch-v-a-gi-i-t-i-u-c-ch-s-d-ng-ram/260528-qce-SUMMARY.md`.
