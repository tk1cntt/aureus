# Phase 12: Handle Multi-OB Mitigation Events - Research

## Objective
Chuẩn hóa hành vi mitigation trong cùng candle theo nguyên tắc **last-event-wins** nhưng vẫn giữ contract legacy (`ob_bull_mitigated`, `ob_bear_mitigated`).

## Scope Constraints
- Không thêm aggregate keys (`ob_*_mitigated_events`).
- Không đổi snapshot/event payload shape cho downstream consumer.
- Giữ trigger `request_ai_update("OB_INTERACTION")` theo mitigation event cuối cùng.

## Key Technical Findings
- Điểm thi công trung tâm là `StructureSignal._verify_mitigations` trong `structure.py`.
- `event_filter.has_structural_event(...)` đã dựa vào legacy keys, nên không cần schema expansion.
- Emission sau khi quét xong OB list giúp hành vi cùng-candle deterministic rõ ràng hơn.

## Chosen Approach
1. Thu collector nội bộ cho bull/bear mitigation cuối cùng trong candle hiện tại.
2. Sau vòng quét, chỉ emit 2 key legacy nếu collector có giá trị.
3. Không lưu event history dạng list trong `transient_signals` ở phase này.

## Research Outcome
- Hướng triển khai phù hợp mục tiêu Phase 12: deterministic behavior + backward compatibility.
- Mở rộng multi-event history được defer cho phase tương lai nếu business cần.
