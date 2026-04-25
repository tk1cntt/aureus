# Quick Task 260425-aln Summary

## Objective
Viết hàm classify TPO shape cho 4 dạng `D/B/p/b` kèm tỷ lệ nhận dạng (%) và cập nhật hiển thị trong SIGNAL ALERT Telegram.

## GitNexus Impact Analysis
- `build_indicator_snapshot_for_telegram` (`services/aureus-signal/engine/indicator_snapshot.py`) → **CRITICAL**
  - d=1: `_process_candle_work_item`
  - Affected process group: candle processing runtime flows
- `_format_indicator_section` (`services/aureus-notifier/formatters.py`) → **LOW**
  - d=1: `format_signal_event`
  - d=2/d=3: `enqueue` → `run_notifier`
- `_build_profile` (`services/aureus-signal/engine/signals/tpo.py`) → **LOW**
  - d=1: internal TPO compute flow

## Scope implemented
### 1) TPO shape classify + confidence
- `services/aureus-signal/engine/signals/tpo.py`
  - Bổ sung classify 4 shape `D/B/p/b` dựa trên profile levels/counts.
  - Tính `shape_confidence_pct` và `shape_scores_pct` (phân phối % giữa 4 shape).
  - Mở rộng output block TPO thành:
    - `POC`, `VAH`, `VAL`
    - `shape`, `shape_confidence_pct`, `shape_scores_pct`
  - Giữ tương thích giá trị cũ (POC/VAH/VAL vẫn giữ nguyên semantic).

### 2) Telegram SIGNAL ALERT formatting
- `services/aureus-notifier/formatters.py`
  - Cập nhật formatter TPO để hiển thị thêm:
    - `Shape:<D|B|p|b> (<xx.x>%)`
  - Chỉ render khi payload có `shape` + `shape_confidence_pct` hợp lệ.

### 3) Tests updated
- `services/aureus-signal/tests/test_tpo_signal.py`
  - Update expected keys của TPO blocks.
  - Thêm test cho phân phối xác suất shape và confidence.
- `services/aureus-notifier/tests/test_formatters.py`
  - Update fixture TPO payload có shape/confidence.
  - Assert output chứa `Shape:D (82.5%)`.

## Verification
- `pytest services/aureus-signal/tests/test_tpo_signal.py services/aureus-notifier/tests/test_formatters.py services/aureus-signal/tests/test_indicator_snapshot.py -q`
  - **42 passed**

## Commits
- Source commit: `52bd672` — `feat(tpo): classify D/B/p/b shape with confidence for signal alerts`

## Notes
- `npx gitnexus detect_changes` trong môi trường hiện tại vẫn báo `unknown command`; đã fallback bằng review `git diff`/`git diff --stat` để kiểm soát phạm vi thay đổi trước commit.
