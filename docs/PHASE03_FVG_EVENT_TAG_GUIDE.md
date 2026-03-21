# PHASE03_FVG_EVENT_TAG_GUIDE

Ngày lưu: 2026-03-21 01:00 (+07)

## 1) Phase 03 đã làm được gì

- Harden FVG logic tại:
  - `services/aureus-signal/engine/signals/fvg.py`
  - `services/aureus-signal/engine/signals/fvg_up.py`
  - `services/aureus-signal/engine/signals/fvg_down.py`
- Giữ nguyên dual contract:
  - **Event keys (transient):** `fvg_bull_new`, `fvg_bear_new`, `fvg_bull_mitigated`, `fvg_bear_mitigated`
  - **Strategy tags:** `fvg_up`, `fvg_down`
- Bổ sung/khóa test coverage:
  - `test_fvg_o1.py`
  - `test_fvg_integration_execute_signals_for_candle.py`
  - `test_fvg_integration_live_engine.py`
  - `test_signal_contract_normalization.py` (FVG contract assertions)
- Validation pass: các gate xanh, coverage tổng FVG scope ~`87%` (>=80%).

## 2) Event vs Tag khác nhau thế nào

### Event (transient_signals)

- Là tín hiệu **vừa xảy ra trong tick hiện tại**.
- Ghi vào `state_obj.transient_signals`.
- Dùng cho runtime/event pipeline (snapshot trigger, structural event detection).
- Với FVG: phát từ `fvg.py`.

Ví dụ keys:
- `fvg_bull_new`
- `fvg_bear_new`
- `fvg_bull_mitigated`
- `fvg_bear_mitigated`

Liên quan:
- `engine/event_filter.py` (`STRUCTURAL_TAGS`) dùng các key này để quyết định persist snapshot.

### Tag (signal_history)

- Là nhãn tín hiệu để strategy match chuỗi theo thời gian.
- Đi vào `state_obj.signal_history`.
- Dùng cho scoring/sequence matching trong strategy.
- Với FVG: phát từ `fvg_up.py`, `fvg_down.py`.

Ví dụ tags:
- `fvg_up`
- `fvg_down`

Liên quan:
- `engine/strategies/template.py` match theo `item["tag"]` trong history.

## 3) Cách dùng đúng

### Dùng Event khi cần “just happened now”

- Trigger snapshot write
- Trigger event-driven logic runtime
- Theo dõi structural changes ngắn hạn

### Dùng Tag khi cần “sequence + score” cho strategy

- Định nghĩa chuỗi theo tag (vd: `fvg_up` -> `choch_up` -> `ema_21_up`)
- Tính điểm theo trọng số và điều kiện required/max_wait
- Quyết định trigger intent

## 4) Ứng dụng vào strategy

Khuyến nghị luồng:
1. Signal layer phát `fvg_up/fvg_down` vào `signal_history`.
2. Strategy layer (`TemplateStrategy`) đọc history và match sequence theo tag.
3. Runtime/event layer dùng transient event keys để phục vụ persist/monitoring.

## 5) Rule thực hành

- **Không dùng transient event key làm sequence chính cho strategy dài hơi.**
- **Dùng tag trong history cho logic chiến lược.**
- **Giữ dual compatibility** để không phá runtime cũ và không phá strategy sequence.
