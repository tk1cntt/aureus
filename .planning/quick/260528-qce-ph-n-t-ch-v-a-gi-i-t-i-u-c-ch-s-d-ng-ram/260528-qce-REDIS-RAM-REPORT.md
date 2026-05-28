# Redis RAM Report - quick 260528-qce

Generated: 2026-05-28T00:00:00Z
Scope: read-only operational analysis for `aureus_redis_dev`.

## Runtime Evidence

Commands ran through WSL from `/mnt/d/Aureus`. No `FLUSH*`, `DEL`, `XTRIM`, `CONFIG SET`, restart, or data mutation command ran.

### docker ps

Command: `docker ps --filter name=aureus_redis_dev --format '{{.Names}} {{.Status}} {{.Image}}'`

```text
aureus_redis_dev Up 19 hours redis:alpine
```

### docker stats

Command: `docker stats --no-stream --format 'table {{.Name}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.CPUPerc}}\t{{.NetIO}}\t{{.BlockIO}}' aureus_redis_dev`

```text
NAME               MEM USAGE / LIMIT     MEM %     CPU %     NET I/O           BLOCK I/O
aureus_redis_dev   5.677GiB / 15.52GiB   36.59%    1.05%     12.2GB / 11.2GB   1.49GB / 132GB
```

### docker inspect

Command: `docker inspect aureus_redis_dev --format '{{json .HostConfig.Memory}} {{json .HostConfig.MemorySwap}} {{json .HostConfig.RestartPolicy}} {{json .Config.Image}}'`

```text
0 0 {"Name":"unless-stopped","MaximumRetryCount":0} "redis:alpine"
```

Meaning: no Docker memory limit and no swap limit configured for Redis container.

### INFO memory

Command: `docker exec aureus_redis_dev redis-cli INFO memory`

```text
used_memory:6359261104
used_memory_human:5.92G
used_memory_rss:6076137472
used_memory_rss_human:5.66G
used_memory_peak:7514259248
used_memory_peak_human:7.00G
used_memory_overhead:1582733
used_memory_dataset:6357678371
used_memory_dataset_perc:100.00%
allocator_allocated:6359999528
allocator_active:6360498176
allocator_resident:6409265152
maxmemory:0
maxmemory_human:0B
maxmemory_policy:noeviction
allocator_frag_ratio:1.00
allocator_frag_bytes:411320
allocator_rss_ratio:1.01
allocator_rss_bytes:48766976
rss_overhead_ratio:0.95
rss_overhead_bytes:-333127680
mem_fragmentation_ratio:0.96
mem_fragmentation_bytes:-283105320
mem_clients_normal:82165
mem_aof_buffer:0
mem_allocator:jemalloc-5.3.0
```

### INFO keyspace

Command: `docker exec aureus_redis_dev redis-cli INFO keyspace`

```text
db0:keys=957,expires=840,avg_ttl=35852948,subexpiry=0
```

### INFO stats

Command: `docker exec aureus_redis_dev redis-cli INFO stats`

```text
total_connections_received:8141
total_commands_processed:9473385
instantaneous_ops_per_sec:82
total_net_input_bytes:11532714399
total_net_output_bytes:10478250902
expired_keys:491
evicted_keys:0
total_error_replies:70456
pubsub_channels:12
latest_fork_usec:75696
total_forks:223
client_output_buffer_limit_disconnections:0
```

### MEMORY STATS

Command: `docker exec aureus_redis_dev redis-cli MEMORY STATS`

```text
peak.allocated 7514259248
total.allocated 6359260824
startup.allocated 1325744
clients.normal 82165
db.0 overhead.hashtable.main 49720
db.0 overhead.hashtable.expires 21912
keys.count 957
keys.bytes-per-key 6643341
dataset.bytes 6357678091
dataset.percentage 99.99595642089844
allocator-fragmentation.ratio 1.0000635385513306
allocator-fragmentation.bytes 404280
allocator-rss.ratio 1.0076671838760376
allocator-rss.bytes 48766976
fragmentation 0.9554812908172607
fragmentation.bytes -283105320
```

### CONFIG GET

