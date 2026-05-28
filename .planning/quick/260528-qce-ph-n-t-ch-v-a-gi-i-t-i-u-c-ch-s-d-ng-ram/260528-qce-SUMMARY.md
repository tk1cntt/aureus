# Quick 260528-qce Summary

## Evidence

- `aureus_redis_dev` đang Up 19 hours, image `redis:alpine`.
- Docker RAM: `5.677GiB / 15.52GiB`.
- Redis memory: `used_memory_human:5.92G`, `used_memory_rss_human:5.66G`.
- Dataset gần như toàn bộ RAM: `used_memory_dataset:6357678371`, `dataset.percentage:99.99595642089844`.
- Fragmentation không phải nguyên nhân: `mem_fragmentation_ratio:0.96`, `allocator_frag_ratio:1.00`.
- Config không có guard: `maxmemory 0`, `maxmemory-policy noeviction`, compose chưa đặt memory limit/maxmemory.

## Nguyên nhân

RAM Redis tăng chủ yếu do stream dataset không TTL:

1. `aureus:stream:*:signals`: 7 stream chính khoảng 590-657 MB/key, `XLEN=1000`, `TTL=-1`, tổng khoảng 4.27 GB.
2. `aureus:stream:*:orders`: 7 stream khoảng 164-287 MB/key, `XLEN` khoảng 28k-30k, `TTL=-1`, tổng khoảng 1.50 GB.
3. `aureus:profiling:*`, `aureus:state:*`, TPO daily, reasoning queue nhỏ hơn nhiều.

## Khuyến nghị

1. Ưu tiên thêm producer-side retention cho `aureus:stream:*:signals` trong dev, ví dụ maxlen 100-300 sau khi xác nhận consumer needs.
2. Thêm retention riêng cho `aureus:stream:*:orders`, ví dụ maxlen 1000-5000 hoặc theo operational window.
3. Audit payload `aureus:stream:*:signals` vì `XLEN=1000` nhưng mỗi symbol đang chiếm khoảng 600 MB.
4. Sau khi có retention, thêm dev guard `redis-server --maxmemory 3gb --maxmemory-policy noeviction`; tránh `allkeys-lru` vì có thể mất stream/state.

## Artifacts

- Report chi tiết: `D:/Aureus/.planning/quick/260528-qce-ph-n-t-ch-v-a-gi-i-t-i-u-c-ch-s-d-ng-ram/260528-qce-REDIS-RAM-REPORT.md`
- Summary này: `D:/Aureus/.planning/quick/260528-qce-ph-n-t-ch-v-a-gi-i-t-i-u-c-ch-s-d-ng-ram/260528-qce-SUMMARY.md`

## Safety

Chỉ chạy lệnh read-only: `docker ps`, `docker stats`, `docker inspect`, `redis-cli INFO`, `MEMORY STATS`, `CONFIG GET`, `--bigkeys`, `--memkeys`, `SCAN` sample, `TYPE`, `MEMORY USAGE`, `TTL`, `XLEN`, `STRLEN`, `SCARD`.

Không chạy `FLUSH*`, `DEL`, `XTRIM`, `CONFIG SET`, restart container, hoặc sửa runtime Redis state.
