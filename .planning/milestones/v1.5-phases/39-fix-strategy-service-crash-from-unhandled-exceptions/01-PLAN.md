# Phase 39: Fix Strategy Service Crash from Unhandled Exceptions — Plan 01

**Wave:** 1
**Depends on:** None
**Autonomous:** Yes
**Files modified:** `services/aureus-signal/engine/simulated_orders.py` (bare except fix)

## Objective
Sửa bare `except:` clause trong `simulated_orders.py` để ngăn chặn việc bắt luôn `KeyboardInterrupt` và `SystemExit`, gây ngăn clean shutdown.

## Read first
- `services/aureus-signal/engine/simulated_orders.py` — file cần sửa (tìm bare `except:`)
- `services/aureus-signal/engine/orders.py` — để đảm bảo pattern nhất quán

## Plan
1. Dùng `grep_search` với regex `except:` trong `simulated_orders.py` để tìm tất cả bare except clauses
2. Kiểm tra từng location — đảm bảo context là `except Exception:` không phải `except SpecificError:`
3. Thay thế bare `except:` bằng `except Exception:`
4. Verify: `python -m py_compile services/aureus-signal/engine/simulated_orders.py`

## Acceptance criteria
- [ ] Không còn bare `except:` nào trong `simulated_orders.py` (verify bằng grep)
- [ ] File compile thành công qua py_compile
- [ ] Không có lint errors mới sinh ra

## Requirements addressed
- D7: Thay bare `except:` bằng `except Exception:`
