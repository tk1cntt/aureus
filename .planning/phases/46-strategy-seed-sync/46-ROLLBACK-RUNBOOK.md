# 46 Strategy Seed Sync Rollback Runbook

## Pre-check

1. Chạy dry-run và lưu diff + snapshot id:
   `wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus && ./.venv/bin/python services/aureus-signal/scripts/strategy_seed_sync_dryrun.py --output /mnt/d/Aureus/services/aureus-signal/scripts/snapshots/latest-diff.json"`
2. Pass khi output có `"mode": "dry-run"`, có `"snapshot"`, và `counts.activate/deactivate`.
3. Lưu log command + output vào ticket vận hành trước khi rollout.

## Rollout

1. Apply seed sync:
   `wsl -d Aureus -e bash -lc "docker exec aureus-signal-dev python -m engine.strategies.seed_strategies"`
2. Refresh runtime strategies:
   `wsl -d Aureus -e bash -lc "docker exec aureus_redis_dev redis-cli PUBLISH aureus:cmd:refresh_strategies ALL"`
3. Pass khi log có `seed sync completed before reload` và không có error stacktrace.

## Rollback

1. Preview rollback từ snapshot:
   `wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus && ./.venv/bin/python services/aureus-signal/scripts/strategy_seed_sync_rollback.py --snapshot /mnt/d/Aureus/services/aureus-signal/scripts/snapshots/seed-sync-YYYYmmdd-HHMMSS.json"`
2. Nếu preview đúng, apply rollback:
   `wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus && ./.venv/bin/python services/aureus-signal/scripts/strategy_seed_sync_rollback.py --snapshot /mnt/d/Aureus/services/aureus-signal/scripts/snapshots/seed-sync-YYYYmmdd-HHMMSS.json --apply"`
3. Pass khi output trả `"mode": "apply"`, `"count"` đúng phạm vi kỳ vọng, và không có `rollback_error`/`snapshot_invalid_schema`.
