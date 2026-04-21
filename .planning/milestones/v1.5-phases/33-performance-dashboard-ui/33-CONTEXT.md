# Phase 33 — Performance Dashboard UI

## CONTEXT

**Phase:** 33
**Requirements:** PERF-08
**Goal:** Trang web thống kê performance tích hợp vào aureus-dashboard.

---

## Decisions

### D1: Chart Library — Use Existing `lightweight-charts` (NOT recharts)

**Decision:** Sử dụng **`lightweight-charts` v5.1.0** (TradingView) đã có trong project thay vì recharts.

**Rationale:**
- Project đã cài `lightweight-charts` v5.1.0 — không cần thêm dependency
- `BacktestChart.tsx` đã có equity curve sub-chart implementation
- TradingView charts phù hợp với trading dashboard hơn recharts
- Consistent với existing chart UI (SMCChart, BacktestChart)
- Giảm bundle size — không need thêm chart library

**Implementation:**
- Reuse `BacktestChart` pattern cho equity curve
- Custom data format: `{time: string, value: number}[]` → lightweight-charts AreaSeries

---

### D2: New Page — `/performance` Route

**Decision:** Tạo trang mới `web/src/app/performance/page.tsx` với Next.js App Router.

**Page structure:**
```
src/app/performance/
  page.tsx              — Main performance dashboard
  components/
    MetricCard.tsx      — Reusable stat card (extract from backtest)
    PerformanceTable.tsx — Paginated trade list
    FilterBar.tsx       — Symbol, strategy, date range filters
    EquityChart.tsx     — Equity curve using lightweight-charts
```

**Layout:** Use existing root `layout.tsx` with `SymbolsProvider` — no custom layout needed.

**Rationale:**
- Next.js App Router = file-based routing → just create `performance/page.tsx`
- Inherits Sidebar, SymbolsContext, dark theme automatically
- Consistent with existing pages: `/strategies`, `/backtest`, `/ai-insights`

---

### D3: Component Extraction — Extract Reusable Components

**Decision:** Extract existing inline components thành shared components:

| Component | Extract From | Reuse For |
|-----------|-------------|-----------|
| `MetricCard` | `backtest/page.tsx` inline StatCard | Performance metrics cards |
| `PerformanceTable` | `backtest/page.tsx` inline table | Trade history với pagination |
| `FilterBar` | New component | All filter UI |

**MetricCard pattern (existing):**
```tsx
<div className="bg-[#1E222D] border border-gray-800 rounded-xl p-4">
  <div className="text-xs text-gray-500 uppercase">{label}</div>
  <div className="text-2xl font-bold mt-1">{value}</div>
</div>
```

**Rationale:**
- DRY principle — backtest page đã có StatCard inline
- Extract giúp maintain consistent styling
- Performance page cần 6 metric cards → reusable component cần thiết

---

### D4: API Integration — Native `fetch` với Phase 32 Endpoints

**Decision:** Sử dụng native `fetch` pattern (consistent với existing codebase) để gọi Phase 32 APIs.

**API calls:**
```tsx
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001/api/v1";

// Fetch metrics (cached 60s)
const res = await fetch(`${API_BASE}/performance/metrics?${params}`);
const data = await res.json() as { metrics: MetricsData; meta: MetaResponse };

// Fetch trades (paginated)
const res = await fetch(`${API_BASE}/performance/trades?page=${page}&page_size=20&${params}`);
const data = await res.json() as { data: Trade[]; meta: MetaResponse };

// Fetch equity curve (cached 30s)
const res = await fetch(`${API_BASE}/performance/equity-curve?${params}`);
const data = await res.json() as { data: EquityPoint[]; meta: { source: string; points: number } };
```

**Data fetching pattern:** Parallel fetch với `Promise.all`:
```tsx
const [metricsRes, tradesRes, equityRes] = await Promise.all([
  fetch(`${API_BASE}/performance/metrics?${params}`),
  fetch(`${API_BASE}/performance/trades?page=1&page_size=20&${params}`),
  fetch(`${API_BASE}/performance/equity-curve?${params}`),
]);
```

**Rationale:**
- Existing codebase uses native `fetch` exclusively — no axios, SWR, react-query
- Parallel fetching giảm latency (3 calls → 1 round-trip)
- Phase 32 APIs đã có Redis caching → frontend không cần thêm cache layer
- Consistent với pattern: `BacktestChart`, `Sidebar`, `AIInsights` đều dùng `fetch`

---

### D5: Filter UI — Symbol, Strategy, Date Range

**Decision:** FilterBar component với 3 filters chính:

| Filter | UI Element | Source |
|--------|-----------|--------|
| Symbol | Dropdown (reuse `SymbolsContext`) | `useSymbols()` hook |
| Strategy | Multi-select dropdown | `fetch(API_BASE/strategies)` |
| Date Range | `<input type="date">` | Native date picker |