Command: `docker exec aureus_redis_dev redis-cli CONFIG GET maxmemory maxmemory-policy save appendonly client-output-buffer-limit`

```text
appendonly no
save 3600 1 300 100 60 10000
maxmemory 0
maxmemory-policy noeviction
client-output-buffer-limit normal 0 0 0 slave 268435456 67108864 60 pubsub 33554432 8388608 60
```

## Keyspace Sampling

Commands used:

- `docker exec aureus_redis_dev redis-cli --bigkeys`
- `docker exec aureus_redis_dev redis-cli --memkeys --memkeys-samples 1000`
- `SCAN` sample capped to 1000 keys with `TYPE`, `MEMORY USAGE`, `TTL`, and per-type size commands: `XLEN`, `LLEN`, `HLEN`, `ZCARD`, `SCARD`, `STRLEN`.

No `KEYS *` command used.

### --bigkeys summary

```text
Sampled 957 keys in the keyspace.
Biggest hash: aureus:latest:AUDUSD:candle has 8 fields
Biggest stream: aureus:stream:EURUSD:orders has 29768 entries
Biggest string: aureus:state:BTCUSD has 684549 bytes
Biggest set: aureus:orders:history:XAUUSD has 33 members
51 streams with 459508 entries
889 strings with 4643926 bytes
7 sets with 115 members
10 hashes with 74 fields
```

### --memkeys summary

```text
Sampled 957 keys in the keyspace.
51 streams with 5787501226 bytes, avg 113480416 bytes/key
889 strings with 5190776 bytes, avg 5838 bytes/key
7 sets with 3117 bytes
10 hashes with 1435 bytes
Biggest stream: aureus:stream:BTCUSD:signals has 657205630 bytes
Biggest string: aureus:state:USTEC has 786472 bytes
```

### Top MEMORY USAGE sample

```text
657205630 stream aureus:stream:BTCUSD:signals TTL=-1 XLEN=1000
628936620 stream aureus:stream:XAUUSD:signals TTL=-1 XLEN=1000
616313083 stream aureus:stream:USTEC:signals TTL=-1 XLEN=1000
592399331 stream aureus:stream:AUDUSD:signals TTL=-1 XLEN=1000
591178702 stream aureus:stream:GBPUSD:signals TTL=-1 XLEN=1000
590530466 stream aureus:stream:EURUSD:signals TTL=-1 XLEN=1000
589857262 stream aureus:stream:USDJPY:signals TTL=-1 XLEN=1000
286757346 stream aureus:stream:BTCUSD:orders TTL=-1 XLEN=29758
281028101 stream aureus:stream:XAUUSD:orders TTL=-1 XLEN=28200
251352439 stream aureus:stream:USTEC:orders TTL=-1 XLEN=28227
174949590 stream aureus:stream:AUDUSD:orders TTL=-1 XLEN=29744
172113113 stream aureus:stream:GBPUSD:orders TTL=-1 XLEN=29740
166666108 stream aureus:stream:EURUSD:orders TTL=-1 XLEN=29768
164062640 stream aureus:stream:USDJPY:orders TTL=-1 XLEN=29768
4671572 stream aureus:reasoning:embedding_jobs TTL=-1 XLEN=2922
1226249 stream aureus:profiling:BTCUSD TTL=-1 XLEN=10028
1225742 stream aureus:profiling:ETHUSD TTL=-1 XLEN=10008
1222623 stream aureus:profiling:XAUUSD TTL=-1 XLEN=10027
1222216 stream aureus:profiling:USDJPY TTL=-1 XLEN=10022
1220448 stream aureus:profiling:EURUSD TTL=-1 XLEN=10026
1220390 stream aureus:profiling:USTEC TTL=-1 XLEN=10022
1219715 stream aureus:profiling:GBPUSD TTL=-1 XLEN=10016
1217001 stream aureus:profiling:AUDUSD TTL=-1 XLEN=10003
853212 stream aureus:stream:BTCUSD:swing_point TTL=-1 XLEN=22322
786472 string aureus:state:XAUUSD TTL=-1 STRLEN=672164
786472 string aureus:state:USTEC TTL=-1 STRLEN=669681
786472 string aureus:state:BTCUSD TTL=-1 STRLEN=684549
698264 stream aureus:stream:XAUUSD:swing_point TTL=-1 XLEN=18798
666033 stream aureus:stream:USTEC:swing_point TTL=-1 XLEN=17866
655400 string aureus:state:USDJPY TTL=-1 STRLEN=617790
655400 string aureus:state:GBPUSD TTL=-1 STRLEN=623740
655400 string aureus:state:EURUSD TTL=-1 STRLEN=621043
655400 string aureus:state:AUDUSD TTL=-1 STRLEN=621566
```

