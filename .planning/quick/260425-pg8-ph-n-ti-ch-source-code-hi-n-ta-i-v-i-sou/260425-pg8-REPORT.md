# Quick 260425-pg8 Report: So sánh source hiện tại với commit 8b1b282

## 1) Kết luận ngắn

Khác biệt có khả năng gây nghẽn nằm ở `services/aureus-signal/engine/signals/trend.py`, được đưa vào sau baseline `8b1b282d5708df0158929893f9b884805011c910` bởi quick `260425-kj9`/commit `84af094`: trend signal đổi từ logic EMA đơn giản sang scoring tổng hợp và thêm nhánh `_ob_score()` đọc `state_obj.obs[*].quality` rồi ép `float(...)` trực tiếp.

Runtime evidence khớp chính xác với nhánh này: `Signal trend calc error: could not convert string to float: 'LOW'/'MEDIUM'`. `LOW`/`MEDIUM` là categorical order-block quality, không phải số. Khi candle mới tới aureus-signal, trend calc gặp OB quality dạng chữ, raise `ValueError`, làm candle đó bị skip/abort trong phần signal calculation. Vì gateway/db-writer vẫn nhận/ghi candle nhưng signal stream không publish tiếp đều, strategy executor nhìn như bị đói dữ liệu/nghẽn.

Trạng thái HEAD hiện tại (`4313b84`) đã có quick `260425-nub` fix lỗi này bằng numeric coercion trong `TrendSignal._ema_value`, `_ema_score`, `_ob_score`. Nếu runtime vẫn log lỗi `LOW`/`MEDIUM` sau full restart, khả năng cao container/image `aureus-signal-dev` đang chạy source cũ/chưa rebuild đúng image, hoặc log được thu từ trước khi fix `b669aa7` được áp dụng.

## 2) Timeline / symptom

- Baseline so sánh: `8b1b282d5708df0158929893f9b884805011c910` (`260425-kwd`, report-only TPO shape classification).
- Sau baseline có chuỗi thay đổi liên quan:
  - `84af094` `260425-kj9`: update `TrendSignal` theo advisory, thêm scoring tổng hợp `structure_score + ema_score + ob_score + sweep_score`.
  - `8e97d09`, `7c01219`: TPO shape classifier / metadata; chủ yếu ảnh hưởng TPO snapshot/telegram/replay.
  - `ca8ac46`, `0ad72bf`, `b669aa7`: quick `260425-nub` fix regression `LOW` categorical conversion.
- Runtime evidence từ orchestrator trước executor:
  - gateway nhận BTCUSD/ETHUSD candles.
  - db-writer insert/update candles.
  - aureus-signal log lặp: `Signal trend calc error: could not convert string to float: 'LOW'` cho BTCUSD tại `t=1777126440`; `'MEDIUM'` cho ETHUSD tại `t=1777126500`.
  - Strategy executor vào main loop nhưng bị starved vì signal stream dừng/stall.

## 3) Diff evidence so với `8b1b282d5708df0158929893f9b884805011c910`

Commands đã chạy:

- `git -C D:/Aureus diff --stat 8b1b282d5708df0158929893f9b884805011c910..HEAD`
- `git -C D:/Aureus diff --name-status 8b1b282d5708df0158929893f9b884805011c910..HEAD -- services/aureus-signal services gateway db-writer`
- `git -C D:/Aureus log --oneline --decorate --ancestry-path 8b1b282d5708df0158929893f9b884805011c910..HEAD`
- `git -C D:/Aureus show 8b1b282d5708df0158929893f9b884805011c910:services/aureus-signal/engine/signals/trend.py`
- `git -C D:/Aureus show 84af094:services/aureus-signal/engine/signals/trend.py`
- `git -C D:/Aureus diff 8b1b282d5708df0158929893f9b884805011c910..HEAD -- services/aureus-signal/engine/signals/trend.py ...`

