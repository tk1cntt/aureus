---
phase: 260503-sxx-fix-aureus-reasoning-entries-fk-blocking
plan: 01
subsystem: aureus-trader
tags: [reasoning-bank, foreign-key, journal, db-e2e]
dependency_graph:
  requires: [aureus_trade_journal, aureus_trade_signal_snapshots, aureus_trades]
  provides: [fk-safe-reasoning-entry-persistence]
  affects: [services/aureus-trader/journal.py]
tech_stack:
  added: []
  patterns: [asyncpg-parameterized-sql, on-conflict-do-nothing]
key_files:
  created: []
  modified:
    - services/aureus-trader/journal.py
    - services/aureus-trader/tests/test_journal.py
    - services/aureus-trader/scripts/verify_reasoning_bank_reuse_e2e.py
decisions:
  - Giữ FK aureus_reasoning_entries.trace_id sang aureus_trades(trace_id), sửa lifecycle bằng minimal parent upsert.
metrics:
  duration: "unknown"
  completed_date: "2026-05-03"
---

# Quick 260503-sxx Summary: Fix Reasoning Bank FK blocking

## Tóm tắt

Sửa `ORDER_OPENED` để tạo/đảm bảo parent row tối thiểu trong `aureus_trades` trước khi insert `aureus_reasoning_entries`, giữ nguyên FK và persist `reasoning_text` thật cho scenario trước đây thiếu parent.

## Công việc đã làm

- Thêm unit regression trong `services/aureus-trader/tests/test_journal.py`:
  - `on_order_opened` phải chạy `INSERT INTO aureus_trades` trước `INSERT INTO aureus_reasoning_entries`.
  - Reasoning insert fail vẫn non-blocking.
- Sửa production source trong `services/aureus-trader/journal.py`:
  - Bỏ nhánh skip khi parent trade thiếu.
  - Thêm `INSERT INTO aureus_trades (...) ON CONFLICT (trace_id) DO NOTHING` trong cùng transaction trước reasoning insert.
  - Giữ parameterized SQL, không format dữ liệu event vào SQL string.
  - Giữ enqueue embedding sau insert reasoning thành công.
- Sửa real DB E2E trong `services/aureus-trader/scripts/verify_reasoning_bank_reuse_e2e.py`:
  - Scenario `no_parent_trace_id` gọi `on_strategy_match` rồi `on_order_opened`, không pre-insert `aureus_trades` thủ công.
  - Assert journal count = 1, snapshot count = 1, reasoning count = 1.
  - Assert `reasoning_text` non-empty và chứa `reasoning_reuse_no_parent`, `XAUUSD`, `BUY`, `london`, `cisd_m15=1`.

## Bằng chứng verify

### Unit tests

Command:

```bash
wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus && ./.venv/bin/python -m pytest services/aureus-trader/tests/test_journal.py -q"
```

Kết quả:

```text
76 passed in 0.42s
```

### RED trước fix

Cùng command unit test fail trước production fix:

```text
FAILED test_on_order_opened_ensures_parent_trade_before_reasoning_insert
FAILED test_on_order_opened_reasoning_insert_failure_non_blocking
2 failed, 74 passed
```

### Real DB E2E

Command đầu với default DSN fail do host DB trong config không resolve từ WSL:

```text
socket.gaierror: [Errno -2] Name or service not known
```

Theo `RUN_SERVICES.md`, chạy service bằng bash vì file script có CRLF shebang issue khi chạy trực tiếp:

```bash
wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus && bash ./scripts/dev-service.sh"
```

Command DB E2E pass với DSN dev từ `.env`:

```bash
wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus && AUREUS_DB_DSN=postgresql://aureus:aureus_password@localhost:5433/aureus ./.venv/bin/python services/aureus-trader/scripts/verify_reasoning_bank_reuse_e2e.py"
```

Kết quả:

```text
PASS reasoning bank reuse DB E2E trace_id=e2e-reasoning-reuse-701a414f86c5 no_parent_trace_id=e2e-reasoning-noparent-9221720c019a
```

E2E chứng minh `no_parent_trace_id=e2e-reasoning-noparent-9221720c019a` tạo được `aureus_reasoning_entries` row và persist `reasoning_text` cho scenario trước đây thiếu parent.

## GitNexus

### Impact trước edit

Command plan đề xuất fail vì CLI syntax khác:

```bash
npx gitnexus impact --target TradeJournalManager --direction upstream
```

Kết quả:

```text
error: unknown option '--target'
```

Fallback pass:

```bash
npx gitnexus impact TradeJournalManager --direction upstream --repo Aureus
```

Kết quả:

```json
{
  "risk": "LOW",
  "summary": {
    "direct": 0,
    "processes_affected": 0,
    "modules_affected": 0
  }
}
```

Blast radius: LOW, 0 direct callers, 0 affected processes, 0 affected modules.

### Detect changes trước commit

Commands theo hướng dẫn không có trong CLI hiện tại:

```bash
npx gitnexus detect-changes --repo Aureus
npx gitnexus detect_changes --repo Aureus
```

Kết quả:

```text
error: unknown command 'detect-changes'
error: unknown command 'detect_changes'
```

Fallback dùng scoped `git diff`/`git status`. Scope đúng: chỉ `journal.py`, `test_journal.py`, `verify_reasoning_bank_reuse_e2e.py` được commit. User work vẫn còn untouched/uncommitted:

```text
 M mql5/AureusProvider_v2.mq5
?? mql5/AureusProvider_v2.ex5
?? stable/
```

## Commits

- `4fbcaca` test(260503-sxx): add no-parent reasoning FK regression
- `f1177a0` fix(260503-sxx): ensure trade parent before reasoning insert

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] GitNexus CLI syntax khác plan**
- **Found during:** Task 2, Task 3
- **Issue:** `--target` và `detect-changes` không tồn tại trong CLI hiện tại.
- **Fix:** Dùng `npx gitnexus impact TradeJournalManager --direction upstream --repo Aureus`; dùng scoped `git diff/status` khi detect changes unavailable.
- **Files modified:** none
- **Commit:** none

**2. [Rule 3 - Blocking] Service script CRLF shebang**
- **Found during:** Task 3
- **Issue:** `./scripts/dev-service.sh` fail với `/bin/bash^M: bad interpreter`.
- **Fix:** Chạy bằng `bash ./scripts/dev-service.sh` theo WSL.
- **Files modified:** none
- **Commit:** none

## Auth Gates

None.

## Known Stubs

None found in modified files that block plan goal.

## Threat Flags

None. Không thêm endpoint, auth path, file access, hoặc schema trust-boundary mới. DB trust boundary đã có trong plan threat model.

## Self-Check: PASSED

- `services/aureus-trader/journal.py` exists.
- `services/aureus-trader/tests/test_journal.py` exists.
- `services/aureus-trader/scripts/verify_reasoning_bank_reuse_e2e.py` exists.
- Commit `4fbcaca` exists.
- Commit `f1177a0` exists.
- Real DB E2E pass và in trace IDs.
