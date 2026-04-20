import React from "react";
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, waitFor, cleanup } from "@testing-library/react";
import PerformancePage from "../page";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  useSearchParams: () => ({ get: (_key: string) => null }),
}));

vi.mock("@/context/SymbolsContext", () => ({
  useSymbols: () => ({ symbols: ["EURUSD"] }),
}));

vi.mock("@/components/Sidebar", () => ({
  Sidebar: () => <div data-testid="sidebar" />,
}));

vi.mock("@/components/ClientOnly", () => ({
  default: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

vi.mock("../components/FilterBar", () => ({
  FilterBar: () => <div data-testid="filter-bar" />,
}));

vi.mock("../components/EquityChart", () => ({
  EquityChart: () => <div data-testid="equity-chart" />,
}));

vi.mock("../components/PerformanceTable", () => ({
  PerformanceTable: ({ trades }: { trades: Array<{ symbol: string }> }) => (
    <div>{trades[0]?.symbol ?? "no-trades"}</div>
  ),
}));

vi.mock("../components/MetricCard", () => ({
  MetricCard: ({ value }: { value: string | number }) => <div>{value}</div>,
}));

describe("/performance contract", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
    cleanup();
    localStorage.clear();
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("uses same filter params for metrics/trades/equity and renders success data", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);

      if (url.includes("/performance/metrics")) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            metrics: {
              total_trades: 10,
              win_rate: 60,
              profit_factor: 1.8,
              max_drawdown: 5.5,
              avg_rr: 1.2,
              sharpe_ratio: 1.1,
              total_profit: 120.5,
              total_loss: -40,
              avg_win: 20,
              avg_loss: -10,
              best_trade: 50,
              worst_trade: -20,
            },
            meta: {
              symbol: "EURUSD",
              strategy_id: 2,
              start: "2026-04-01T00:00",
              end: "2026-04-07T00:00",
              source: "db",
            },
          }),
        } as Response;
      }

      if (url.includes("/performance/trades")) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            data: [
              {
                id: 1,
                trace_id: "trace-1",
                ticket: 1001,
                symbol: "EURUSD",
                strategy_name: "S2",
                direction: "BUY",
                entry_price: 1.1,
                exit_price: 1.2,
                sl: 1.0,
                tp: 1.3,
                volume: 0.1,
                profit: 12.5,
                commission: 0,
                swap: 0,
                filled_at: "2026-04-02T01:00:00Z",
                closed_at: "2026-04-02T02:00:00Z",
              },
            ],
            meta: {
              total: 1,
              page: 1,
              page_size: 20,
              total_pages: 1,
              filters: {
                symbol: "EURUSD",
                strategy_id: 2,
                start: "2026-04-01T00:00",
                end: "2026-04-07T00:00",
                status: "closed",
              },
            },
          }),
        } as Response;
      }

      return {
        ok: true,
        status: 200,
        json: async () => ({
          data: [
            {
              time: "2026-04-02T00:00:00Z",
              equity: 1000,
              pnl: 0,
            },
          ],
          meta: {
            source: "db",
            points: 1,
          },
        }),
      } as Response;
    });

    global.fetch = fetchMock as unknown as typeof fetch;

    render(<PerformancePage />);

    await screen.findByText("Performance Dashboard");
    await screen.findByText("60.0%");
    await screen.findByText("+120.50");
    await screen.findByText("EURUSD");

    await waitFor(() => {
      expect(fetchMock.mock.calls.length).toBeGreaterThanOrEqual(3);
    });

    const urls = fetchMock.mock.calls.slice(0, 3).map((call) => String(call[0]));
    expect(urls).toHaveLength(3);
    const metricsUrl = urls.find((u) => u.includes("/performance/metrics"));
    const tradesUrl = urls.find((u) => u.includes("/performance/trades"));
    const equityUrl = urls.find((u) => u.includes("/performance/equity-curve"));

    expect(metricsUrl).toBeDefined();
    expect(tradesUrl).toBeDefined();
    expect(equityUrl).toBeDefined();

    const m = new URL(metricsUrl as string);
    const t = new URL(tradesUrl as string);
    const e = new URL(equityUrl as string);

    const dims = ["symbol", "strategy_id", "start", "end"] as const;
    for (const dim of dims) {
      expect(t.searchParams.get(dim)).toBe(m.searchParams.get(dim));
      expect(e.searchParams.get(dim)).toBe(m.searchParams.get(dim));
    }
  });

  it("shows explicit error state when API returns invalid-filter structured error", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);

      if (url.includes("/performance/metrics")) {
        return {
          ok: false,
          status: 422,
          json: async () => ({
            error: {
              code: "invalid_filter",
              message: "start must be before end",
            },
          }),
        } as Response;
      }

      return {
        ok: true,
        status: 200,
        json: async () => ({ data: [], meta: { source: "db", points: 0 } }),
      } as Response;
    });

    global.fetch = fetchMock as unknown as typeof fetch;

    render(<PerformancePage />);

    expect(await screen.findByText("Invalid filter: start must be before end")).toBeTruthy();

    expect(screen.queryByText("No trades found — adjust filters or wait for live trades")).toBeNull();
  });
});