### Prefix groups

| Prefix/group | Evidence | Estimated RAM driver |
|---|---:|---|
| `aureus:stream:*:signals` | 7 active symbol streams near 590-657 MB each, XLEN=1000, TTL=-1 | primary driver, about 4.27 GB total in sample |
| `aureus:stream:*:orders` | 7 streams near 164-287 MB each, XLEN about 28k-30k, TTL=-1 | secondary driver, about 1.50 GB total in sample |
| `aureus:profiling:*` | 8 streams near 1.2 MB each, XLEN about 10k, TTL=-1 | small but unbounded trend risk |
| `aureus:state:*` | strings near 0.65-0.79 MB each, TTL=-1 | small compared to streams |
| `aureus:reasoning:embedding_jobs` | 4.7 MB, XLEN=2922, TTL=-1 | small now, backlog risk |
| TPO daily strings | about 504 bytes each, TTL=-1 | negligible RAM |

### Sampling limits

`--bigkeys` and `--memkeys` scan runtime keyspace while services may write concurrently. `SCAN` is incremental and not a strict snapshot. Results are enough to identify memory drivers because top stream keys dominate Redis dataset.

## Diagnosis

Main cause: Redis RAM is dataset-heavy stream retention, not allocator fragmentation or client buffers.

Evidence:

- Container RSS: `docker stats` shows `5.677GiB / 15.52GiB`.
- Redis process: `used_memory_human:5.92G`, `used_memory_rss_human:5.66G`.
- Dataset: `used_memory_dataset:6357678371`, `dataset.percentage:99.99595642089844`.
- Overhead: `used_memory_overhead:1582733`, tiny relative to dataset.
- Fragmentation: `mem_fragmentation_ratio:0.96`, `allocator_frag_ratio:1.00`; fragmentation is not problem.
- Clients: `mem_clients_normal:82165`; client buffers not problem.
- Keyspace: 957 keys, 840 with expiry; large RAM concentrated in no-TTL streams.
- Biggest memory group: `aureus:stream:*:signals`, 7 keys near 590-657 MB each despite XLEN only 1000. Payload per stream entry is huge.
- Second group: `aureus:stream:*:orders`, XLEN near 30k, 164-287 MB each, no TTL.

`docker-compose.dev.yml` comparison:

- Redis uses `redis:alpine` with container name `aureus_redis_dev`.
- Host port is `${DEV_REDIS_PORT:-6380}:6379`.
- No Docker memory limit is configured.
- No Redis `maxmemory` or `maxmemory-policy` is configured in compose.
- Runtime confirms `maxmemory 0` and `maxmemory-policy noeviction`.

## Optimization Options

### Option 1: Trim stream backlog by producer retention policy

Best first target: `aureus:stream:*:signals` and `aureus:stream:*:orders`.

Tradeoff: safest if implemented in producers with bounded `XADD MAXLEN`/retention. Do not manually trim blindly because consumers may need history. Need map consumers first, then retention by stream role.

Suggested policy candidates for dev:

- `aureus:stream:*:signals`: keep last 100-300 entries if each entry contains large full snapshots.
- `aureus:stream:*:orders`: keep last 1000-5000 entries or keep by operational window.
- `aureus:profiling:*`: keep last 1000 entries.
- `aureus:reasoning:embedding_jobs`: monitor backlog, retain enough for pending worker recovery.

Verify before any future trim:

```bash
wsl -d Aureus -e bash -lc "docker exec aureus_redis_dev redis-cli XLEN aureus:stream:BTCUSD:signals && docker exec aureus_redis_dev redis-cli MEMORY USAGE aureus:stream:BTCUSD:signals"
```

