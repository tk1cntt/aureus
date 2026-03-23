# Aureus Backtest Architecture — Project Execution

> **Tạo ngày**: 2026-03-02  
> **Master Plan**: [BACKTEST_ARCHITECTURE_PLAN.md](../BACKTEST_ARCHITECTURE_PLAN.md)

## Phases (Thứ tự ưu tiên: Dễ → Khó, Ít ảnh hưởng → Nhiều ảnh hưởng)

| Phase | Tên | Độ khó | Ảnh hưởng Live | Ước thời gian |
|:---|:---|:---|:---|:---|
| A | [Schema & Migration](./phase-a-schema/) | ⭐ | Zero | 30 phút |
| B | [Signal Computer (Offline)](./phase-b-signal-computer/) | ⭐⭐ | Zero | 2-3 giờ |
| C | [Live System Alignment](./phase-c-live-alignment/) | ⭐⭐ | Thấp (async write) | 1-2 giờ |
| D | [Recovery Enhancement](./phase-d-recovery/) | ⭐⭐⭐ | Trung bình (sửa recalc) | 2-3 giờ |
| E | [Backtest Engine v2](./phase-e-backtest-engine/) | ⭐⭐⭐⭐ | Zero | 3-4 giờ |
| F | [Backtest Chart UI](./phase-f-chart-ui/) | ⭐⭐⭐⭐⭐ | Zero | 5-8 giờ |

## Quy tắc thực hiện

1. **Hoàn thành từng Phase tuần tự** — Phase sau phụ thuộc Phase trước
2. **Mỗi Phase phải pass tất cả acceptance criteria** trước khi chuyển sang Phase tiếp
3. **Rollback plan**: Nếu Phase C/D gây issue cho live → revert commit và quay lại
