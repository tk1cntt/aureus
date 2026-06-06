# Phase 58: Fix inactive trading strategies - Context

**Gathered:** 2026-06-06
**Status:** Ready for planning

<domain>
## Phase Boundary

Verify rằng 8 strategies không bao giờ trigger (0 lệnh) có thể emit signals end-to-end trên live runtime. Mỗi strategy phải đi qua đầy đủ pipeline: detector → signal bridge → context filter → sequence matching. Phase này chỉ fix runtime/pipeline — không đổi seed strategy config.

**8 strategies trong scope:**

| Strategy | Signal Tags | Entry | Root Cause (từ quick 260602) |
|----------|-------------|-------|-------------------------------|
| TPO_VA_REJECTION_BULL | `tpo_va_rejection_bull` | MARKET | Tags không map + tpo_context filter missing (260602-pvk: FIXED) |
| TPO_VA_REJECTION_BEAR | `tpo_va_rejection_bear` | MARKET | Tags không map + tpo_context filter missing (260602-pvk: FIXED) |
| TPO_VA_BREAKOUT_BULL | `tpo_va_breakout_bull` | MARKET | Tags không map + tpo_context filter missing (260602-pvk: FIXED) |
| TPO_VA_BREAKOUT_BEAR | `tpo_va_breakout_bear` | MARKET | Tags không map + tpo_context filter missing (260602-pvk: FIXED) |
| TPO_TREND_PULLBACK_BULL | `tpo_trend_pullback_bull` | MARKET | Tags không map + tpo_context filter missing (260602-pvk: FIXED) |
| TPO_TREND_PULLBACK_BEAR | `tpo_trend_pullback_bear` | MARKET | Tags không map + tpo_context filter missing (260602-pvk: FIXED) |
| FZ_CONT_BULL | `choch_up` → `bos_up` | LIMIT | `bos_up`/`bos_down` chưa implement (260602-riq: FIXED) |
| FZ_CONT_BEAR | `choch_down` → `bos_down` | LIMIT | `bos_up`/`bos_down` chưa implement (260602-riq: FIXED) |

**Out of scope:**
- Cải thiện winrate SESSION_SWEEP_* (43%), LIMIT_PULLBACK_* (35%)
- Root cause cho LIMIT_OB_EDGE, LIMIT_EMA_TOUCH, TREND_CONT_FVG, TREND_CONT_LIMIT
- Thay đổi seed strategy config (min_score, context_filter, bias array)

</domain>

<decisions>
## Implementation Decisions

### Success criteria
- Live runtime emit được signal tag qua đầy đủ pipeline: detector → bridge → context filter → sequence matching
- Tối thiểu: verify signal tag xuất hiện trong Redis event stream hoặc sequence match được
- Không yêu cầu winrate tốt, không yêu cầu có lệnh thực qua MT5
- Không thay đổi seed strategy config

### Signal pipeline stages cần verify
- **Stage A**: TPO/BOS detector chạy và emit candidate
- **Stage B**: Signal bridge (map tag to candle record events)
- **Stage C**: Context filter validate (tpo_context handler)
- **Stage D**: Sequence matching (tags xuất hiện trong events array)
- **Stage E**: Strategy match event emitted (STRATEGY_MATCH)

### Approach: verification-first
- Dùng deterministic replay/backtest harness (từ quick 260425-il0)
- Hoặc dùng live dev runtime với instrumented logging
- Mỗi stage verify bằng evidence cụ thể: log line, Redis key, DB record

### Claude's Discretion
- Thứ tự verify 8 strategies (nên verify TPO trước vì 260602-pvk đã fix gần đây, rồi FZ_CONT sau vì 260602-riq mới implement)
- Cách instrument để capture signal flow evidence
- Có verify hay chỉ review code + unit test

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Quick task analysis (root cause đã xác định)

- `.planning/quick/260602-pvk-tpo-detector-signal-debug/260602-pvk-SUMMARY.md` — Root cause TPO: tags không map + tpo_context filter missing. Đã fix ở `live_engine.py` và `template.py`
- `.planning/quick/260602-qu7-fz-cont-signal-debug/260602-qu7-SUMMARY.md` — Root cause FZ_CONT: `bos_up`/`bos_down` chưa implement. Recommend implement BOS detector
- `.planning/quick/260602-riq-implement-bos-signals/260602-riq-SUMMARY.md` — Implement `bos_up`/`bos_down` ở `structure.py` + consumer signals + factory registration. Tests pass