### Option 2: Reduce signal stream payload size

Evidence shows `aureus:stream:*:signals` uses about 600 MB per 1000 entries, meaning entry payload is too large for dev stream retention. Prefer publishing compact signal event and storing heavy snapshot elsewhere or only latest-state key.

Tradeoff: requires code change and compatibility review with consumers. Highest long-term payoff.

Verify candidate payload size without mutating data:

```bash
wsl -d Aureus -e bash -lc "docker exec aureus_redis_dev redis-cli XRANGE aureus:stream:BTCUSD:signals - + COUNT 1"
```

### Option 3: Add dev maxmemory guard after retention is in place

Do this only after stream retention/payload cleanup. Redis stream/trading systems should avoid silent loss unless producer/consumer semantics are understood.

Suggested compose diff for dev guard only:

```diff
 redis-dev:
   image: redis:alpine
   container_name: aureus_redis_dev
+  command: ["redis-server", "--maxmemory", "3gb", "--maxmemory-policy", "noeviction"]
   ports:
     - "${DEV_REDIS_PORT:-6380}:6379"
```

Tradeoff:

- `noeviction`: safest for correctness; writers fail loudly when RAM cap hit.
- `allkeys-lru`: can evict streams/state unexpectedly; dangerous for trading/event flow.
- `volatile-lru`: only helps keys with TTL; current major streams have TTL=-1.

### Option 4: Docker/WSL memory limit guard

Set Docker Desktop/WSL memory cap only as outer guard. It will not fix Redis dataset growth. Use after Redis retention policy so cap does not cause dev instability.

Verify after future config changes:

```bash
wsl -d Aureus -e bash -lc "docker stats --no-stream aureus_redis_dev && docker exec aureus_redis_dev redis-cli INFO memory | grep -E 'used_memory_human|used_memory_dataset|mem_fragmentation_ratio|maxmemory|maxmemory_policy'"
```

## Recommended Plan

1. Add producer-side bounded retention for `aureus:stream:*:signals`, starting with dev maxlen target 100-300. Reason: saves about 4 GB and targets primary driver.
2. Add retention for `aureus:stream:*:orders` with a higher maxlen or time-window policy. Reason: saves about 1.5 GB while preserving operational trail.
3. Audit signal stream payload and remove duplicated heavy snapshot fields from stream event if consumers do not require all fields. Reason: XLEN=1000 still costs about 600 MB per symbol.
4. Add dev-only `maxmemory 3gb` with `noeviction` after retention exists. Reason: fail loud instead of silent evict in trading flow.

Do not restart Redis, do not `XTRIM`, do not delete keys during this analysis task.

## Verification Commands

Read-only current-state checks:

```bash
wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus && docker stats --no-stream --format 'table {{.Name}}\t{{.MemUsage}}\t{{.MemPerc}}' aureus_redis_dev"
wsl -d Aureus -e bash -lc "docker exec aureus_redis_dev redis-cli INFO memory | grep -E 'used_memory_human|used_memory_dataset|used_memory_overhead|mem_fragmentation_ratio|maxmemory|maxmemory_policy'"
wsl -d Aureus -e bash -lc "docker exec aureus_redis_dev redis-cli --memkeys --memkeys-samples 1000"
wsl -d Aureus -e bash -lc "docker exec aureus_redis_dev redis-cli XLEN aureus:stream:BTCUSD:signals && docker exec aureus_redis_dev redis-cli MEMORY USAGE aureus:stream:BTCUSD:signals && docker exec aureus_redis_dev redis-cli TTL aureus:stream:BTCUSD:signals"
```

Post-optimization checks, after future separate implementation:

```bash
wsl -d Aureus -e bash -lc "docker exec aureus_redis_dev redis-cli XLEN aureus:stream:BTCUSD:signals && docker exec aureus_redis_dev redis-cli MEMORY USAGE aureus:stream:BTCUSD:signals"
wsl -d Aureus -e bash -lc "docker exec aureus_redis_dev redis-cli INFO stats | grep -E 'evicted_keys|rejected_connections|total_error_replies'"
wsl -d Aureus -e bash -lc "docker stats --no-stream aureus_redis_dev"
```