| File / function | Diff evidence | Liên quan stall? | Lý do |
|---|---|---:|---|
| `services/aureus-signal/engine/signals/trend.py` / `TrendSignal.calculate` | Sau baseline có scoring mới: `structure_score`, `ema_score`, `ob_score`, `sweep_score`, `ema200_penalty`; HEAD hiện tại đã thêm guard `pd.to_numeric(...)`. | Có | Đây là code path log lỗi `Signal trend calc error`. Runtime string `LOW`/`MEDIUM` khớp với lỗi ép numeric trong trend calculation. |
| `services/aureus-signal/engine/signals/trend.py` / `_ema_value` | Baseline/`84af094`: `return float(ema_state["current"])` và `return float(df[col].iloc[-1])`; HEAD: `pd.to_numeric(..., errors="coerce")`, invalid -> `None`. | Có, nhưng không phải bằng chứng mạnh nhất cho `MEDIUM` | Nếu categorical rơi vào cột/state EMA thì gây đúng `ValueError`. Quick `nub` đã cover test `ema_3="LOW"`. |
| `services/aureus-signal/engine/signals/trend.py` / `_ema_score` | Baseline/`84af094`: `close = float(df["c"].iloc[-1])`; HEAD: numeric coercion và return `0.0` nếu invalid. | Có phụ | Bảo vệ thêm boundary numeric, nhưng candle close thường là số nên ít phù hợp với `LOW`/`MEDIUM` hơn OB quality. |
| `services/aureus-signal/engine/signals/trend.py` / `_ob_score` | Baseline/`84af094`: `quality = float(ob.get("quality") or 0.5)`, `body_ratio = float(...)`; HEAD: `pd.to_numeric(..., errors="coerce")`, non-numeric fallback `0.5`. | Rất có khả năng là root cause trực tiếp | `LOW`/`MEDIUM` là category thường gặp cho quality; stack symptom nói trend calc error convert string to float. Đây là exact expression có thể raise `ValueError: could not convert string to float: 'LOW'`. |
| `services/aureus-signal/tests/test_trend_categorical_values.py` | File mới sau quick `260425-nub`, test `quality="LOW"` không raise và categorical EMA không raise. | Fix evidence | Xác nhận maintainers đã nhận diện đúng boundary và thêm regression test. |
| `services/aureus-signal/engine/signals/tpo.py` | Nhiều thay đổi calibrated classifier, confidence, metadata. | Ít khả năng gây stall này | Diff tạo categorical shape/quality metadata TPO, nhưng runtime error nằm ở `Signal trend calc error` và conversion `LOW`/`MEDIUM` sang float; không thấy nhánh TPO trực tiếp ép các string này trong trend calc. |
| `services/aureus-signal/engine/indicator_snapshot.py` | Chỉ guard TPO block bằng `_get_tpo_block`. | Không | Ảnh hưởng snapshot payload, không giải thích trend calc float conversion. |
| `services/aureus-notifier/*`, `mql5/AureusProvider.mq5` | Formatter / diagnostics INVALID_PRICE. | Không | Không nằm trong candle-to-signal trend pipeline. |
| `gateway`, `db-writer` | `git diff --name-status ... -- services/aureus-signal services gateway db-writer` không cho thấy thay đổi riêng dưới `gateway`/`db-writer`; chỉ có services liên quan signal/notifier/test. | Loại trừ tương đối | Phù hợp runtime: ingest vẫn hoạt động, lỗi nằm sau db-writer ở signal calc. |

Diff stat tổng quan cho thấy 27 files changed, 2503 insertions, 62 deletions; phần source liên quan trực tiếp nhất là `services/aureus-signal/engine/signals/trend.py` và test regression `services/aureus-signal/tests/test_trend_categorical_values.py`.

## 4) Runtime correlation

Runtime log collection trong executor:

- Theo ràng buộc dự án, thử chạy Docker qua WSL:
  - `wsl -d Ubuntu-24.04 -u root bash -lc "docker logs --tail 400 aureus-signal-dev ..."`
  - Kết quả: WSL distro `Ubuntu-24.04` không tồn tại trong environment executor (`WSL_E_DISTRO_NOT_FOUND`).
- Fallback read-only bằng Docker CLI trực tiếp:
  - `docker logs --tail 200 aureus-signal-dev ...`
  - `docker logs --tail 100 aureus-gateway-dev ...`
  - `docker logs --tail 100 aureus-db-writer-dev ...`
  - Kết quả trong environment này không trả dòng match mới cho regex `Signal trend calc error|LOW|MEDIUM|1777126440|1777126500` và cũng không trả ingest lines theo regex. Vì vậy runtime conclusion dựa trên evidence orchestrator đã cung cấp và source diff/log correlation, không paste thêm log runtime mới.

Correlation theo code path:

