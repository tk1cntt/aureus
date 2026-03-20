# Signal Contract Cleanup + Full Risk Mitigation (A-D)

Mục tiêu: giữ hướng **Approach 1 (nhẹ, an toàn)** nhưng bổ sung đầy đủ cơ chế giảm thiểu rủi ro A-D để triển khai thực tế ổn định.

## User Review Required

> [!IMPORTANT]
> Kế hoạch này thêm rollout an toàn cho FVG bằng feature flag (`AUREUS_ENABLE_FVG_SIGNAL`) để có thể bật/tắt nhanh nếu phát sinh side-effect sản lượng event.

## Proposed Changes

### 1) Contract Alignment (Risk A)

#### [MODIFY] [base.py](file:///d:/Aureus/services/aureus-signal/engine/signals/base.py)
- Chuẩn hóa abstract signature sang runtime thật: `calculate(df, state_obj, **kwargs)`.
- Cập nhật docstring contract để nhất quán với cách call ở `live_engine.py`/`signal_computer.py`.

#### [MODIFY] [signals/*.py](file:///d:/Aureus/services/aureus-signal/engine/signals)
- Audit toàn bộ signal implementation để đảm bảo tương thích call-site:
  - chấp nhận `**kwargs` **hoặc** có signature vẫn nhận được `redis_client/symbol`.
- Với file nào quá cứng signature, chuẩn hóa nhẹ để tránh `TypeError` khi runtime truyền kwargs.

---

### 2) FVG Single Path + Safe Rollout (Risk B)

#### [MODIFY] [signal_factory.py](file:///d:/Aureus/services/aureus-signal/engine/signal_factory.py)
- Đăng ký `FVGSignal` với key `fvg`.
- Bọc đăng ký qua feature flag env:
  - `AUREUS_ENABLE_FVG_SIGNAL=1` -> bật `fvg`
  - mặc định `0` -> tắt để rollout dần.
- Khi flag OFF, normalized snapshot vẫn trả `fvg_state` dạng `MISSING` có source rõ ràng.

#### [MODIFY] [fvg.py](file:///d:/Aureus/services/aureus-signal/engine/signals/fvg.py)
- Giữ nguyên core logic detect/mitigation.
- Bổ sung guard tối thiểu (không đổi hành vi business): kiểm tra `state_obj` có thuộc tính cần thiết trước khi mutate/log.

#### [KEEP-AS-IS] [fvg_up.py](file:///d:/Aureus/services/aureus-signal/engine/signals/fvg_up.py)
#### [KEEP-AS-IS] [fvg_down.py](file:///d:/Aureus/services/aureus-signal/engine/signals/fvg_down.py)
- Giữ legacy file, không wiring vào factory trong batch này.

---

### 3) Snapshot Contract Hardening (Risk C)

#### [MODIFY] [signal_factory.py](file:///d:/Aureus/services/aureus-signal/engine/signal_factory.py)
- `build_normalized_signal_snapshot`:
  - ưu tiên `transient_signals["fvg_state"]` nếu có,
  - fallback `MISSING` + `source` metadata (không hardcode `FVG_NOT_IMPLEMENTED`).

#### [MODIFY] [test_signal_contract_normalization.py](file:///d:/Aureus/services/aureus-signal/tests/test_signal_contract_normalization.py)
- Cập nhật test để assert contract ổn định thay vì reason string legacy.
- Thêm test cho cả 2 mode factory:
  - flag OFF: không có/không chạy FVG path nhưng `fvg_state` hợp lệ,
  - flag ON: có key `fvg` trong signal set.

---

### 4) State Coupling Guardrails (Risk D)

#### [MODIFY] [fvg.py](file:///d:/Aureus/services/aureus-signal/engine/signals/fvg.py)
#### [MODIFY] [structure.py](file:///d:/Aureus/services/aureus-signal/engine/signals/structure.py)
#### [MODIFY] [sweep.py](file:///d:/Aureus/services/aureus-signal/engine/signals/sweep.py)
- Bổ sung guard nhẹ tại các điểm coupling nhạy cảm:
  - `hasattr`/default fallback cho field không bắt buộc,
  - tránh crash khi state chưa đủ shape trong unit/integration edge case.
- Không refactor lớn protocol trong batch này; chỉ harden điểm crash-prone.

#### [MODIFY] [tests/*signal*.py](file:///d:/Aureus/services/aureus-signal/tests)
- Thêm test edge case với dummy/minimal state để xác minh guardrails không làm vỡ luồng chính.

## Verification Plan

### Automated Tests
1. `python -m pytest d:/Aureus/services/aureus-signal/tests/test_signal_contract_normalization.py -q`
2. `python -m pytest d:/Aureus/services/aureus-signal/tests/test_live_engine_gates.py d:/Aureus/services/aureus-signal/tests/test_decision_trace_schema.py -q`
3. `python -m pytest d:/Aureus/services/aureus-signal/tests -k "fvg or signal_contract or sweep or structure" -q`

### Manual Verification
- Chạy local với `AUREUS_ENABLE_FVG_SIGNAL=0`, xác nhận hệ thống ổn định như baseline.
- Bật `AUREUS_ENABLE_FVG_SIGNAL=1` trên replay ngắn, so sánh:
  - số lượng event/transient,
  - snapshot `fvg_state`,
  - log lỗi runtime.
- Nếu side-effect tăng bất thường, rollback tức thì bằng cách tắt flag.

## Rollout / Rollback
- **Rollout**: deploy mặc định flag OFF -> quan sát -> bật ON theo môi trường kiểm thử trước production.
- **Rollback**: tắt env flag, không cần revert code để dừng FVG path ngay.
