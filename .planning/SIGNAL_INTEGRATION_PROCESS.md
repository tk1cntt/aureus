# Signal Integration Process (Aureus Signal)

## Mục tiêu
Tránh thiếu sót integration như trường hợp ATR vừa gặp: wiring thiếu, test bị che lỗi, và assert lệch schema runtime.

## Issues đã gặp (rút kinh nghiệm)
1. **Thiếu wiring trong factory**  
   `atr_14` chưa được đăng ký trong `engine/signal_factory.py::create_signal_set(...)`.
2. **Runtime test bị mask lỗi wiring**  
   Test `test_atr_integration_live_engine.py` patch `create_signal_set` trả ATR trực tiếp, nên factory thật bị sai vẫn pass.
3. **Lệch contract dữ liệu signal_history**  
   Assertion dùng `ts` trong khi runtime lưu timestamp bằng key `t` (`SymbolState.log_signal`).
4. **Coverage helper-level bị thiếu case cũ**  
   Một số test legacy quan trọng bị mất khi refactor.
5. **Thiếu test contract ở tầng factory**  
   Không có test bắt buộc rằng signal mới đã được đăng ký trong `create_signal_set`.

## Process chuẩn khi thêm/chỉnh signal

### 1) Design & Contract trước khi code
- Xác định rõ:
  - signal tag chuẩn (vd: `atr_14`),
  - output payload contract (`tag`, `t`, `value` nếu có),
  - state fields được cập nhật.
- Ghi rõ vị trí wiring bắt buộc:
  - `engine/signal_factory.py` (đăng ký signal),
  - các luồng engine/backtest/signal_computer dùng chung factory.

### 2) Implementation checklist (bắt buộc)
- [ ] Tạo/điều chỉnh class signal trong `engine/signals/`.
- [ ] **Đăng ký signal trong `create_signal_set(...)`**.
- [ ] Không thay đổi key contract runtime nếu chưa có migration/test update đồng bộ.

### 3) Test strategy 3 tầng (không được bỏ)
1. **Factory Contract Test** (chống thiếu wiring)
   - Assert `create_signal_set(...)` có key signal mới (vd: `atr_14`).
2. **Helper-level Integration Test** (logic + state)
   - Chạy qua `execute_signals_for_candle` + `WindowManager`/`SymbolState`.
   - Assert state progression, tag xuất hiện, timestamp key đúng schema (`t`).
3. **Runtime-path Integration Test** (luồng thật)
   - Test qua `run_signal_engine` với fake infra (DB/Redis).
   - **Không mock `create_signal_set` để inject signal cần test**.
   - Chỉ mock các dependency ngoài phạm vi (network/news/IO noise).

### 4) Anti-masking rules
- Không patch factory output cho chính signal đang verify.
- Nếu cần patch để isolate, phải có **ít nhất 1 test khác** chạy qua wiring thật.
- Mọi assert contract phải lấy theo schema runtime hiện tại (nguồn chuẩn: `state.py`, payload persisted).
- **Không được phép xóa các test case cũ (legacy test cases).** Chỉ được phép chỉnh sửa để phù hợp contract/runtime mới và phải giữ nguyên intent kiểm thử ban đầu.

### 5) Regression guard bắt buộc
Mỗi signal mới phải có:
- [ ] 1 factory contract test,
- [ ] 1 helper integration test,
- [ ] 1 runtime-path integration test.

## Lệnh verify chuẩn
```bash
python -m pytest services/aureus-signal/tests/test_signal_contract_normalization.py services/aureus-signal/tests/test_atr_integration_execute_signals_for_candle.py services/aureus-signal/tests/test_atr_integration_live_engine.py -q
```

## Definition of Done cho Signal Integration
- [ ] Signal được đăng ký trong factory.
- [ ] 3 tầng test đều pass.
- [ ] Không có test nào mask wiring thật.
- [ ] Assertion khớp schema runtime (`t` vs `ts` được xác nhận đúng nguồn).
- [ ] **Không xóa test case cũ**; mọi testcase legacy được giữ lại và chỉ chỉnh sửa cho phù hợp khi có thay đổi contract/runtime.
- [ ] Walkthrough/notes cập nhật đầy đủ bài học & evidence.

## PR Review Checklist (bắt buộc trước merge)
- [ ] Có thay đổi signal mới thì đã update `create_signal_set(...)`.
- [ ] Có test contract xác nhận signal key tồn tại trong factory.
- [ ] Runtime integration test không patch factory cho signal đang verify.
- [ ] Không xóa legacy test case; chỉ chỉnh sửa để phù hợp runtime/contract mới.
- [ ] Đã chạy full lệnh verify chuẩn và đính kèm kết quả pass trong PR.
