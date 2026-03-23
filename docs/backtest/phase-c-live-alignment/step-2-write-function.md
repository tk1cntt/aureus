# Step 2: Thêm write_signal_snapshot() Function

> **Phase**: C — Live System Alignment  
> **Thời gian**: ~20 phút | **Risk**: Thấp  
> **Input**: `snapshot_utils.py` từ Phase B  
> **Output**: Function `write_signal_snapshot()` trong `main.py`

---

## Mô tả

Async function nhận state + candle, gọi `build_snapshot()` → INSERT vào DB. Wrap trong try/except để KHÔNG crash main loop khi DB error.

## Checklist

- [ ] Import `build_snapshot` từ `snapshot_utils.py`
- [ ] Function `async def write_signal_snapshot(db_pool, symbol, ts_unix, state)`
- [ ] Gọi `build_snapshot(state, candle)` để collect data
- [ ] `db_pool.execute(INSERT ... ON CONFLICT DO UPDATE)`
- [ ] try/except: log error nhưng KHÔNG re-raise
- [ ] Không block main loop (function body chỉ chạy khi await)

## Điều kiện nghiệm thu

| # | Điều kiện | Pass? |
|:---|:---|:---|
| 1 | Function tồn tại và importable | [ ] |
| 2 | Ghi 1 snapshot thành công vào DB | [ ] |
| 3 | DB error → log warning, không crash | [ ] |
| 4 | ON CONFLICT → update thay vì error | [ ] |

## Test

```python
# Simulate DB error
async def test_graceful_error():
    # Pass None as db_pool → should log error, not crash
    await write_signal_snapshot(None, "TEST", 123456, mock_state)
    print("✅ Graceful error handling OK")
```

## Rollback

Remove function. Không ảnh hưởng gì vì chưa được gọi từ main loop.
