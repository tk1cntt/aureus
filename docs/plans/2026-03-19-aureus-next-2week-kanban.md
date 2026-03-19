# Aureus 2-Week Kanban Board

## To Do
- [ ] Clean lint/type warnings in `execution_client.py`
- [ ] Clean lint/type warnings in `data_client.py`
- [ ] Add CI quality gates (`pytest` + lint + type-check)
- [ ] Finalize deploy preflight checklist
- [ ] Define SLO v1 + metric mapping
- [ ] Build baseline dashboards
- [ ] Wire/tune alert thresholds
- [ ] Validate kill-switch trigger flow
- [ ] Run rollback drill and capture MTTR
- [ ] Run chaos test: Redis disconnect
- [ ] Run chaos/replay test: duplicate + stale stream
- [ ] Validate idempotency/OCO under load
- [ ] Run shadow rehearsal + canary gate automation
- [ ] Publish final Go/No-Go report

## In Progress
- [ ] (update daily)

## Done
- [x] Complete Nautilus deep integration production hardening tasks 1–7
- [x] Pass `services/aureus-nautilus-node` test suite (`21 passed`)
- [x] Save 2-week roadmap and day-by-day breakdown

## Blockers / Risks
- [ ] Docker CLI unavailable in current tool PATH (manual runtime check may be needed)
- [ ] Remaining lint/type warnings in `data_client.py`, `execution_client.py`