**Filter state management:** URL search params (Next.js `useSearchParams`):
```tsx
const params = new URLSearchParams();
if (symbol) params.set("symbol", symbol);
if (strategyId) params.set("strategy_id", strategyId);
if (startDate) params.set("start", startDate.toISOString());
if (endDate) params.set("end", endDate.toISOString());
router.push(`/performance?${params.toString()}`);
```

**Rationale:**
- URL params = shareable URLs (user có thể bookmark/filter URL)
- Consistent với Next.js App Router patterns
- Không cần state management library — URL là source of truth
- Native date picker đủ cho v1 — không cần date range library

---

### D6: Layout & Responsive Design

**Decision:** 3-section layout:

```
┌─────────────────────────────────────────────────┐
│ FilterBar (symbol, strategy, date range)         │
├─────────────────────────────────────────────────┤
│ Metric Cards (6 cards, 3 columns × 2 rows)       │
│ [Win Rate] [Net PnL] [Profit Factor]            │
│ [Max DD]   [Avg R:R] [Sharpe Ratio]             │
├─────────────────────────────────────────────────┤
│ Equity Chart (full width, 300px height)          │
├─────────────────────────────────────────────────┤
│ Trade History Table (paginated, 20 rows/page)    │
│ [Ticket] [Symbol] [Direction] [PnL] [Date]      │
└─────────────────────────────────────────────────┘
```

**Responsive breakpoints:**
- Desktop (>1024px): 3 columns metric cards
- Tablet (768-1024px): 2 columns
- Mobile (<768px): 1 column, stacked layout

**Styling:** Reuse existing dark theme tokens:
- Card bg: `bg-[#1E222D] border border-gray-800 rounded-xl`
- Primary text: `text-white`
- Secondary text: `text-gray-500`
- Green (profit): `text-green-500`
- Red (loss): `text-red-500`

**Rationale:**
- Layout consistent với existing dashboard pages
- Mobile responsive — traders check phone frequently
- Reuse design tokens → consistent với toàn bộ app

---

## Reusable Assets

### EXISTS (can reuse):
- ✅ Next.js App Router: `src/app/` structure, file-based routing
- ✅ Tailwind CSS v4: Dark theme tokens, utility classes
- ✅ `lightweight-charts` v5.1.0: TradingView chart library
- ✅ `SymbolsContext`: Global symbol list provider
- ✅ `Sidebar.tsx`: Navigation component (auto-included via layout)
- ✅ `ClientOnly.tsx`: SSR hydration guard
- ✅ `fetch` pattern: Native API calls (no wrapper needed)
- ✅ StatCard pattern: Inline in `backtest/page.tsx`
- ✅ Trade table pattern: Inline in `backtest/page.tsx`
- ✅ Dark theme tokens: `#131722`, `#1E222D`, `#0B0E11`
- ✅ Phase 32 APIs: `/performance/trades`, `/metrics`, `/equity-curve`

### MUST BUILD:
- ❌ `src/app/performance/page.tsx` — New performance dashboard page
- ❌ `MetricCard` component — Extract from backtest page
- ❌ `PerformanceTable` component — Paginated trade list
- ❌ `FilterBar` component — Symbol, strategy, date range filters
- ❌ `EquityChart` component — Equity curve with lightweight-charts
- ❌ URL param-based filtering logic

## Carry-forward from prior phases

| Source | Decision | Relevance |
|--------|----------|-----------|
| Phase 30 | `aureus_trades` table structure | Data source for trade history |
| Phase 32 | Performance API endpoints | Frontend calls these endpoints |
| Phase 32 | Response envelope format | `{data, meta}` pattern for API responses |
| Phase 32 | Redis caching (60s/30s TTL) | Frontend không cần thêm cache layer |

## Requirements Detail

### PERF-08: Performance Dashboard UI
- [ ] Trade history page với pagination (20 rows/page)
- [ ] Performance metrics cards (win rate, PF, drawdown, R:R, Sharpe, net PnL)
- [ ] Equity curve chart với lightweight-charts
- [ ] Filters: symbol dropdown, strategy multi-select, date range
- [ ] Responsive design (desktop, tablet, mobile)
- [ ] Consistent với existing dark theme

## Success Criteria (Updated)

1. ✅ Trang `/performance` hiển thị trade history với pagination
2. ✅ 6 performance metrics cards hiển thị chính xác (từ Phase 32 API)
3. ✅ Equity curve chart render đúng với lightweight-charts
4. ✅ Filters hoạt động: symbol, strategy, date range (URL params)
5. ✅ Responsive design: 3 columns → 2 → 1 theo breakpoints
6. ✅ Consistent dark theme với existing dashboard

---
*Context created: 2026-04-06*
*Ready for planning and execution*
