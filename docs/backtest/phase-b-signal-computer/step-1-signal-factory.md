# Step 1: Extract Signal Factory Function

> **Phase**: B — Signal Computer  
> **Thời gian**: ~30 phút | **Risk**: Thấp (refactor, không đổi logic)  
> **Input**: Signal registration code trong `main.py` (dòng 132-151)  
> **Output**: `services/aureus-signal/engine/signal_factory.py`

---

## Mô tả

Extract phần tạo + đăng ký signals từ `main.py` thành factory function riêng. Function này sẽ được dùng bởi 3 nơi: live engine, signal_computer, và recovery recalc. Đảm bảo output giống 100% so với trước refactor.

## Checklist

- [ ] Tạo file `signal_factory.py`
- [ ] `create_signal_set(symbol) -> Dict[str, BaseSignal]`
- [ ] Copy chính xác logic đăng ký signals từ `main.py`
- [ ] Import tất cả signal classes cần thiết
- [ ] `main.py` thay thế inline code bằng `from engine.signal_factory import create_signal_set`
- [ ] Verify Signal Engine start bình thường sau refactor
- [ ] Verify số lượng signals trả về đúng

## Điều kiện nghiệm thu

| # | Điều kiện | Pass? |
|:---|:---|:---|
| 1 | File `signal_factory.py` tồn tại | [ ] |
| 2 | `create_signal_set('XAUUSD')` trả về dict có ≥ 10 entries | [ ] |
| 3 | `main.py` dùng factory function thay vì inline | [ ] |
| 4 | Signal Engine start không lỗi sau refactor | [ ] |
| 5 | Tất cả signals tính toán bình thường (check Redis state) | [ ] |

## Test

```bash
# 1. Unit test factory
cd services/aureus-signal
python -c "
from engine.signal_factory import create_signal_set
signals = create_signal_set('XAUUSD')
print(f'Signal count: {len(signals)}')
for tag in sorted(signals.keys()):
    print(f'  - {tag}: {type(signals[tag]).__name__}')
"

# 2. Integration test: restart Signal Engine
docker compose -f aureus-foundation.yml restart aureus-signal
docker logs aureus_signal_engine --tail 20
# Expect: No errors, signals running normally

# 3. Verify live state unchanged
curl http://localhost:8001/api/v1/state/XAUUSD | python -m json.tool | head -10
```

## Rollback

Nếu refactor gây lỗi: revert `main.py` về inline signal registration (git checkout).
