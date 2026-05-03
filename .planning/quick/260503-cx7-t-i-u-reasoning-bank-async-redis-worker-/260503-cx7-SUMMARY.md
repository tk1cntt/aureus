---
phase: 260503-cx7-reasoning-bank-async-redis-worker
plan: 01
subsystem: aureus-trader
tags: [reasoning-bank, redis, worker, embeddings]
completed: 2026-05-03
key-files:
  created:
    - services/aureus-trader/reasoning_embedding_worker.py
    - services/aureus-trader/scripts/verify_reasoning_embedding_worker_e2e.py
    - services/aureus-trader/tests/test_reasoning_embedding_queue.py
  modified:
    - services/aureus-trader/reasoning_embeddings.py
    - services/aureus-trader/journal.py
    - services/aureus-trader/main.py
    - services/aureus-trader/tests/test_journal.py
decisions:
  - Use Redis Stream key aureus:reasoning:embedding_jobs for async Reasoning Bank embedding jobs.
  - Keep embed_reasoning_entry as worker/backfill function; remove inline journal embedding call.
---

# Phase 260503-cx7 Plan 01: Reasoning Bank async Redis worker Summary

STRATEGY_MATCH journal now writes DB rows and enqueues Redis embedding jobs; separate worker processes embeddings so MT5 lifecycle is not blocked by embedding HTTP service.

## Completed Tasks

| Task | Name | Commit | Evidence |
| --- | --- | --- | --- |
| 1 | Add Redis queue contract and non-blocking enqueue tests | 42e0346 | `python -m pytest services/aureus-trader/tests/test_reasoning_embedding_queue.py -v` passed |
| 2 | Replace journal inline embedding and wire Redis into runtime manager | efcaf81 | `python -m pytest services/aureus-trader/tests/test_journal.py services/aureus-trader/tests/test_reasoning_embedding_queue.py -v` passed |
| 3 | Add worker entrypoint and strict DB/Redis runtime verification | 133ab74 | `python -m pytest services/aureus-trader/tests/test_journal.py services/aureus-trader/tests/test_reasoning_embedding_queue.py -v` passed |

## What Changed

- Added `enqueue_reasoning_embedding_job()` and `REASONING_EMBEDDING_QUEUE_KEY` in `services/aureus-trader/reasoning_embeddings.py`.
- Added `ReasoningEmbeddingWorker` consuming Redis Stream jobs and acknowledging with `XDEL` only after `embed_reasoning_entry()` succeeds.
- Updated `TradeJournalManager(db_pool, redis_client=None)` to store Redis client.
- Replaced STRATEGY_MATCH inline `ReasoningEmbeddingClient()` / `await embed_reasoning_entry(...)` with async Redis enqueue after `aureus_reasoning_entries` insert.
- Updated `services/aureus-trader/main.py` runtime wiring to `TradeJournalManager(db_pool, redis_client=r)`.
- Added standalone worker entrypoint: `services/aureus-trader/reasoning_embedding_worker.py`.
- Added runtime E2E script: `services/aureus-trader/scripts/verify_reasoning_embedding_worker_e2e.py`.

## Verification

Passed:

```bash
wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus && ./.venv/bin/python -m pytest services/aureus-trader/tests/test_journal.py services/aureus-trader/tests/test_reasoning_embedding_queue.py -v"
```

Result: `77 passed in 0.69s`.

```bash
wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus && AUREUS_DB_DSN=postgresql://aureus:aureus_password@localhost:5433/aureus REDIS_URL=redis://127.0.0.1:6380 ./.venv/bin/python services/aureus-trader/scripts/verify_reasoning_embedding_worker_e2e.py --redis-url redis://127.0.0.1:6380 --timeout 20 --static-embedding"
```

Result: exit code `0`; runtime DB/Redis E2E passed. Command output only included redis close deprecation warning from `verify_reasoning_embedding_worker_e2e.py:62`; no assertion failures.

## GitNexus Impact

- `select_embedding_sources`: CLI first failed with wrong `--target` option; no symbol edit made beyond caller/helper usage.
- `embed_reasoning_entry`: CRITICAL, 12 impacted, 2 direct callers (`journal.py:on_strategy_match`, `scripts/backfill_reasoning_embeddings.py:backfill`). Mitigation: kept function signature/behavior intact, removed journal caller via Task 2, worker calls preserved.
- `TradeJournalManager`: LOW, 0 direct upstream impacted. Mitigation: constructor default `redis_client=None` preserves tests/scripts.
- `on_strategy_match`: CRITICAL, 9 impacted, 4 direct script callers, 20 process hits. Mitigation: return contract unchanged; DB insert behavior unchanged; embedding moved to non-blocking enqueue.
- `run_trader`: LOW, 1 direct file impact. Mitigation: single construction change passes existing Redis client.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Environment] WSL verification distro corrected**
- **Found during:** Task 1 verification
- **Issue:** Earlier verification used unavailable `wsl -d Ubuntu-24.04`, while repo runtime documentation uses `wsl -d Aureus`.
- **Fix:** Ran unit and DB/Redis runtime E2E through `wsl -d Aureus`; E2E passed with exit code `0`.
- **Files modified:** none
- **Commit:** n/a

**3. [Rule 1 - Worker resilience] Embedding job exception crashed worker path**
- **Found during:** Verifier gap fix
- **Issue:** `ReasoningEmbeddingWorker.process_once()` propagated embedding exceptions and continuous worker loop lacked catch/log fallback.
- **Fix:** `process_once()` now logs job failure and returns `False` without `XDEL`, leaving message retryable; continuous loop catches unexpected exceptions and continues.
- **Files modified:** `services/aureus-trader/reasoning_embeddings.py`, `services/aureus-trader/reasoning_embedding_worker.py`, `services/aureus-trader/tests/test_reasoning_embedding_queue.py`
- **Commit:** 5e97765

**2. [Rule 1 - Test expectation] Existing reasoning linkage assertions mismatched current SQL**
- **Found during:** Task 2 verification
- **Issue:** Two old tests asserted obsolete `UPDATE aureus_reasoning_entries` argument positions.
- **Fix:** Updated assertions to match actual current SQL args without changing runtime logic.
- **Files modified:** `services/aureus-trader/tests/test_journal.py`
- **Commit:** efcaf81

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: redis-queue-consumer | `services/aureus-trader/reasoning_embeddings.py` | New Redis Stream consumer validates JSON shape enough for `entry_id` and non-empty selected sources before DB update. |
| threat_flag: worker-db-update | `services/aureus-trader/reasoning_embedding_worker.py` | New worker process updates `aureus_reasoning_entries` embeddings from queued jobs. |

## Known Stubs

None.

## Self-Check: PASSED

- Created files exist.
- Commits exist: `42e0346`, `efcaf81`, `133ab74`.
- Execute-order gating files not modified.
