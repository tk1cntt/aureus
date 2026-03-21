---
stepsCompleted: [1, 2, 3]
inputDocuments: []
session_topic: 'tối ưu gate realtime candle / xử lý integrity'
session_goals: 'xác định root cause ưu tiên, checklist fix, patch đề xuất, plan benchmark'
selected_approach: 'ai-recommended'
techniques_used: ['Five Whys', 'Constraint Mapping', 'Solution Matrix']
ideas_generated: ['P0: gate bypass do block bị comment-out', 'P1: backfill polling gây DB I/O spike', 'P1: full-window hash O(n) mỗi candle', 'P2: lock scope quá rộng trong symbol loop']
context_file: ''
technique_execution_complete: true
facilitation_notes: 'Ưu tiên tính thực thi production-safe, tách quick wins và medium-risk patches.'
---

# Brainstorming Session Results

**Facilitator:** Boss
**Date:** 2026-03-21T10:04:59+07:00

## Session Overview

**Topic:** tối ưu gate realtime candle / xử lý integrity
**Goals:** xác định root cause ưu tiên, checklist fix, patch đề xuất, plan benchmark

### Context Guidance

_Không có context file bổ sung. Phiên này dùng trực tiếp code context từ `live_engine.py` và `manager.py`._

### Session Setup

_Bài toán tập trung vào tác động hiệu năng của gate pipeline trong realtime candle path và lý do window integrity gate thường reject. Kết quả mong muốn là danh sách nguyên nhân ưu tiên và kế hoạch xử lý/đo lường có thể hành động ngay._

## Technique Selection

**Approach:** AI-Recommended Techniques
**Recommended:** Five Whys → Constraint Mapping → Solution Matrix

## Technique Execution Results

### 1) Root cause ưu tiên (ranked)
- **P0 – Gate bypass do block gate bị comment-out trong loop realtime**
  - Evidence: `live_engine.py` đoạn gate checks nằm trong block `''' ... '''` ngay trước `window_manager.update(...)`.
  - Tác động: hệ thống xử lý candle mà không qua closed-candle/backfill/window-integrity gate; reject reason và hành vi gate mất hiệu lực thực tế.

- **P1 – Integrity metadata tính theo full window mỗi candle (`_build_integrity_metadata`)**
  - Evidence: `manager.py` tạo `timestamps`, tính `deltas`, và SHA256 trên toàn bộ window mỗi lần `update`.
  - Tác động: O(n) CPU mỗi candle/symbol; n lớn sẽ kéo latency tăng dần.

- **P1 – Background `integrity_and_recalc_task` polling DB liên tục**
  - Evidence: `integrity_and_recalc_task` gọi `find_gaps(... lookback_hours=1)` theo chu kỳ 180s/symbol.
  - Tác động: DB read amplification khi nhiều symbol; cạnh tranh tài nguyên với luồng ingest/execute realtime.

- **P2 – Lock scope rộng trong symbol loop**
  - Evidence: `async with symbol_locks[symbol]` bao quanh gần như toàn bộ logic: update, signal calc, strategy eval, redis/db side effects.
  - Tác động: tăng queueing delay khi burst entries, giảm throughput realtime.

### 2) Checklist fix (ưu tiên triển khai)
1. **Khôi phục gate path có kiểm soát**
   - Bật lại gate checks bằng feature flag (`enable_realtime_gates`).
   - Log reject theo mã reason chuẩn hóa (counter + sample).
2. **Tách “hard reject” vs “soft degrade”**
   - Hard reject: candle không đóng / timestamp invalid.
   - Soft degrade: window integrity fail → cho phép process với `degraded_mode=true` + cảnh báo.
3. **Giảm chi phí integrity computation**
   - Chuyển sang incremental integrity state (last_t, expected_next_t, contiguous_count, rolling hash).
4. **Giảm lock contention**
   - Giữ lock cho mutation critical section; tách DB/Redis heavy work ra ngoài lock nếu safe.
5. **Tối ưu backfill polling**
   - Backoff động theo trạng thái: khi READY ổn định thì poll thưa hơn; khi GAP_DETECTED thì poll nhanh hơn có giới hạn.
6. **Bổ sung metrics bắt buộc**
   - `gate_reject_rate`, `gate_reason_count`, `candle_process_latency_ms`, `lock_wait_ms`, `integrity_compute_ms`, `db_gap_check_ms`.

### 3) Patch đề xuất (theo mức rủi ro)
- **Patch A (Low risk, triển khai nhanh 1-2 ngày):**
  - Re-enable gate block dưới feature flag.
  - Chuẩn hóa reason codes + metrics/logging.
  - Không đổi hành vi business logic cốt lõi.

- **Patch B (Medium risk, 2-4 ngày):**
  - Refactor `WindowManager` integrity từ full-scan sang incremental update.
  - Giữ fallback full-recompute khi phát hiện out-of-order/backfill merge.

- **Patch C (Medium-high risk, 3-5 ngày):**
  - Thu hẹp lock scope và tách side-effect async.
  - Bổ sung regression guard cho race condition snapshot/state.

### 4) Benchmark plan (trước/sau patch)
- **Dataset/Load profile**
  - Replay 3 mức tải: 1x, 3x, 5x throughput candle hiện tại.
  - Kịch bản có/không out-of-order candles và có/không gap recovery.

- **KPI chính**
  - p50/p95 `candle_process_latency_ms`
  - throughput candles/sec/symbol
  - `gate_reject_rate` theo reason
  - CPU%, event-loop lag, DB read/write latency

- **Thiết kế đo lường**
  - Chạy baseline (current), Patch A, Patch A+B, Patch A+B+C.
  - Mỗi run 15-30 phút, warm-up 5 phút, lưu metric snapshots theo mốc 1 phút.

- **Tiêu chí đạt**
  - Giảm p95 latency ≥ 20% so baseline.
  - Không tăng reject sai (false reject) vượt ngưỡng đã định.
  - Không xuất hiện data integrity regression trên window contiguous checks.