1. Candle BTCUSD/ETHUSD tới gateway và db-writer, nên TCP ingest/DB persistence không phải điểm nghẽn chính.
2. aureus-signal xử lý candle mới và gọi trend signal calculation.
3. Trong source sau `260425-kj9`, `TrendSignal.calculate()` gọi `_ob_score(recent_obs, current_t)`.
4. `_ob_score()` trong bản lỗi dùng `float(ob.get("quality") or 0.5)`.
5. Khi OB quality là `LOW` hoặc `MEDIUM`, Python raise `ValueError: could not convert string to float`.
6. Exception được log dạng `Signal trend calc error`, candle hiện tại không hoàn tất signal publish/stream update; strategy executor không nhận đủ signal mới nên bị starved dù candle vẫn tới hệ thống.

## 5) Root cause + stall mechanism

Root cause trực tiếp: mismatch schema/semantic giữa producer của order-block metadata và consumer `TrendSignal._ob_score()`.

- Producer/state có thể chứa `quality` dạng categorical (`LOW`, `MEDIUM`, có thể `HIGH`).
- Consumer mới sau `260425-kj9` giả định `quality` là numeric float trong `[0,1]`.
- Không có coercion/validation ở boundary, nên categorical string làm `float(...)` raise exception.

Stall mechanism:

- Lỗi không làm gateway/db-writer dừng, vì candle ingest nằm upstream.
- Lỗi xảy ra trong aureus-signal khi build signal từ candle đã nhận.
- Nếu exception được catch ở signal level và log rồi skip, service vẫn sống nhưng không publish signal/event tiếp cho candle lỗi.
- Strategy executor phụ thuộc signal stream nên không có input mới; biểu hiện bên ngoài là "service không xử lý tiếp mặc dù nhận được candle".

Trạng thái source hiện tại:

- HEAD hiện tại đã có fix trong `TrendSignal._ob_score()`:
  - `quality = pd.to_numeric(pd.Series([ob.get("quality")]), errors="coerce").iloc[0]`
  - invalid/categorical -> fallback `0.5`.
- HEAD cũng guard `_ema_value()` và `_ema_score()`.
- Summary quick `260425-nub` ghi rõ verification: `11 passed`, commits `ca8ac46`, `0ad72bf`, `b669aa7`.

Vì vậy nếu container runtime vẫn phát lỗi `LOW`/`MEDIUM` sau HEAD `4313b84`, nguyên nhân vận hành có khả năng là stale runtime image/source: service chưa chạy image chứa commit `b669aa7`, hoặc logs được quan sát là log cũ trước khi rebuild/restart đúng service.

## 6) Recommended next action

Ưu tiên an toàn, nhỏ, định lượng được:

1. Không rollback toàn bộ về `8b1b282` nếu mục tiêu chỉ xử lý lỗi nghẽn này. Rollback sẽ mất nhiều thay đổi TPO/MQL5/notifier sau baseline và rộng hơn cần thiết.
2. Nếu runtime hiện tại chưa có fix `260425-nub`: hotfix tối thiểu là áp dụng đúng phần `b669aa7` trong `services/aureus-signal/engine/signals/trend.py` tại `_ob_score()` để non-numeric `quality`/`body_ratio` fallback `0.5`.
3. Bắt buộc rebuild/restart `aureus-signal-dev` để container nhận code mới, vì `RUN_SERVICES.md` ghi backend Docker không mount source code. Lệnh chuẩn theo docs là rebuild service signal qua WSL; executor này không restart vì scope cấm restart service.
4. Test bắt buộc trước/sau deploy:
   - Focused regression: `services/aureus-signal/tests/test_trend_categorical_values.py`.
   - Runtime verify: sau rebuild, tail log `aureus-signal-dev` không còn `Signal trend calc error` với `LOW`/`MEDIUM` khi BTCUSD/ETHUSD candle mới tới.
   - Pipeline verify: gateway/db-writer vẫn ingest candle và downstream signal/strategy executor nhận signal mới sau timestamp lỗi cũ `1777126440/1777126500`.
5. Nếu sau rebuild đúng HEAD vẫn còn lỗi, kiểm tra stack trace đầy đủ của `Signal trend calc error`; khả năng còn boundary khác ép float categorical ngoài `_ob_score()`, nhưng diff hiện tại cho thấy boundary đã biết trong trend.py đã được guard.

## 7) Verification / scope

- Không sửa production source.
- Không restart service.
- Artifact tạo: `D:/Aureus/.planning/quick/260425-pg8-ph-n-ti-ch-source-code-hi-n-ta-i-v-i-sou/260425-pg8-REPORT.md`.
- `git -C D:/Aureus status --short` trước khi viết report chỉ cho thấy quick directory `260425-pg8...` là untracked; không có source file modified trong executor này.
