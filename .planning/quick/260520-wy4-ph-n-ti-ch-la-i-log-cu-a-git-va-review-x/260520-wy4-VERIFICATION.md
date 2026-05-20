status: human_needed

# Verification quick-260520-wy4 sau commit 75a7ec6

Mục tiêu: chứng minh bug hiện tại không còn nằm ở MQL5 close mapping 260520-9kx, mà nằm ở ORDER_OPENED parent trade upsert khiến `aureus_trades` kẹt `SENT`; fix phải dùng exact `trace_id`, không fallback rộng.

Kết luận: code gap chính đã đóng. Targeted regression pass. DB transaction proof pass. Còn cần human/live service verification vì runtime service cần restart và cần lifecycle MT5 thật để chứng minh journal close/winrate có row mới.

## Must-haves

| # | Must-have | Trạng thái | Bằng chứng |
|---|---|---|---|
| 1 | Root cause xác định bằng git/runtime/DB, không đoán | passed | `260520-wy4-SUMMARY.md` ghi DB trước fix: `aureus_trade_journal` hôm nay `0`, `aureus_trades` hôm nay `SENT=125`; `260520-9kx` đã sửa close correlation nhưng chưa sửa parent status conflict. |
| 2 | ORDER_OPENED có exact trace_id phải rời `SENT` | passed | Commit `75a7ec6` sửa `services/aureus-trader/journal.py`: conflict update trong `on_order_opened` set `status='OPEN'` và `filled_at=COALESCE(aureus_trades.filled_at, now())`. |
| 3 | Không thêm fallback rộng ticket/cmd_id/random | passed | Diff `75a7ec6` chỉ sửa parent upsert bằng existing `trace_id`; không thêm fallback ticket-only/cmd_id-only/symbol-time/random. |
| 4 | Targeted regression pass | passed | `wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus/services/aureus-trader && PYTHONPATH=. ../../.venv/bin/python -m pytest tests/test_journal.py::TestReasoningBank::test_on_order_opened_ensures_parent_trade_before_reasoning_insert -q"` -> `1 passed in 0.14s`. |
| 5 | DB E2E/proof với database thật xác nhận update data | passed | `aureus_timescaledb_dev` transaction: seed `e2e-lifecycle-wy4-verify` status `SENT`, update exact `trace_id` -> returned `e2e-lifecycle-wy4-verify | OPEN | 2605204`, rollback cleanup. |
| 6 | Live MT5/service lifecycle tạo journal close/winrate | human_needed | Chưa có bằng chứng runtime sau restart service và trade close thật. |

Score: 5/6 automated verified, 1/6 cần human/live verification.

## Key links

| Link | Trạng thái | Bằng chứng |
|---|---|---|
| Existing DB writer creates parent trade `SENT` | passed | Runtime DB evidence trong summary: 125 row hôm nay kẹt `SENT`. |
| `ORDER_OPENED` reaches `on_order_opened` | passed | Runtime logs trong summary có `ORDER_OPENED` với `cmd_id`/ticket quanh 16:18. |
| Parent upsert conflict previously kept `SENT` | passed | Summary identifies conflict update did not update `status`/`filled_at`. |
| Parent upsert now moves row to `OPEN` | passed | Code commit `75a7ec6`; DB transaction proof returned `OPEN`. |
| `260520-9kx` close mapping remains exact | passed | No MQL5/gateway files changed in `75a7ec6`; fix scope only trader journal/tests. |

## Behavioral spot-checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Focused journal regression | `wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus/services/aureus-trader && PYTHONPATH=. ../../.venv/bin/python -m pytest tests/test_journal.py::TestReasoningBank::test_on_order_opened_ensures_parent_trade_before_reasoning_insert -q"` | `1 passed in 0.14s` | passed |
| Commit contains expected files | `git show --stat --oneline 75a7ec6` | 3 files: `journal.py`, `tests/conftest.py`, `tests/test_journal.py` | passed |
| DB exact trace update proof | WSL docker exec psql transaction against `aureus_timescaledb_dev` | Returned `e2e-lifecycle-wy4-verify | OPEN | 2605204`; rollback | passed |
| Live service restart + new trade lifecycle | not run | Needs operator/runtime step | human_needed |

## GitNexus / scope

- Executor ran `gitnexus_impact` for `on_order_opened`: CRITICAL, 8 impacted, 3 direct, 9 affected processes.
- Direct d=1 listed in summary: `on_order_filled`, `verify_reasoning_bank_reuse_e2e.py:run_e2e`, `verify_reasoning_bank_db_e2e.py:main`.
- `gitnexus_detect_changes` unavailable in installed CLI (`unknown command` for detect variants). Fallback scoped review used. No HIGH/CRITICAL warning ignored; edited symbol was intended lifecycle hot path.

## Anti-pattern scan

| File | Pattern | Severity | Impact |
|---|---|---|
| `services/aureus-trader/journal.py` | No broad fallback; exact `trace_id` conflict update only | none | Maintains correlation invariant. |
| `services/aureus-trader/tests/test_journal.py` | Focused assertion on parent upsert status behavior | none | Regression covers SENT -> OPEN conflict path. |
| `services/aureus-trader/tests/conftest.py` | Mock trace arg alignment | none | Test validates correct trace input. |

## Human verification required

1. Restart affected Python service so `services/aureus-trader/journal.py` code is loaded.
   Expected: new `ORDER_OPENED` event updates existing `aureus_trades` row from `SENT` to `OPEN`, sets `filled_at`.
   Why human: verifier does not mutate live service runtime state.

2. Run/observe new MT5 lifecycle after prior provider build.
   Expected: `ORDER_OPENED` -> DB `OPEN`; later `ORDER_CLOSED` keeps `cmd_id`/`trace_id` from 260520-9kx and creates/updates journal close row.
   Why human: needs broker/MT5 runtime and real close event.

3. Re-query journal/winrate after at least one real close.
   Expected: `aureus_trade_journal` has closed row for today; strategy winrate query no longer empty.
   Why human: current automated DB proof only verifies parent status update, not live market close.

## Gaps

Không còn automated code gap cho bug `SENT` parent trade conflict. Trạng thái tổng là `human_needed` vì cần restart service và lifecycle live MT5/DB/notifier evidence để chứng minh end-to-end winrate có data mới.

Verified: 2026-05-20
Verifier: Claude