### Quick task performance (baseline data)

- `.planning/quick/260602-0d8-tpo-strategy-performance-review/260602-0d8-SUMMARY.md` — TPO strategies: 0 lệnh all-time. Verify strategies có lệnh (TREND_CONT_*, CISD_CONSENSUS_*) winrate 60-64%. SESSION_SWEEP winrate 43%, LIMIT_PULLBACK winrate 35%

### Signal pipeline architecture

- `services/aureus-signal/engine/live_engine.py` — TPO tag emitter (Stage B bridge), candle state management
- `services/aureus-signal/engine/strategies/template.py` — Sequence evaluator, context filter handler (đã thêm tpo_context)
- `services/aureus-signal/engine/signals/structure.py` — CHOCH/BOS detection, emit tags
- `services/aureus-signal/engine/signals/bos_up.py` — Consumer signal cho bos_up
- `services/aureus-signal/engine/signals/bos_down.py` — Consumer signal cho bos_down
- `services/aureus-signal/engine/signal_factory.py` — Register bos_up/bos_down signals
- `services/aureus-signal/engine/signals/tpo.py` — TPO detector base
- `services/aureus-signal/engine/logic/tpo_detectors/` — VARejection, VABreakoutAcceptance, TrendPullback detectors
- `services/aureus-signal/engine/strategies/seed_strategies.py` — 28 strategy templates (8 trong scope)

### Replay/test harness

- Deterministic TPO replay từ quick 260425-il0 — dùng để verify TPO signal flow mà không cần live market

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **Deterministic replay harness**: từ 260425-il0, cho phép replay historical candle data qua signal pipeline mà không cần live market. Có thể dùng để verify TPO/BOS signal flow
- **22 existing TPO unit tests**: pass post 260602-pvk fix
- **Strategy config**: 8 strategies đã có config đầy đủ trong seed_strategies.py

### Pre-fixed Issues (dùng đã implement, cần verify)
- **260602-pvk fix**: `live_engine.py` đã pass `record` vào `_maybe_emit_tpo_strategy_tags()`, `template.py` đã có `tpo_context` handler
- **260602-riq fix**: `structure.py` đã emit `bos_up`/`bos_down`, consumer signals + factory registration đã thêm

### Integration Points
- Signal bridge → Redis stream: `aureus:stream:{symbol}:signals`
- Sequence evaluator → Strategy match → Redis channel: `aureus:signals:{symbol}`
- TPO context builder → State → Context filter

</code_context>

<specifics>
## Specific Ideas

- FZ_CONT_BULL/BEAR dùng LIMIT entry → sau khi sequence match, strategy match event emit, trader dispatch LIMIT order đến MT5. Entry method: `FIRST_HIGH_LOW_PIVOT` / `FIRST_LOW_HIGH_PIVOT`
- TPO strategies dùng MARKET entry → sau khi sequence match, trader dispatch MARKET order
- 6 TPO strategies đều require D1 bias: `["bullish", "neutral", "neutral-up"]` (bullish) và `["bearish", "neutral", "neutral-down"]` (bearish) với `min_confidence_pct: 70`
- FZ_CONT strategies: `bos_up`/`bos_down` chỉ emit khi không có opposing extreme (khác với CHOCH)

</specifics>

<deferred>
## Deferred Ideas

### Out of scope (user decision)
- Cải thiện winrate SESSION_SWEEP_* (43%) — belong in scoring/reporting phase
- Cải thiện winrate LIMIT_PULLBACK_* (35%) — belong in scoring/reporting phase
- Root cause LIMIT_OB_EDGE, LIMIT_EMA_TOUCH, TREND_CONT_FVG, TREND_CONT_LIMIT — new phase needed
- Tune strategy config (min_score, bias array, min_confidence_pct) — user chọn "không đổi seed"

### Reviewed Todos (not folded)
- Không có todo từ .planning/todos/ pending trùng với phase 58

</deferred>

---

*Phase: 58-fix-inactive-trading-strategies*
*Context gathered: 2026-06-06*
