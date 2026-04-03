# Phase 15.11: Optimize LLM Pulse Context — Research

## Objective
Thiết kế input contract mới cho pulse narrative để LLM phản hồi ổn định ở tần suất cao, dùng nguồn `log_signal_normalize` 60 record gần nhất và không phá output contract hiện tại.

## Scope
- `services/aureus-signal/engine/ai_validator.py`
  - `ContextBuilder.build_pulse_context`
  - `AIBrainClient.generate_pulse`
- Không thay đổi flow call-site `AIValidator.analyze_market`
- Không đổi quyết định từ `validate_trigger/debate`

## Current Code Evidence
1. `build_pulse_context` hiện assemble từ các section mô tả tổng quát (`STRUCTURE`, `LEVELS`, `LIQUIDITY`, `METRICS`), thiếu khối anchor định lượng cố định.
2. `generate_pulse` đang enforce JSON output và `temperature=0.1`, nhưng prompt chưa quy định rõ thứ tự ưu tiên anchor + điều kiện được phép nêu luận điểm mới.
3. Engine đã chuẩn hóa nguồn signal theo `signal_history_normalized` rolling 60 record nên đủ dữ liệu để xây deterministic summary.

## Template Alignment Notes (`chart-analyst-skill.txt`)
- Mẫu yêu cầu phân tích có cấu trúc cố định theo mục: context, setup, plan, đánh giá.
- Tinh thần phù hợp cho pulse là: bias-first, anchor-backed reasoning, concise output, không lan man.
- Vì `generate_pulse` phải giữ JSON phẳng, chỉ áp dụng “template mindset”, không copy nguyên markdown table.

## Proposed Deterministic Contract Direction
1. **Payload blocks cố định (fixed-order):**
   - `PULSE_META` (symbol/time/price/trigger)
   - `ANCHOR_WINDOW` (window size=60, latest timestamp, event density)
   - `STRUCTURE_ANCHORS` (CHOCH/BOS/HH/HL/LH/LL gần nhất)
   - `LIQUIDITY_ANCHORS` (sweep/mitigation/ob-touch gần nhất)
   - `METRIC_ANCHORS` (range, volume ratio)
   - `INSTRUCTION_GUARD` (no-new-claim-without-anchor)
2. **Prompt rules rõ ràng:**
   - Ưu tiên recency nhưng chỉ được suy luận từ anchors có trong payload.
   - Nếu anchor không đổi đáng kể, sentiment/ACI chỉ thay đổi nhẹ.
   - `debate_log` bắt buộc chỉ gồm string phẳng theo key cố định.
3. **Fallback behavior:**
   - Nếu thiếu anchor trọng yếu, trả narrative neutral với confidence thấp thay vì phóng đoán.

## Research Outcome
Phase 15.11 nên đi theo hướng **anchor-first deterministic context contract**: khóa format payload + prompt rule đồng bộ để giảm narrative drift, đồng thời bảo toàn parser contract JSON phẳng cho downstream.
