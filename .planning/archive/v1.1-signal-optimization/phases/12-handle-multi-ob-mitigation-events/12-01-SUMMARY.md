# 12-01 Summary: Deterministic Last-Event-Wins for OB Mitigation

## Accomplishments
- Refactor `_verify_mitigations` để collector semantics rõ ràng theo **last-event-wins**.
- Giữ nguyên legacy transient signal keys:
  - `ob_bull_mitigated`
  - `ob_bear_mitigated`
- Không thêm aggregate keys dạng `ob_*_mitigated_events`.
- Bổ sung regression coverage cho event filter nhận diện legacy mitigation keys.

## User-facing Impact
- Hành vi mitigation trong cùng candle deterministic hơn (event cuối cùng thắng).
- Dashboard/consumer không cần đổi contract vì payload shape legacy được giữ nguyên.
- Tránh phát sinh side-effect từ schema expansion ngoài scope phase.

## Verification Snapshot
- `tests/test_structure_integration_execute_signals_for_candle.py`: pass
- `unittest/test_event_filter.py`: pass
- `tests/test_sweep_integration_execute_signals_for_candle.py` + structure integration: pass
- Guard check xác nhận không xuất hiện aggregate mitigation keys: pass
